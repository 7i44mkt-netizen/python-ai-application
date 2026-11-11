"""Gemini API との通信をまとめたモジュール。"""

from __future__ import annotations

import os
from collections.abc import Iterator

from google import genai
from google.genai import types

REQUEST_TIMEOUT_MS = 120_000

# "*-latest" は常に最新版を指すエイリアスなので、モデルの提供終了に強い
DEFAULT_MODELS = [
    "gemini-flash-lite-latest",  # 高速・安定（デフォルト）
    "gemini-3.8-flash",          # 高品質（混雑時は遅いことがある）
    "gemini-flash-latest",
    "gemini-pro-latest",  # 無料枠では使えない場合あり（429）
]


def explain_error(e: Exception) -> str:
    """API エラーを日本語のわかりやすい説明に変換する。"""
    msg = str(e)
    if "404" in msg or "NOT_FOUND" in msg:
        return ("指定したモデルは利用できません（提供終了または名前の誤り）。"
                "サイドバーで別のモデルを選んでください。\n\n" + msg)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return ("利用上限（クォータ）に達しました。少し時間をおくか、"
                "Flash 系など別のモデルを選んでください（Pro 系は無料枠で使えない場合があります）。\n\n" + msg)
    if "503" in msg or "UNAVAILABLE" in msg:
        return ("Gemini 側が一時的に混雑しています。少し待ってから再度お試しいただくか、"
                "別のモデルを選んでください。\n\n" + msg)
    if "timed out" in msg.lower() or "timeout" in msg.lower():
        return ("Gemini からの応答がタイムアウトしました。混雑している可能性があります。"
                "再度お試しいただくか、別のモデルを選んでください。")
    if "API_KEY_INVALID" in msg or "API key not valid" in msg:
        return "APIキーが正しくありません。.env の GEMINI_API_KEY を確認してください。"
    return f"生成中にエラーが発生しました: {msg}"


def get_api_key() -> str | None:
    """環境変数 → Streamlit secrets の順で API キーを探す。"""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


def available_models() -> list[str]:
    """選択肢に出すモデル一覧。GEMINI_MODEL が設定されていれば先頭に置く。"""
    models = list(DEFAULT_MODELS)
    env_model = os.getenv("GEMINI_MODEL")
    if env_model:
        if env_model in models:
            models.remove(env_model)
        models.insert(0, env_model)
    return models


def stream_generate(
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.7,
) -> Iterator[str]:
    """Gemini からテキストをストリーミングで受け取り、チャンクごとに yield する。"""
    # 応答が返らないまま固まらないよう、タイムアウト（ミリ秒）を設定
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
    )
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=prompt,
        config=config,
    ):
        if chunk.text:
            yield chunk.text
