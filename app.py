"""AIライティングツール（個人用） - Streamlit + Gemini API"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from gemini_client import available_models, explain_error, get_api_key, stream_generate
from tools import TOOLS, TOOLS_BY_ID, Field, Tool

load_dotenv()

st.set_page_config(page_title="AIライティングツール", page_icon="✍️", layout="wide")

MAX_HISTORY = 30

# ---------------------------------------------------------------------------
# セッション状態の初期化
# ---------------------------------------------------------------------------
st.session_state.setdefault("tool_id", TOOLS[0].id)
st.session_state.setdefault("results", {})  # tool_id -> {"prompt", "output"}
st.session_state.setdefault("history", [])  # 新しい順


def load_history(index: int) -> None:
    """履歴の項目を該当ツールの結果として復元する（on_click コールバック）。"""
    item = st.session_state.history[index]
    st.session_state.tool_id = item["tool_id"]
    st.session_state.results[item["tool_id"]] = {"prompt": item["prompt"], "output": item["output"]}


def save_result(tool: Tool, prompt: str, output: str) -> None:
    st.session_state.results[tool.id] = {"prompt": prompt, "output": output}
    st.session_state.history.insert(0, {
        "tool_id": tool.id,
        "tool_name": f"{tool.icon} {tool.name}",
        "time": datetime.now().strftime("%m/%d %H:%M"),
        "prompt": prompt,
        "output": output,
    })
    del st.session_state.history[MAX_HISTORY:]


# ---------------------------------------------------------------------------
# サイドバー
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("✍️ AIライティング")

    st.radio(
        "ツールを選択",
        options=[t.id for t in TOOLS],
        format_func=lambda tid: f"{TOOLS_BY_ID[tid].icon} {TOOLS_BY_ID[tid].name}",
        key="tool_id",
    )
    tool = TOOLS_BY_ID[st.session_state.tool_id]

    st.divider()
    st.subheader("⚙️ 設定")

    api_key = get_api_key()
    if not api_key:
        api_key = st.text_input(
            "Gemini APIキー",
            type="password",
            help=".env に GEMINI_API_KEY を設定すると入力を省略できます",
        )

    model = st.selectbox("モデル", available_models())
    custom_model = st.text_input(
        "モデル名を直接入力（任意）",
        placeholder="例: gemini-3.8-flash",
        help="入力するとこちらが優先されます。一覧にない新しいモデルを試すときに使います",
    ).strip()
    if custom_model:
        model = custom_model.removeprefix("models/")
    temperature = st.slider(
        "創造性（temperature）",
        min_value=0.0,
        max_value=2.0,
        value=tool.default_temperature,
        step=0.1,
        key=f"temp_{tool.id}",
        help="低いほど正確・安定、高いほど多様で創造的な出力になります",
    )

    st.divider()
    st.subheader("🕘 履歴")
    if not st.session_state.history:
        st.caption("まだ履歴はありません")
    for i, item in enumerate(st.session_state.history):
        preview = item["output"].strip().replace("\n", " ")[:40]
        st.button(
            f"{item['time']} {item['tool_name']}\n\n{preview}…",
            key=f"hist_{i}",
            on_click=load_history,
            args=(i,),
            use_container_width=True,
        )
    if st.session_state.history and st.button("履歴をクリア", type="tertiary"):
        st.session_state.history = []
        st.rerun()


# ---------------------------------------------------------------------------
# 入力フォーム
# ---------------------------------------------------------------------------
def render_field(f: Field, tool_id: str) -> Any:
    key = f"{tool_id}__{f.key}"
    label = f"{f.label} *" if f.required else f.label
    if f.kind == "textarea":
        return st.text_area(label, placeholder=f.placeholder, height=f.height, help=f.help, key=key)
    if f.kind == "select":
        index = f.options.index(f.default) if f.default in f.options else 0
        return st.selectbox(label, f.options, index=index, help=f.help, key=key)
    if f.kind == "slider":
        return st.slider(label, min_value=f.min_value, max_value=f.max_value,
                         value=f.default if f.default is not None else f.min_value,
                         step=f.step, help=f.help, key=key)
    return st.text_input(label, placeholder=f.placeholder, help=f.help, key=key)


def render_form(tool: Tool) -> dict[str, Any] | None:
    """フォームを描画し、送信されたら入力値を返す。"""
    with st.form(key=f"form_{tool.id}"):
        values: dict[str, Any] = {}
        half: list[Field] = []

        def flush_half() -> None:
            # 半幅フィールドを2列に並べる
            for row_start in range(0, len(half), 2):
                cols = st.columns(2)
                for col, f in zip(cols, half[row_start:row_start + 2]):
                    with col:
                        values[f.key] = render_field(f, tool.id)
            half.clear()

        for f in tool.fields:
            if f.full_width:
                flush_half()
                values[f.key] = render_field(f, tool.id)
            else:
                half.append(f)
        flush_half()

        submitted = st.form_submit_button("✨ 生成する", type="primary", use_container_width=True)

    if not submitted:
        return None

    missing = [f.label for f in tool.fields
               if f.required and not str(values.get(f.key, "")).strip()]
    if missing:
        st.warning(f"必須項目を入力してください: {', '.join(missing)}")
        return None
    return values


# ---------------------------------------------------------------------------
# 生成処理
# ---------------------------------------------------------------------------
def run_generation(tool: Tool, prompt: str) -> None:
    if not api_key:
        st.error("Gemini APIキーが設定されていません。サイドバーで入力するか、.env に設定してください。")
        return
    # ストリーミング表示用の一時領域。完了後に消して render_result で正式に表示する
    placeholder = st.empty()
    try:
        with placeholder.container(border=True):
            with st.spinner("生成中..."):
                output = st.write_stream(stream_generate(
                    api_key=api_key,
                    model=model,
                    prompt=prompt,
                    system_instruction=tool.system_instruction,
                    temperature=temperature,
                ))
    except Exception as e:  # noqa: BLE001 - APIエラーは種類を問わず画面に表示する
        placeholder.empty()
        st.error(explain_error(e))
        return

    placeholder.empty()
    if not isinstance(output, str) or not output.strip():
        st.warning("出力が空でした。入力内容を変えて再度お試しください。")
        return
    save_result(tool, prompt, output)


def request_regenerate(tool_id: str) -> None:
    """「同じ条件で再生成」ボタンのコールバック。"""
    st.session_state.pending = st.session_state.results[tool_id]["prompt"]


def request_refine(tool_id: str) -> None:
    """「修正を依頼」ボタンのコールバック。"""
    instruction = st.session_state.get(f"refine_input_{tool_id}", "").strip()
    if not instruction:
        return
    result = st.session_state.results[tool_id]
    st.session_state.pending = build_refine_prompt(result["prompt"], result["output"], instruction)


def build_refine_prompt(prev_prompt: str, prev_output: str, instruction: str) -> str:
    return (
        "以前、次の依頼に対して文章を作成しました。\n\n"
        f"# 元の依頼\n{prev_prompt}\n\n"
        f"# 作成した文章\n{prev_output}\n\n"
        f"# 修正指示\n{instruction}\n\n"
        "修正指示を反映した文章を、全文で出力してください。"
    )


def render_result(tool: Tool) -> None:
    result = st.session_state.results.get(tool.id)
    if not result:
        return

    st.subheader("📄 生成結果")
    with st.container(border=True):
        st.markdown(result["output"])

    output = result["output"]
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.download_button(
            "⬇️ Markdownで保存",
            data=output,
            file_name=f"{tool.id}_{datetime.now():%Y%m%d_%H%M%S}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "⬇️ テキストで保存",
            data=output,
            file_name=f"{tool.id}_{datetime.now():%Y%m%d_%H%M%S}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with c3:
        st.button("🔁 同じ条件で再生成", use_container_width=True,
                  on_click=request_regenerate, args=(tool.id,))

    st.caption(f"文字数: {len(output):,} 文字")
    with st.expander("📋 コピー用（右上のアイコンでコピー）"):
        st.code(output, language="markdown", wrap_lines=True)

    with st.form(key=f"refine_{tool.id}", clear_on_submit=True):
        st.text_input(
            "🛠️ この結果を修正する",
            placeholder="例: もう少し短く / 結論を最初に / 具体例を追加して",
            key=f"refine_input_{tool.id}",
        )
        st.form_submit_button("修正を依頼", on_click=request_refine, args=(tool.id,))


# ---------------------------------------------------------------------------
# メイン画面
# ---------------------------------------------------------------------------
st.header(f"{tool.icon} {tool.name}")
st.caption(tool.description)

values = render_form(tool)
pending = st.session_state.pop("pending", None)
if values is not None:
    run_generation(tool, tool.build_prompt(values))
elif pending:
    run_generation(tool, pending)

render_result(tool)
