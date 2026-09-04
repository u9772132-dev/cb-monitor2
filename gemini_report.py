from __future__ import annotations
import os
import pandas as pd
from google import genai


def _client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            key = None
    if not key:
        raise RuntimeError("找不到 GEMINI_API_KEY，請在 Streamlit Secrets 或環境變數設定。")
    return genai.Client(api_key=key)


def generate_report(neg: pd.DataFrame, cheap: pd.DataFrame, asof: str):
    def compact(df):
        cols = [c for c in ["CB代號", "CB名稱", "標的股票代號", "CB價格", "標的股價", "轉換價格", "轉換價值", "溢價率", "成交量(張)"] if c in df.columns]
        return df[cols].head(20).to_string(index=False)
    prompt = f"""
你是台灣可轉債投資研究員。以下是 {asof} 收盤資料。
請用繁體中文寫一段 250~400 字的主管晨會/收盤日報摘要。
要求：1. 先講市場概況；2. 點出負溢價與低價低溢價代表性標的；3. 若有『剛突破轉換價』標的，特別指出；4. 不得捏造資料；5. 不直接下買進/賣出指令，以研究觀察語氣呈現。

負溢價：
{compact(neg)}

低價低溢價：
{compact(cheap)}
"""
    return _client().models.generate_content(model="gemini-2.5-flash", contents=prompt).text


def generate_company_summary(code: str, name: str):
    prompt = f"""
請用繁體中文簡單介紹台灣上市櫃公司「{name}」（股票代號 {code}）主要做什麼。
限制 80~120 字，重點說明：主要產品/服務、主要客戶或應用市場、公司在產業鏈的位置。
如果你不確定，請明確寫『資訊需再向公司最新公開資料確認』，不要自行捏造財務數字或客戶名稱。
"""
    return _client().models.generate_content(model="gemini-2.5-flash", contents=prompt).text
