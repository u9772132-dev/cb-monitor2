# Taiwan CB Relative Value Dashboard V2

給台灣可轉債投資主管使用的 Streamlit Dashboard。

## 功能
- TPEx CB 每日行情與轉換價格
- 標的股票價格（TWSE / TPEx）
- 轉換價值、轉換溢價率、距轉換價%
- 全市場平均 CB 價格 + 價格區間分布
- 負溢價 Scanner
- CB 價格 ≤ 105 且溢價率 ≤ 15% Scanner
- 「剛突破轉換價」偵測與 Highlight
- 個股研究：CB 指標 + Gemini 公司業務摘要
- 我的最愛清單
- Gemini 每日 CB 投資摘要
- GitHub Actions 每個交易日自動更新資料

## 公式
- 轉換價值 = 標的股價 / 轉換價格 × 100
- 溢價率 = CB價格 / 轉換價值 - 1
- 距轉換價 = 標的股價 / 轉換價格 - 1
- 剛突破：今日距轉換價 > 0%，且前一交易日 ≤ 0%

## 本地執行
```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
```

建立 `.env`：
```text
GEMINI_API_KEY=你的 Gemini API Key
```

啟動：
```bash
streamlit run app.py
```

## GitHub + Streamlit Community Cloud
1. 把本專案全部檔案 push 到 GitHub。
2. 在 Streamlit Community Cloud 選 repository、branch=`main`、entrypoint=`app.py`。
3. 在 App 的 Secrets 設定：
```toml
GEMINI_API_KEY = "你的 Gemini API Key"
```
4. Deploy。

## GitHub Actions
`daily_update.yml` 會在平日約台灣時間 15:30 執行，將當日資料寫入 `data/latest.csv`，並將上一個 snapshot 留在 `data/previous_market.csv`，供「剛突破轉換價」判斷使用。

注意：GitHub Actions 的排程可能因平台負載略有延遲。

## 重要注意事項
TPEx 網站欄位或公開資料路徑若變更，`cb_monitor.py` 的欄位解析可能需要調整。此工具供研究與監控使用，不構成投資建議。


## V3 upgrades

- Daily archival: `data/daily/YYYY-MM-DD.csv`
- Market price-band counts and percentages
- Historical low-price CB heat trend for CB price <= 105
- GitHub Actions force-adds generated CSVs so `.gitignore` cannot block archival commits
- Gemini API key supports Streamlit Cloud `st.secrets["GEMINI_API_KEY"]`


## V4 修正：TPEx 舊 CSV 連結已失效

V3 使用的舊式 `RSta0113.YYYYMMDD-C.csv` 路徑目前會回傳 TPEx 404 HTML，因此 Streamlit 會看到「抓取失敗／CSV 欄位無法辨識」。

V4 已改成使用 TPEx 官方 OpenAPI：
- `bond_cb_daily`：CB 每日買賣斷券商買賣日報資料
- `bond_ISSBD5_data`：轉(交)換債發行/條件資料

並加入 JSON response normalization、欄位別名辨識與重試機制。

官方 TPEx OpenAPI 文件：
https://www.tpex.org.tw/openapi/swagger.json

部署後如仍出現抓取問題，可先在 GitHub Actions 手動執行：
`python scripts/diagnose_tpex.py`
查看 TPEx 實際回傳欄位。


## V5 修正
- 修正 `name '_get' is not defined`：補上共用 HTTP GET helper。
- 移除 V4 中誤殘留的舊 `fetch_cb_board()`，避免呼叫舊 TPEx HTML 頁面。
- Streamlit 即時抓取失敗時，若存在 `data/latest.csv`，自動改讀最近成功快取。
- 加入 GitHub Actions `workflow_dispatch`，可手動觸發每日資料更新。
- 修正 CB 價格區間邊界：100–105 含 105；105–110 從 105 以上至 110。


## V6 重要修正
- CB 每日行情改回 TPEx 官方 RSta0113 CSV。URL 依日期自動組成：`/storage/bond_zone/tradeinfo/cb/YYYY/YYYYMM/RSta0113.YYYYMMDD-C.csv`。
- `bond_cb_daily` 不再用作市場行情；該 API 是券商買賣日報。
- 遇週末/休市，程式會往前最多尋找 7 天的最近可用 CSV。
- CSV 解析支援 UTF-8 BOM、CP950/Big5，以及前置說明列。
- 保留 V5 的 cache fallback、每日 archive、價格分布、負溢價、突破轉換價、Favorites、Gemini 與 GitHub Actions。
- `bond_ISSBD5_data` 僅作 CB 條款/轉換價格來源；實際「有效轉換價格」仍應持續驗證公司行動/調整資料。


## V6 Debug 修正
- CB 每日行情唯一主來源：TPEx `RSta0113.YYYYMMDD-C.csv`。
- `bond_cb_daily` 已完全從每日行情流程移除，不再呼叫、不再做欄位解析。
- 因此不可能再因 `FinancialInstitutionsCode / ParValueOfPurchase / AmountOfPurchase` 觸發每日行情錯誤。
- CSV 解析支援 UTF-8-SIG、CP950、Big5、UTF-8，以及常見分隔格式。
- 應用程式首頁會顯示「資料引擎 V6 - TPEx RSta0113 CSV」，方便確認部署的版本。
