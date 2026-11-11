"""AIライティングツールの定義。

新しいツールを追加するときは、Tool を1つ作って TOOLS に追加するだけでOK。
画面の入力フォームは fields の定義から自動生成される。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

FieldKind = Literal["text", "textarea", "select", "slider"]


@dataclass
class Field:
    key: str
    label: str
    kind: FieldKind = "text"
    placeholder: str = ""
    options: list[str] = field(default_factory=list)
    default: Any = None
    required: bool = False
    help: str | None = None
    height: int = 150
    min_value: int = 0
    max_value: int = 100
    step: int = 1
    full_width: bool = False  # 2カラムレイアウトで横幅いっぱいに表示するか


@dataclass
class Tool:
    id: str
    name: str
    icon: str
    description: str
    fields: list[Field]
    build_prompt: Callable[[dict[str, Any]], str]
    system_instruction: str
    default_temperature: float = 0.7


def _opt(label: str, value: Any) -> str:
    """値が空でなければ「- ラベル: 値」の行を返す。"""
    if value is None or value == "":
        return ""
    return f"- {label}: {value}\n"


BASE_SYSTEM = (
    "あなたは日本語のプロのライター兼編集者です。"
    "読みやすく自然な日本語で、ユーザーの目的に沿った文章を作成してください。"
    "前置きや「承知しました」などの返事は書かず、成果物そのものを出力してください。"
)

TONES = ["丁寧", "カジュアル", "フォーマル", "フレンドリー", "専門的", "熱意のある", "簡潔"]


# ---------------------------------------------------------------------------
# 1. ブログ記事作成
# ---------------------------------------------------------------------------
def _blog_prompt(v: dict[str, Any]) -> str:
    return (
        "以下の条件でブログ記事を執筆してください。\n\n"
        f"- テーマ: {v['topic']}\n"
        + _opt("想定読者", v.get("audience"))
        + _opt("含めたいキーワード", v.get("keywords"))
        + f"- トーン: {v['tone']}\n"
        f"- 目安の文字数: 約{v['length']}文字\n"
        + _opt("補足・要望", v.get("notes"))
        + "\n# 出力形式\n"
        "- Markdown形式\n"
        "- 1行目に「# 」で魅力的なタイトル\n"
        "- 導入 → 見出し(##)ごとの本文 → まとめ の構成\n"
        "- 必要に応じて箇条書きや太字を使って読みやすく\n"
    )


BLOG = Tool(
    id="blog",
    name="ブログ記事作成",
    icon="📝",
    description="テーマとキーワードから、見出し付きのブログ記事を丸ごと執筆します。",
    fields=[
        Field("topic", "テーマ", placeholder="例: 初心者向けのPython学習ロードマップ", required=True, full_width=True),
        Field("audience", "想定読者", placeholder="例: プログラミング未経験の社会人"),
        Field("keywords", "キーワード（カンマ区切り）", placeholder="例: Python, 独学, おすすめ教材"),
        Field("tone", "トーン", kind="select", options=TONES, default="フレンドリー"),
        Field("length", "目安の文字数", kind="slider", min_value=500, max_value=6000, step=500, default=2000),
        Field("notes", "補足・要望（任意）", kind="textarea", height=100,
              placeholder="例: 自分の体験談を交えた雰囲気で。最後に行動を促す一文を入れて。", full_width=True),
    ],
    build_prompt=_blog_prompt,
    system_instruction=BASE_SYSTEM + "SEOを意識しつつ、読者にとって価値のある具体的な内容を書いてください。",
    default_temperature=0.8,
)


# ---------------------------------------------------------------------------
# 2. ブログ構成案
# ---------------------------------------------------------------------------
def _outline_prompt(v: dict[str, Any]) -> str:
    return (
        "以下のテーマで、ブログ記事の構成案を作ってください。\n\n"
        f"- テーマ: {v['topic']}\n"
        + _opt("想定読者", v.get("audience"))
        + _opt("狙うキーワード", v.get("keywords"))
        + f"\n# 出力内容\n"
        f"1. タイトル案を{v['count']}つ\n"
        "2. 読者の検索意図・悩みの整理\n"
        "3. 見出し構成（H2/H3）と各見出しで書くべき要点\n"
        "4. 差別化のためのアイデア\n"
    )


OUTLINE = Tool(
    id="outline",
    name="ブログ構成案",
    icon="🗂️",
    description="記事を書く前の、タイトル案・見出し構成・要点をまとめます。",
    fields=[
        Field("topic", "テーマ", placeholder="例: 在宅ワークの集中力を上げる方法", required=True, full_width=True),
        Field("audience", "想定読者", placeholder="例: 在宅勤務を始めたばかりの会社員"),
        Field("keywords", "狙うキーワード", placeholder="例: 在宅ワーク 集中できない"),
        Field("count", "タイトル案の数", kind="slider", min_value=3, max_value=10, default=5),
    ],
    build_prompt=_outline_prompt,
    system_instruction=BASE_SYSTEM + "あなたはSEOに詳しいコンテンツディレクターでもあります。",
)


# ---------------------------------------------------------------------------
# 3. メール返信
# ---------------------------------------------------------------------------
def _email_reply_prompt(v: dict[str, Any]) -> str:
    return (
        "以下の受信メールに対する返信文を作成してください。\n\n"
        f"# 受信メール\n{v['received']}\n\n"
        f"# 返信で伝えたいこと\n{v['intent']}\n\n"
        "# 条件\n"
        f"- 相手との関係: {v['relation']}\n"
        f"- トーン: {v['tone']}\n"
        + _opt("差出人（自分）の名前", v.get("my_name"))
        + f"- 返信案の数: {v['variations']}パターン\n"
        "\n# 出力形式\n"
        "- 各パターンに「## 返信案1」のような見出しを付ける\n"
        "- 件名（Re: を含む）と本文を記載\n"
    )


EMAIL_REPLY = Tool(
    id="email_reply",
    name="メール返信",
    icon="✉️",
    description="受信したメールと伝えたいことから、適切な返信文を考えます。",
    fields=[
        Field("received", "受信したメール", kind="textarea", height=200, required=True, full_width=True,
              placeholder="返信したいメールの本文を貼り付けてください"),
        Field("intent", "返信で伝えたいこと", kind="textarea", height=100, required=True, full_width=True,
              placeholder="例: 日程は了承。ただし開始時間を30分遅らせてほしい"),
        Field("relation", "相手との関係", kind="select",
              options=["取引先・顧客", "社内の上司", "社内の同僚", "部下・後輩", "友人・知人", "初対面"], default="取引先・顧客"),
        Field("tone", "トーン", kind="select", options=TONES, default="丁寧"),
        Field("my_name", "自分の名前（任意）", placeholder="例: 山田"),
        Field("variations", "返信案の数", kind="slider", min_value=1, max_value=3, default=2),
    ],
    build_prompt=_email_reply_prompt,
    system_instruction=BASE_SYSTEM + "あなたはビジネスメールのマナーに精通しています。",
    default_temperature=0.6,
)


# ---------------------------------------------------------------------------
# 4. メール新規作成
# ---------------------------------------------------------------------------
def _email_new_prompt(v: dict[str, Any]) -> str:
    return (
        "以下の内容でメールを作成してください。\n\n"
        f"- 目的: {v['purpose']}\n"
        f"- 宛先: {v['recipient']}\n"
        f"- 伝えたい要点:\n{v['points']}\n"
        f"- トーン: {v['tone']}\n"
        + _opt("差出人（自分）の名前", v.get("my_name"))
        + "\n件名と本文を出力してください。"
    )


EMAIL_NEW = Tool(
    id="email_new",
    name="メール作成",
    icon="📨",
    description="依頼・お礼・お詫び・案内など、新規メールを作成します。",
    fields=[
        Field("purpose", "目的", kind="select",
              options=["依頼", "お礼", "お詫び", "案内・お知らせ", "日程調整", "問い合わせ", "催促", "断り", "挨拶", "その他"],
              default="依頼"),
        Field("recipient", "宛先", placeholder="例: 取引先の担当者 佐藤様", required=True),
        Field("points", "伝えたい要点", kind="textarea", height=150, required=True, full_width=True,
              placeholder="例:\n- 見積書を今週金曜までに送ってほしい\n- 数量は前回と同じ"),
        Field("tone", "トーン", kind="select", options=TONES, default="丁寧"),
        Field("my_name", "自分の名前（任意）", placeholder="例: 山田"),
    ],
    build_prompt=_email_new_prompt,
    system_instruction=BASE_SYSTEM + "あなたはビジネスメールのマナーに精通しています。",
    default_temperature=0.6,
)


# ---------------------------------------------------------------------------
# 5. 要約
# ---------------------------------------------------------------------------
SUMMARY_STYLES = {
    "箇条書き": "重要なポイントを箇条書きで",
    "短い文章": "簡潔な文章（段落）で",
    "3行まとめ": "ちょうど3行で",
    "TL;DR + 詳細": "冒頭に1文のTL;DR、その後に箇条書きの詳細で",
    "議事録風": "「概要／決定事項／ToDo（担当・期限があれば）／保留事項」の見出しで整理して",
}


def _summary_prompt(v: dict[str, Any]) -> str:
    return (
        f"以下の文章を{SUMMARY_STYLES[v['style']]}要約してください。\n"
        f"- 要約の長さ: {v['length']}\n"
        + _opt("特に注目してほしい観点", v.get("focus"))
        + "- 原文にない情報は加えないこと\n\n"
        f"# 原文\n{v['text']}"
    )


SUMMARY = Tool(
    id="summary",
    name="文章要約",
    icon="📋",
    description="長い文章・記事・会議メモなどを、指定の形式で要約します。",
    fields=[
        Field("text", "要約したい文章", kind="textarea", height=300, required=True, full_width=True,
              placeholder="要約したい文章を貼り付けてください"),
        Field("style", "要約の形式", kind="select", options=list(SUMMARY_STYLES.keys()), default="箇条書き"),
        Field("length", "長さ", kind="select", options=["とても短く", "短め", "標準", "詳しめ"], default="標準"),
        Field("focus", "注目する観点（任意）", placeholder="例: コストに関する部分", full_width=True),
    ],
    build_prompt=_summary_prompt,
    system_instruction=BASE_SYSTEM + "あなたは情報整理と要約の専門家です。正確さを最優先してください。",
    default_temperature=0.3,
)


# ---------------------------------------------------------------------------
# 6. 校正・推敲
# ---------------------------------------------------------------------------
def _proofread_prompt(v: dict[str, Any]) -> str:
    return (
        f"以下の文章を校正・推敲してください。修正レベルは「{v['level']}」です。\n\n"
        "# 出力形式\n"
        "## 修正後の文章\n（修正した全文）\n\n"
        "## 主な修正点\n（「修正前 → 修正後：理由」の形式で箇条書き）\n\n"
        f"# 対象の文章\n{v['text']}"
    )


PROOFREAD = Tool(
    id="proofread",
    name="校正・推敲",
    icon="✅",
    description="誤字脱字・文法・表現をチェックし、修正版と修正理由を出します。",
    fields=[
        Field("text", "チェックしたい文章", kind="textarea", height=300, required=True, full_width=True),
        Field("level", "修正レベル", kind="select",
              options=["誤字脱字のみ", "軽め（意味は変えない）", "しっかり（読みやすさ重視で書き換え可）"],
              default="軽め（意味は変えない）"),
    ],
    build_prompt=_proofread_prompt,
    system_instruction=BASE_SYSTEM + "あなたは経験豊富な校正者です。",
    default_temperature=0.2,
)


# ---------------------------------------------------------------------------
# 7. リライト・トーン変換
# ---------------------------------------------------------------------------
def _rewrite_prompt(v: dict[str, Any]) -> str:
    return (
        "以下の文章をリライトしてください。\n\n"
        f"- 目的: {v['mode']}\n"
        f"- トーン: {v['tone']}\n"
        + _opt("その他の要望", v.get("notes"))
        + "- 元の意味・主張は保つこと\n\n"
        f"# 元の文章\n{v['text']}"
    )


REWRITE = Tool(
    id="rewrite",
    name="リライト・言い換え",
    icon="🔄",
    description="文章のトーン変更、わかりやすく言い換え、文字数の調整などを行います。",
    fields=[
        Field("text", "元の文章", kind="textarea", height=250, required=True, full_width=True),
        Field("mode", "リライトの目的", kind="select",
              options=["読みやすく整える", "もっと短く簡潔に", "もっと詳しく膨らませる",
                       "小学生にもわかるように", "敬語に直す", "くだけた口語にする", "オリジナリティを出す（言い換え）"],
              default="読みやすく整える"),
        Field("tone", "トーン", kind="select", options=TONES, default="丁寧"),
        Field("notes", "その他の要望（任意）", placeholder="例: 300文字以内で", full_width=True),
    ],
    build_prompt=_rewrite_prompt,
    system_instruction=BASE_SYSTEM,
)


# ---------------------------------------------------------------------------
# 8. 翻訳
# ---------------------------------------------------------------------------
def _translate_prompt(v: dict[str, Any]) -> str:
    return (
        f"以下の文章を{v['target']}に翻訳してください。\n"
        f"- 文体: {v['style']}\n"
        + ("- 翻訳文の後に「## 補足」として、訳し方のポイントや注意すべき表現を簡潔に説明してください\n"
           if v["explain"] == "あり" else "- 翻訳文のみを出力してください\n")
        + f"\n# 原文\n{v['text']}"
    )


TRANSLATE = Tool(
    id="translate",
    name="翻訳",
    icon="🌐",
    description="自然な文体での翻訳。ビジネス・カジュアルなど文体も指定できます。",
    fields=[
        Field("text", "翻訳したい文章", kind="textarea", height=250, required=True, full_width=True),
        Field("target", "翻訳先の言語", kind="select",
              options=["英語", "日本語", "中国語（簡体字）", "中国語（繁体字）", "韓国語", "スペイン語", "フランス語", "ドイツ語"],
              default="英語"),
        Field("style", "文体", kind="select", options=["自然", "ビジネス", "カジュアル", "直訳寄り"], default="自然"),
        Field("explain", "訳のポイント解説", kind="select", options=["なし", "あり"], default="なし"),
    ],
    build_prompt=_translate_prompt,
    system_instruction="あなたはプロの翻訳者です。原文のニュアンスを保ちつつ、翻訳先の言語として自然な文章にしてください。前置きは不要です。",
    default_temperature=0.3,
)


# ---------------------------------------------------------------------------
# 9. SNS投稿作成
# ---------------------------------------------------------------------------
SNS_RULES = {
    "X (Twitter)": "1投稿あたり全角140文字以内。インパクトのある書き出し。ハッシュタグは1〜2個",
    "Instagram": "共感を呼ぶキャプション。改行と絵文字を適度に使い、末尾にハッシュタグを10個程度",
    "Threads": "会話的でカジュアル。500文字以内",
    "LinkedIn": "プロフェッショナルなトーン。学びや気づきを共有する構成。ハッシュタグは3個程度",
    "Facebook": "親しみやすく、ストーリー性のある文章",
}


def _sns_prompt(v: dict[str, Any]) -> str:
    return (
        f"{v['platform']}用の投稿文を{v['count']}パターン作成してください。\n\n"
        f"- 内容: {v['content']}\n"
        f"- 目的: {v['goal']}\n"
        f"- プラットフォームのルール: {SNS_RULES[v['platform']]}\n"
        "\n各パターンに「## 案1」のような見出しを付けてください。"
    )


SNS = Tool(
    id="sns",
    name="SNS投稿作成",
    icon="📱",
    description="X・Instagram などプラットフォームに合わせた投稿文を作ります。",
    fields=[
        Field("content", "投稿したい内容", kind="textarea", height=150, required=True, full_width=True,
              placeholder="例: 新しいブログ記事「Python独学ロードマップ」を公開した"),
        Field("platform", "プラットフォーム", kind="select", options=list(SNS_RULES.keys()), default="X (Twitter)"),
        Field("goal", "目的", kind="select",
              options=["告知・宣伝", "共感・エンゲージメント", "情報共有", "日常・雑談", "ブログへの誘導"], default="告知・宣伝"),
        Field("count", "パターン数", kind="slider", min_value=1, max_value=5, default=3),
    ],
    build_prompt=_sns_prompt,
    system_instruction=BASE_SYSTEM + "あなたはSNSマーケティングに詳しいコピーライターです。",
    default_temperature=0.9,
)


# ---------------------------------------------------------------------------
# 10. タイトル・キャッチコピー
# ---------------------------------------------------------------------------
def _copy_prompt(v: dict[str, Any]) -> str:
    return (
        f"以下の対象について、{v['kind']}を{v['count']}個考えてください。\n\n"
        f"- 対象: {v['subject']}\n"
        + _opt("ターゲット", v.get("target"))
        + f"- 方向性: {v['direction']}\n"
        "\n番号付きリストで出力し、それぞれに一言で狙いを添えてください。"
    )


COPY = Tool(
    id="copy",
    name="タイトル・キャッチコピー",
    icon="💡",
    description="記事タイトル、商品キャッチコピー、メール件名などを大量に提案します。",
    fields=[
        Field("subject", "対象（内容・商品・記事の概要）", kind="textarea", height=120, required=True, full_width=True),
        Field("kind", "種類", kind="select",
              options=["ブログ記事タイトル", "キャッチコピー", "メール件名", "YouTube動画タイトル", "商品名・サービス名", "見出し"],
              default="ブログ記事タイトル"),
        Field("target", "ターゲット（任意）", placeholder="例: 20代の女性"),
        Field("direction", "方向性", kind="select",
              options=["バランスよく", "興味を引く・クリックされやすい", "信頼感・誠実", "ユーモア", "短くシンプル", "数字を使う"],
              default="バランスよく"),
        Field("count", "案の数", kind="slider", min_value=3, max_value=20, default=10),
    ],
    build_prompt=_copy_prompt,
    system_instruction=BASE_SYSTEM + "あなたは実績のあるコピーライターです。",
    default_temperature=1.0,
)


# ---------------------------------------------------------------------------
# 11. アイデア出し
# ---------------------------------------------------------------------------
def _idea_prompt(v: dict[str, Any]) -> str:
    return (
        f"以下のテーマについて、アイデアを{v['count']}個出してください。\n\n"
        f"- テーマ: {v['theme']}\n"
        + _opt("前提・制約", v.get("constraints"))
        + f"- 発想の幅: {v['mode']}\n"
        "\n各アイデアは「**タイトル**：説明（1〜2文）」の形式で番号付きリストにしてください。"
        "最後に「## おすすめ」として特に良いものを3つ選び、理由を添えてください。"
    )


IDEA = Tool(
    id="idea",
    name="アイデア出し",
    icon="🧠",
    description="ブログネタ、企画、プレゼントなど、ブレインストーミングの相棒になります。",
    fields=[
        Field("theme", "テーマ", placeholder="例: 来月のブログで書くネタ", required=True, full_width=True),
        Field("constraints", "前提・制約（任意）", kind="textarea", height=100, full_width=True,
              placeholder="例: 技術ブログ。初心者向け。1記事で完結する内容"),
        Field("mode", "発想の幅", kind="select", options=["現実的・すぐ使える", "バランス", "斬新・ユニーク"], default="バランス"),
        Field("count", "アイデアの数", kind="slider", min_value=5, max_value=30, step=5, default=10),
    ],
    build_prompt=_idea_prompt,
    system_instruction=BASE_SYSTEM + "あなたは発想力豊かな企画者です。",
    default_temperature=1.0,
)


# ---------------------------------------------------------------------------
# 12. フリープロンプト
# ---------------------------------------------------------------------------
FREE = Tool(
    id="free",
    name="フリー入力",
    icon="✨",
    description="上記に当てはまらない文章作成を、自由な指示で依頼できます。",
    fields=[
        Field("prompt", "指示", kind="textarea", height=250, required=True, full_width=True,
              placeholder="例: 退職する同僚への寄せ書きメッセージを3パターン考えて"),
    ],
    build_prompt=lambda v: v["prompt"],
    system_instruction=BASE_SYSTEM,
)


TOOLS: list[Tool] = [
    BLOG, OUTLINE, EMAIL_REPLY, EMAIL_NEW, SUMMARY, PROOFREAD,
    REWRITE, TRANSLATE, SNS, COPY, IDEA, FREE,
]
TOOLS_BY_ID: dict[str, Tool] = {t.id: t for t in TOOLS}
