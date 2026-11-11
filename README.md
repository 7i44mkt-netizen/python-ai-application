# ✍️ AIライティングツール（個人用）

Python + Streamlit + Gemini API で作った、ライティング系AI機能をまとめたツールです。

## 機能

| ツール | 内容 |
|---|---|
| 📝 ブログ記事作成 | テーマ・キーワード・トーン・文字数から記事を丸ごと執筆 |
| 🗂️ ブログ構成案 | タイトル案、見出し構成、要点、差別化アイデア |
| ✉️ メール返信 | 受信メール＋伝えたいことから返信案を複数作成 |
| 📨 メール作成 | 依頼・お礼・お詫びなどの新規メール |
| 📋 文章要約 | 箇条書き / 3行 / TL;DR / 議事録風などで要約 |
| ✅ 校正・推敲 | 修正版と「修正前→修正後：理由」の一覧 |
| 🔄 リライト・言い換え | 短く・詳しく・やさしく・敬語化など |
| 🌐 翻訳 | 多言語対応、文体指定、訳のポイント解説 |
| 📱 SNS投稿作成 | X / Instagram / Threads / LinkedIn / Facebook 向け |
| 💡 タイトル・キャッチコピー | 記事タイトル、件名、商品名などを大量提案 |
| 🧠 アイデア出し | ブレスト＋おすすめ3選 |
| ✨ フリー入力 | 自由な指示で文章作成 |

共通機能:
- ストリーミング出力
- 結果への追加修正指示（「もっと短く」など）／同じ条件で再生成
- Markdown・テキストでの保存、コピー用表示、文字数カウント
- 生成履歴（セッション中、最大30件）
- モデル選択、創造性（temperature）の調整

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # .env に GEMINI_API_KEY を記入
streamlit run app.py
```

APIキーは [Google AI Studio](https://aistudio.google.com/apikey) で取得できます。
`.env` を用意しない場合は、サイドバーから直接入力することもできます。

## ツールの追加方法

`tools.py` に `Tool` を1つ定義して `TOOLS` リストに追加するだけです。
入力フォームは `fields` の定義から自動で作られます。

```python
MY_TOOL = Tool(
    id="my_tool",
    name="ツール名",
    icon="🆕",
    description="説明文",
    fields=[Field("text", "入力欄", kind="textarea", required=True, full_width=True)],
    build_prompt=lambda v: f"次の文章を〇〇してください。\n\n{v['text']}",
    system_instruction=BASE_SYSTEM,
)
```

## ファイル構成

```
app.py            Streamlit の画面（サイドバー、フォーム、結果表示、履歴）
tools.py          各AIツールの定義（入力項目とプロンプト）
gemini_client.py  Gemini API 呼び出し（google-genai SDK、ストリーミング）
```
