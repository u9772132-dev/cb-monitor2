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
