# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

個人用のAIライティングツール（Python + Streamlit + Gemini API）。DB・認証は持たない方針。履歴などの状態はすべて `st.session_state` に置くので、ブラウザを再読み込みすると消える。

## コマンド（Windows / 仮想環境は `.venv`）

```powershell
.venv\Scripts\python -m pip install -r requirements.txt   # 依存関係のインストール
.venv\Scripts\streamlit run app.py                        # 起動（http://localhost:8501）
```

テストスイートやリンターは用意していない。動作確認には Streamlit の `AppTest` を使う。

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py", default_timeout=150).run()
at.sidebar.radio[0].set_value("summary").run()   # ツール切替（値は Tool.id）
at.text_area[0].input("...")                     # ここで .run() を挟むと入力値が失われる
at.button[0].click().run()                       # フォーム送信
at.session_state.results["summary"]["output"]    # 生成結果
```

- `.env` の `GEMINI_API_KEY` があると実際にAPIを呼ぶ。キーなしの経路を試すときは `GEMINI_API_KEY=` で上書きして実行する。
- プロジェクト外に置いたスクリプトから読み込むときは `load_dotenv(<プロジェクトの .env の絶対パス>)` とする（引数なしの `load_dotenv()` は、スクリプトの場所から `.env` を探すため見つからない）。
- Windows のコンソールでは日本語が文字化けするので `PYTHONIOENCODING=utf-8` を付ける。

## アーキテクチャ

- **`tools.py`**：各ツールを宣言的に定義する場所。`Tool` は入力項目の定義（`fields: list[Field]`）、`build_prompt(values) -> str`、`system_instruction`、`default_temperature` を持つ。ツールの追加は `Tool` を定義して `TOOLS` に足すだけで、`app.py` 側の変更は要らない。`values` のキーは `Field.key`。
- **`app.py`**：`Field.kind`（text / textarea / select / slider）から入力フォームを自動生成する。`full_width=False` の項目は2列に並ぶ。ウィジェットのキー命名規則は `{tool_id}__{field_key}`、`temp_{tool_id}`、`refine_input_{tool_id}`。
- **`gemini_client.py`**：`google-genai` SDK を薄くラップしたもの（`stream_generate` でストリーミング生成、タイムアウト120秒）。`explain_error` は API エラーの文字列から 404 / 429 / 503 / タイムアウトを判別し、日本語の説明に変換する。

### 生成フロー（変更時に注意）

生成後に `st.rerun()` は**使わない**。AppTest ではフォーム送信の状態がリランに引き継がれ、生成を繰り返してしまったため。現在の流れは次のとおり。

1. 「再生成」「修正を依頼」ボタンは `on_click` コールバックの中で `st.session_state.pending` に送るプロンプトを入れる。
2. スクリプト本体で、フォームの送信値または `pending` を取り出し、`run_generation` を呼ぶ。
3. `run_generation` は `st.empty()` の中にストリーミング表示し、完了したら消してから `save_result` を呼ぶ。
4. 最後に `render_result` が `results[tool_id]` を表示する。

## Gemini モデルの注意点

- `models.list()` に載っていても使えないモデルがある（例：`gemini-2.5-flash` は一覧に出るが、新規ユーザーは 404）。
- デフォルトは `gemini-flash-lite-latest`。2026-10 時点の実測では、`gemini-3.8-flash` は遅く（約70秒）、`gemini-flash-latest` はタイムアウトし、`gemini-pro-latest` は無料枠では 429 だった。
- モデル一覧は `gemini_client.DEFAULT_MODELS` にある。環境変数 `GEMINI_MODEL` を設定すると、そのモデルが一覧の先頭に入る。サイドバーからモデル名を直接入力することもできる。
