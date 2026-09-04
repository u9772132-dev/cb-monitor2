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
TPEx_CB_DAILY_PAGE = "https://www.tpex.org.tw/web/bond/tradeinfo/cb/CBDaily.php?l=zh-tw"
TPEx_CB_DAILY_CSV = "https://www.tpex.org.tw/storage/bond_zone/tradeinfo/cb/{yyyy}/{yyyymm}/RSta0113.{yyyymmdd}-C.csv"
TPEx_CB_LEGACY_CSV = "https://www.tpex.org.tw/web/bond_trading_info/bonds_info/daily/data/rsta0113.{yyyymmdd}-C.csv"
TWSE_MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"


def _get(url, **kwargs):
    r = requests.get(url, headers=HEADERS, timeout=30, **kwargs)
    r.raise_for_status()
    return r


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


def fetch_cb_daily(date=None):
    d = date.date() if isinstance(date, datetime) else (date or datetime.now().date())
    last = None
    for i in range(10):
        dd = d - timedelta(days=i)
        if dd.weekday() >= 5:
            continue
        yyyymmdd, yyyy, yyyymm = dd.strftime("%Y%m%d"), dd.strftime("%Y"), dd.strftime("%Y%m")
        candidates = [
            TPEx_CB_DAILY_CSV.format(yyyy=yyyy, yyyymm=yyyymm, yyyymmdd=yyyymmdd),
            TPEx_CB_LEGACY_CSV.format(yyyymmdd=yyyymmdd),
        ]
        for url in candidates:
            try:
                raw = _get(url).content
                text = None
                for enc in ("utf-8-sig", "big5", "cp950", "utf-8"):
                    try:
                        text = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        pass
                if text is None:
                    continue
                df = pd.read_csv(io.StringIO(text), dtype=str)
                df = flatten_columns(df)
                if len(df.columns) < 3:
                    continue
                out = normalize_daily(df)
                out["資料日期"] = dd.isoformat()
                return out
            except Exception as e:
                last = e
    raise RuntimeError(f"無法取得 TPEx CB 每日 CSV。最後錯誤：{last}")


def normalize_daily(df):
    df = flatten_columns(df)
    code = pick_col(df.columns, [["代號"], ["證券代號"], ["債券代號"]])
    name = pick_col(df.columns, [["名稱"], ["證券名稱"], ["債券名稱"]])
    close = pick_col(df.columns, [["成交價"], ["收盤價"], ["收市價"], ["最後成交價"]])
    volume = pick_col(df.columns, [["成交量"], ["成交股數"], ["成交張數"]])
    amount = pick_col(df.columns, [["成交金額"], ["成交值"]])
    if code is None or close is None:
        raise ValueError(f"TPEx CSV 欄位無法辨識：{list(df.columns)}")
    out = pd.DataFrame()
    out["CB代號"] = df[code].astype(str).str.extract(r"(\d{4,6})")[0]
    out["CB名稱"] = df[name].astype(str).str.strip() if name else ""
    out["CB價格"] = df[close].map(clean_num)
    out["成交量原始"] = df[volume].map(clean_num) if volume else np.nan
    out["成交金額原始"] = df[amount].map(clean_num) if amount else np.nan
    out["成交量(張)"] = out["成交量原始"]
    out["成交金額(千元)"] = out["成交金額原始"] / 1000 if amount else np.nan
    out = out.dropna(subset=["CB代號", "CB價格"])
    return out[out["CB代號"].str.match(r"^\d{5,6}$", na=False)].drop_duplicates("CB代號")


def fetch_cb_board():
    r = _get(TPEx_CB_DAILY_PAGE)
    tables = pd.read_html(io.StringIO(r.text))
    best, score = None, -1
    for t in tables:
        t = flatten_columns(t)
        txt = " ".join(map(str, t.columns)) + " " + " ".join(t.astype(str).head(5).fillna("").values.ravel())
        s = sum(k in txt for k in ["轉換", "代號", "價格", "公司債"])
        if s > score:
            score, best = s, t
    if best is None:
        raise ValueError("TPEx CB 資訊看板沒有可解析的表格。")
    return normalize_board(best)


def normalize_board(df):
    df = flatten_columns(df)
    code = pick_col(df.columns, [["代號"], ["債券代號"], ["證券代號"]])
    name = pick_col(df.columns, [["名稱"], ["債券名稱"], ["證券名稱"]])
    conv = pick_col(df.columns, [["轉換價格"], ["轉換價"]])
    underlying = pick_col(df.columns, [["轉換標的代號"], ["標的代號"], ["轉換標的"]])
    maturity = pick_col(df.columns, [["到期日"], ["到期日期"]])
    if code is None or conv is None:
        raise ValueError(f"TPEx CB 資訊看板找不到代號/轉換價格欄位：{list(df.columns)}")
    out = pd.DataFrame()
    out["CB代號"] = df[code].astype(str).str.extract(r"(\d{5,6})")[0]
    if name:
        out["CB名稱板"] = df[name].astype(str).str.strip()
    out["轉換價格"] = df[conv].map(clean_num)
    out["標的股票代號"] = df[underlying].astype(str).str.extract(r"(\d{4})")[0] if underlying else out["CB代號"].str[:4]
    if maturity:
        out["到期日"] = df[maturity].astype(str).str.strip()
    return out.dropna(subset=["CB代號"]).drop_duplicates("CB代號")


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
