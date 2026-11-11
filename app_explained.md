# Streamlitアプリ `app.py` を上から順に読む：AIライティングツールの仕組み

## はじめに：まず「Streamlitの癖」を知る

`app.py` を読む前に、Streamlitの一番大事なルールを押さえておきます。

> **ボタンを押す、文字を入れるなどの操作があるたびに、スクリプト全体が上から下まで実行し直される**

普通のGUIアプリでは「ボタンが押されたらこの関数を呼ぶ」と書きます。Streamlitでは、操作のたびに `app.py` 全体が最初から動き直します（これを「リラン」と呼びます）。`st.button(...)` は「押された直後の1回だけ `True` を返す関数」です。

ここから2つのことが言えます。

- 普通の変数はリランのたびに初期化されて消える。残したい値は **`st.session_state`** に入れる。
- コードは「イベントの処理」というより「**今の状態から画面を毎回描き直す手順**」として読むと分かりやすい。

この前提で、上から順に見ていきます。

---

## 1. 準備：読み込みと初期設定（1〜25行目）

```python
from gemini_client import available_models, explain_error, get_api_key, stream_generate
from tools import TOOLS, TOOLS_BY_ID, Field, Tool

load_dotenv()
st.set_page_config(page_title="AIライティングツール", page_icon="✍️", layout="wide")
MAX_HISTORY = 30
```

- `gemini_client`：Gemini APIとやり取りする部分
- `tools`：「ブログ記事作成」「メール返信」などのツールの定義（後で詳しく説明します）
- `load_dotenv()`：`.env` に書いた `GEMINI_API_KEY` を環境変数として読み込む

続いて、セッション状態を初期化します。

```python
st.session_state.setdefault("tool_id", TOOLS[0].id)
st.session_state.setdefault("results", {})   # tool_id -> {"prompt", "output"}
st.session_state.setdefault("history", [])   # 新しい順
```

`setdefault` は「まだ値がなければ入れる」という意味です。リランのたびにこの行は実行されますが、2回目以降は既に値があるので何も起きません。ここで初期化を1回だけにしているわけです。

| キー | 中身 |
|---|---|
| `tool_id` | いま選んでいるツール（例：`"blog"`） |
| `results` | ツールごとの最新の生成結果 |
| `history` | 生成履歴（新しいものが先頭、最大30件） |

このアプリはDBを持たないので、ブラウザを再読み込みすると全部消えます。

---

## 2. 結果を保存する2つの関数（28〜44行目）

```python
def save_result(tool, prompt, output):
    st.session_state.results[tool.id] = {"prompt": prompt, "output": output}
    st.session_state.history.insert(0, {...})
    del st.session_state.history[MAX_HISTORY:]
```

生成が終わったら、次の2か所に保存します。

1. `results[tool.id]`：そのツールの「今の結果」として上書きする
2. `history` の**先頭**に追加し、31件目以降を削除する（`del リスト[30:]` で古い分を切り捨てる定番の書き方です）

`load_history` はその逆で、履歴の1件を `results` に戻し、ツールの選択も切り替えます。履歴ボタンの `on_click` で呼ばれます。

---

## 3. サイドバー（50〜105行目）

`with st.sidebar:` の中に書いた部品はすべてサイドバーに表示されます。

### ツール選択

```python
st.radio("ツールを選択", options=[t.id for t in TOOLS],
         format_func=lambda tid: f"{TOOLS_BY_ID[tid].icon} {TOOLS_BY_ID[tid].name}",
         key="tool_id")
tool = TOOLS_BY_ID[st.session_state.tool_id]
```

ここで使っている書き方は2つあります。

- **値はID、表示は名前**：`options` には `"blog"` のようなIDを渡し、画面には `format_func` で「📝 ブログ記事作成」と表示します。
- **`key="tool_id"`**：ウィジェットに `key` を付けると、その値が自動的に `st.session_state.tool_id` と結び付きます。`load_history` が `tool_id` を書き換えるとラジオボタンの選択も変わるのは、このためです。

### 設定（APIキー・モデル・temperature）

- APIキーが `.env` にあれば入力欄を出しません。なければパスワード欄を出します。
- モデルは一覧から選べます。「直接入力」欄に何か入れると、そちらが優先されます（`models/` という接頭辞は取り除きます）。
- temperatureのスライダーは `key=f"temp_{tool.id}"` のように**ツールごとに別のキー**を持ちます。要約は0.3、アイデア出しは1.0のように、ツールごとの初期値と調整した値をそれぞれ覚えておけます。

### 履歴

```python
for i, item in enumerate(st.session_state.history):
    preview = item["output"].strip().replace("\n", " ")[:40]
    st.button(f"{item['time']} {item['tool_name']}\n\n{preview}…",
              key=f"hist_{i}", on_click=load_history, args=(i,), ...)
```

履歴の1件ごとにボタンを作り、出力の最初の40文字をプレビューとして表示します。押すと `load_history(i)` が呼ばれます。

---

## 4. 入力フォームの自動生成（111〜159行目）

このアプリの設計で一番の特徴がここです。`app.py` には「ブログ用の入力欄」「メール用の入力欄」のようなコードがありません。代わりに `tools.py` に次のような**データ**を書いておきます。

```python
Field("topic", "テーマ", required=True, full_width=True),
Field("tone", "トーン", kind="select", options=TONES, default="フレンドリー"),
Field("length", "目安の文字数", kind="slider", min_value=500, max_value=6000, ...),
```

### `render_field`：1項目を描く

`Field.kind` に応じて使う部品を選びます。

| kind | Streamlitの部品 |
|---|---|
| `textarea` | `st.text_area` |
| `select` | `st.selectbox` |
| `slider` | `st.slider` |
| それ以外（`text`） | `st.text_input` |

キーは `f"{tool_id}__{f.key}"`（例：`blog__topic`）です。ツールを切り替えて戻ってきても、入力内容が残ります。必須項目にはラベルに「*」を付けます。

### `render_form`：2列レイアウト

```python
for f in tool.fields:
    if f.full_width:
        flush_half()          # たまっている半幅項目を先に描く
        values[f.key] = render_field(f, tool.id)
    else:
        half.append(f)        # 半幅項目は一旦ためる
flush_half()
```

`full_width=False` の項目は `half` にためておき、2つずつ `st.columns(2)` に並べます。横幅いっぱいの項目が来たら、先にたまっている分を描いてから描きます。こうすると定義の順番を崩さずに2列表示ができます。

### `st.form` を使う理由

`with st.form(...)` の中の入力欄は、**送信ボタンを押すまでリランを起こしません**。フォームを使わないと、1文字打つたびにスクリプト全体が動き直します。

送信されたら必須チェックをして、問題なければ `{"topic": "...", "tone": "..."}` という辞書を返します。送信されていなければ `None` を返します。

---

## 5. 生成処理（165〜214行目）

### `run_generation`：ストリーミング表示

```python
placeholder = st.empty()
with placeholder.container(border=True):
    with st.spinner("生成中..."):
        output = st.write_stream(stream_generate(...))
...
placeholder.empty()
save_result(tool, prompt, output)
```

1. `st.empty()` で一時的な表示枠を用意する
2. `st.write_stream` に、Geminiから少しずつ届く文字を流す。ChatGPTのように文字が順に表示され、最後に全文が返ってくる
3. 終わったら一時枠を消して保存する（正式な表示は、この後の `render_result` が行う）

エラーは `explain_error` で「429＝利用上限です」のような日本語に変換して表示します。出力が空のときは保存しません。

### 再生成と修正依頼は「予約」するだけ

```python
def request_regenerate(tool_id):
    st.session_state.pending = st.session_state.results[tool_id]["prompt"]

def request_refine(tool_id):
    instruction = st.session_state.get(f"refine_input_{tool_id}", "").strip()
    ...
    st.session_state.pending = build_refine_prompt(...)
```

この2つのコールバックは**生成を実行しません**。`pending` に「次に送るプロンプト」を入れるだけです。

修正依頼のプロンプトは「元の依頼」「作成した文章」「修正指示」をまとめて送ります。Geminiに会話の記憶はないので、前回の内容を毎回すべて渡しているわけです。

---

## 6. 結果表示（217〜258行目）

`render_result` は `results[tool.id]` があれば、次のものを並べます。

- Markdownとして整形した結果
- `.md` と `.txt` のダウンロードボタン（ファイル名は `blog_20261104_153000.md` のような形式）
- 「🔁 同じ条件で再生成」ボタン
- 文字数（`f"{len(output):,}"` で「2,345」のように3桁ごとにカンマを入れる）
- コピー用のコードブロック（`st.code` には右上にコピーボタンが付く）
- 修正依頼のフォーム（`clear_on_submit=True` で送信後に入力欄を空にする）

---

## 7. メイン部分：ここで全体がつながる（264〜274行目）

```python
st.header(f"{tool.icon} {tool.name}")
st.caption(tool.description)

values = render_form(tool)
pending = st.session_state.pop("pending", None)
if values is not None:
    run_generation(tool, tool.build_prompt(values))
elif pending:
    run_generation(tool, pending)

render_result(tool)
```

わずか10行ですが、生成の流れはすべてここに集まっています。

### シナリオA：「✨ 生成する」を押した

1. リランが始まり、`render_form` が入力値の辞書を返す
2. `tool.build_prompt(values)` でプロンプト文を作り、生成する
3. `render_result` が新しい結果を表示する

### シナリオB：「🔁 再生成」または「修正を依頼」を押した

1. **リランより前に** `on_click` のコールバックが動き、`pending` にプロンプトが入る
2. リランが始まり、`pop("pending")` で取り出す（`pop` なので取り出すと同時に消える。次のリランで同じ生成が繰り返されることはない）
3. 生成して表示する

### なぜ `st.rerun()` を使わないのか

「生成したら `st.rerun()` で画面を更新する」という書き方もよく見かけます。ただ、`CLAUDE.md` によると、テスト（AppTest）ではフォーム送信の状態がリラン後にも残り、**生成が繰り返される**問題が起きました。そこで次の順番にしています。

> 予約（コールバック）→ 取り出して生成 → 同じ実行の中で表示

`run_generation` を `render_result` より**前**に書いているので、生成した結果がその実行の中ですぐ表示されます。

---

## 全体の流れ（図）

```
ユーザーの操作
   │
   ├─ on_click コールバック（あれば先に実行）
   │     └─ pending に予約 / 履歴を results に復元
   ▼
app.py を上から実行
   ├─ session_state の初期化（初回だけ）
   ├─ サイドバー描画 → tool, model, temperature が決まる
   ├─ フォーム描画 → 送信されていれば values
   ├─ values か pending があれば run_generation → save_result
   └─ render_result で results[tool.id] を表示
```

---

## まとめ

- **Streamlitは毎回全体を再実行する**。状態は `st.session_state` に置き、ウィジェットの `key` で結び付ける。
- **ツールはデータとして定義する**。`tools.py` に `Tool` を1つ足すだけで、フォームも含めて画面ができる（`app.py` は変更しなくてよい）。
- **生成の流れは「予約 → 取り出して生成 → 表示」**。`st.rerun()` を使わずに二重生成を防いでいる。
- **見た目の工夫**：フォームでリランを抑え、`st.empty()` でストリーミング表示し、ツールごとのキーで入力値とtemperatureを別々に覚える。

最初は `tools.py` の `FREE` ツール（入力欄が1つだけの一番単純なもの）を見ながら、`app.py` のメイン部分（264〜274行目）を追ってみてください。全体の流れがつかみやすいです。
