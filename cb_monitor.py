from __future__ import annotations
import io, re
from datetime import datetime, timedelta
from typing import Iterable

import numpy as np
import pandas as pd
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}
TPEx_CB_DAILY_PAGE = "https://www.tpex.org.tw/zh-tw/bond/info/statistics-cb/day-quotes.html"
TPEX_OPENAPI_BASE = "https://www.tpex.org.tw/openapi/v1"
TPEX_CB_DAILY_API = f"{TPEX_OPENAPI_BASE}/bond_cb_daily"
TPEX_CB_ISSUE_API = f"{TPEX_OPENAPI_BASE}/bond_ISSBD5_data"
TWSE_MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"


def clean_num(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip().replace(",", "").replace("%", "")
    if s in {"", "-", "--", "N/A", "nan", "None"}:
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def flatten_columns(df):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["".join(str(x) for x in col if str(x) != "nan").strip() for col in df.columns]
    df.columns = [re.sub(r"\s+", "", str(c)) for c in df.columns]
    return df


def pick_col(columns, groups):
    for group in groups:
        for c in columns:
            if all(k in str(c) for k in group):
                return c
    return None


def _get(url, **kwargs):
    """HTTP GET helper used by TPEx/TWSE fetchers."""
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", 30)
    r = requests.get(url, **kwargs)
    r.raise_for_status()
    return r


def _get_json(url, **kwargs):
    r = _get(url, **kwargs)
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError(f"TPEx API 回傳不是 JSON：{url}；HTTP {r.status_code}") from e


def _api_rows(payload):
    """Normalize common TPEx OpenAPI response shapes into a list of dicts."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "Data", "result", "results", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        # Some APIs return a dict of records.
        if payload and all(isinstance(v, dict) for v in payload.values()):
            return list(payload.values())
    return []


def _norm_key(x):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(x).lower())


def _pick_json_field(rows, aliases, required=False):
    if not rows:
        return None
    keys = list(rows[0].keys())
    nkeys = {_norm_key(k): k for k in keys}
    # Exact normalized match first.
    for a in aliases:
        na = _norm_key(a)
        if na in nkeys:
            return nkeys[na]
    # Then substring match.
    for a in aliases:
        na = _norm_key(a)
        for nk, original in nkeys.items():
            if na and na in nk:
                return original
    if required:
        raise ValueError(f"TPEx API 欄位無法辨識，現有欄位：{keys}")
    return None


def _json_rows_to_frame(rows):
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def fetch_cb_daily(date=None):
    """
    Fetch CB daily market data from the current TPEx OpenAPI.

    The previous V3 implementation depended on the legacy RSta0113 CSV URL,
    which now returns a TPEx 404 HTML page. TPEx currently exposes the CB
    broker daily report through the OpenAPI endpoint `bond_cb_daily`.
    """
    last = None
    for attempt in range(3):
        try:
            payload = _get_json(TPEX_CB_DAILY_API)
            rows = _api_rows(payload)
            if not rows:
                raise ValueError("TPEx bond_cb_daily API 回傳 0 筆資料。")
            df = _json_rows_to_frame(rows)
            out = normalize_daily(df)
            if out.empty:
                raise ValueError("TPEx bond_cb_daily API 有資料，但無法辨識有效 CB 價格。")
            out["資料日期"] = datetime.now().date().isoformat()
            return out
        except Exception as e:
            last = e
            if attempt < 2:
                import time
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(
        "無法取得 TPEx CB 每日行情（已改用 TPEx OpenAPI）。"
        f"最後錯誤：{last}"
    )


def normalize_daily(df):
    df = flatten_columns(df)
    code = pick_col(df.columns, [
        ["證券代號"], ["債券代號"], ["代號"], ["bondcode"], ["securitiescode"]
    ])
    name = pick_col(df.columns, [
        ["證券名稱"], ["債券名稱"], ["名稱"], ["bondname"], ["securitiesname"]
    ])
    close = pick_col(df.columns, [
        ["收盤價"], ["收市價"], ["成交價"], ["最後成交價"],
        ["closingprice"], ["close"], ["lastprice"], ["price"]
    ])
    volume = pick_col(df.columns, [
        ["成交張數"], ["成交量"], ["成交股數"], ["tradingvolume"],
        ["tradinglots"], ["volume"]
    ])
    amount = pick_col(df.columns, [
        ["成交金額"], ["成交值"], ["transactionamount"], ["tradingamount"],
        ["amount"]
    ])

    if code is None or close is None:
        raise ValueError(f"TPEx API 欄位無法辨識：{list(df.columns)}")

    out = pd.DataFrame()
    out["CB代號"] = (
        df[code].astype(str).str.replace(r"\.0$", "", regex=True)
        .str.extract(r"(\d{5,6})")[0]
    )
    out["CB名稱"] = df[name].astype(str).str.strip() if name else ""
    out["CB價格"] = df[close].map(clean_num)
    out["成交量原始"] = df[volume].map(clean_num) if volume else np.nan
    out["成交金額原始"] = df[amount].map(clean_num) if amount else np.nan
    out["成交量(張)"] = out["成交量原始"]
    out["成交金額(千元)"] = out["成交金額原始"] / 1000 if amount else np.nan

    out = out.dropna(subset=["CB代號", "CB價格"])
    out = out[out["CB代號"].str.match(r"^\d{5,6}$", na=False)]
    return out.drop_duplicates("CB代號").reset_index(drop=True)


def fetch_cb_terms_openapi():
    """
    Fetch current CB issuance/terms information from TPEx OpenAPI.
    Used as the fallback/current source for conversion price and underlying.
    """
    payload = _get_json(TPEX_CB_ISSUE_API)
    rows = _api_rows(payload)
    if not rows:
        raise ValueError("TPEx bond_ISSBD5_data API 回傳 0 筆資料。")
    df = _json_rows_to_frame(rows)

    code = _pick_json_field(df.to_dict("records"), [
        "證券代號", "債券代號", "代號", "BondCode", "SecuritiesCode"
    ], required=True)
    conv = _pick_json_field(df.to_dict("records"), [
        "轉換價格", "轉換價", "目前轉換價格", "ConversionPrice",
        "CurrentConversionPrice"
    ])
    underlying = _pick_json_field(df.to_dict("records"), [
        "轉換標的代號", "標的股票代號", "標的代號", "轉換標的",
        "UnderlyingStockCode", "UnderlyingCode"
    ])
    name = _pick_json_field(df.to_dict("records"), [
        "證券名稱", "債券名稱", "名稱", "BondName", "SecuritiesName"
    ])
    maturity = _pick_json_field(df.to_dict("records"), [
        "到期日", "到期日期", "MaturityDate", "Maturity"
    ])

    out = pd.DataFrame()
    out["CB代號"] = (
        df[code].astype(str).str.replace(r"\.0$", "", regex=True)
        .str.extract(r"(\d{5,6})")[0]
    )
    out["CB名稱板"] = df[name].astype(str).str.strip() if name else ""
    out["轉換價格"] = df[conv].map(clean_num) if conv else np.nan
    if underlying:
        out["標的股票代號"] = (
            df[underlying].astype(str).str.replace(r"\.0$", "", regex=True)
            .str.extract(r"(\d{4})")[0]
        )
    else:
        out["標的股票代號"] = out["CB代號"].str[:4]
    if maturity:
        out["到期日"] = df[maturity].astype(str).str.strip()
    return out.dropna(subset=["CB代號"]).drop_duplicates("CB代號")


def fetch_cb_board():
    # Keep the old function name for compatibility with the app.
    # It now uses the TPEx OpenAPI instead of the retired HTML table.
    return fetch_cb_terms_openapi()


def normalize_board(df):
    # Compatibility helper retained for external callers.
    return fetch_cb_terms_openapi()


def fetch_stock_prices(stock_ids: Iterable[str]):
    ids = sorted({str(x).zfill(4) for x in stock_ids if pd.notna(x) and re.fullmatch(r"\d{4}", str(x))})
    result = {}
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        ex = "|".join([f"tse_{x}.tw" for x in chunk] + [f"otc_{x}.tw" for x in chunk])
        try:
            data = _get(TWSE_MIS, params={"ex_ch": ex, "json": "1", "delay": "0"}).json()
            for item in data.get("msgArray", []):
                code = str(item.get("c", "")).zfill(4)
                p = item.get("z") or item.get("y")
                result[code] = clean_num(p)
        except Exception:
            for code in chunk:
                for exname in ("tse", "otc"):
                    try:
                        data = _get(TWSE_MIS, params={"ex_ch": f"{exname}_{code}.tw", "json": "1", "delay": "0"}).json()
                        arr = data.get("msgArray", [])
                        if arr:
                            result[code] = clean_num(arr[0].get("z") or arr[0].get("y"))
                            break
                    except Exception:
                        pass
    return result


def calculate(df):
    df = df.copy()
    df["轉換價值"] = df["標的股價"] / df["轉換價格"] * 100
    df["溢價率"] = df["CB價格"] / df["轉換價值"] - 1
    df["距轉換價%"] = df["標的股價"] / df["轉換價格"] - 1
    return df.replace([np.inf, -np.inf], np.nan)


def load_market_data():
    daily = fetch_cb_daily()
    board = fetch_cb_board()
    df = daily.merge(board, on="CB代號", how="left", suffixes=("", "_board"))
    if "CB名稱_board" in df:
        df["CB名稱"] = df["CB名稱"].where(df["CB名稱"].astype(str).str.len() > 0, df["CB名稱_board"])
        df = df.drop(columns=["CB名稱_board"])
    if "標的股票代號" not in df:
        df["標的股票代號"] = df["CB代號"].str[:4]
    prices = fetch_stock_prices(df["標的股票代號"])
    df["標的股價"] = df["標的股票代號"].map(prices)
    df["標的股票名稱"] = ""
    df = calculate(df)
    df = df[df["轉換價格"].notna() & df["標的股價"].notna() & df["CB價格"].notna()]
    return df.sort_values("溢價率").reset_index(drop=True)


def apply_filters(df, price_limit=105.0, premium_limit=15.0, min_volume=0.0):
    x = df.copy()
    if "成交量(張)" in x:
        x = x[x["成交量(張)"].fillna(0) >= min_volume]
    return x


def add_breakout_flags(current: pd.DataFrame, previous: pd.DataFrame | None):
    x = current.copy()
    x["剛突破轉換價"] = False
    x["前一日距轉換價%"] = np.nan
    if previous is None or previous.empty:
        return x
    pcols = [c for c in ["CB代號", "標的股價", "轉換價格"] if c in previous.columns]
    if len(pcols) < 3:
        return x
    p = previous[pcols].copy().drop_duplicates("CB代號")
    p["前一日距轉換價%"] = p["標的股價"] / p["轉換價格"] - 1
    x = x.merge(p[["CB代號", "前一日距轉換價%"]], on="CB代號", how="left", suffixes=("", "_prev"))
    x["剛突破轉換價"] = (x["距轉換價%"] > 0) & (x["前一日距轉換價%"] <= 0)
    return x
