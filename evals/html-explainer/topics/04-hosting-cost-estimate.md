- Language: zh-TW
- Intended interaction: sliders for the assumed inputs, reveal of each assumption

## Source

這是 AI 助手對「部落格網站每月主機要花多少錢」的估算。主機本身每月固定 20 美元。另外要付流量費：每個月約 5 萬次瀏覽，每次瀏覽平均傳出 2 MB，總共約 100 GB，流量費每 GB 0.09 美元，所以約 9 美元。合計每月約 29 美元。這個估算建立在三個假設上：每月 5 萬次瀏覽是用上個月的數字推的；每頁 2 MB 是假設圖片沒有壓縮；流量單價用的是主機商網站上的公開價格，沒有算折扣。如果圖片壓縮到每頁 1 MB，流量費會減半，合計約 24.5 美元。

## Reader should understand

- 每月費用 = 主機 20 美元 + 流量費；5 萬次 × 2 MB ≈ 100 GB，流量費約 9 美元，合計約 29 美元。
- 瀏覽次數、每頁大小和流量單價都是假設，各有來源。
- 每頁大小減半時，流量費也減半，合計約 24.5 美元。
- 瀏覽次數或每頁大小變大時，只有流量費那一部分會跟著變。

## Interaction hints

- No named style (default request). This topic checks two things: default pages do not regress, and the optional
  "make the assumptions visible" pattern appears without a style because the source states assumptions.
- Pattern: sliders for monthly views (10k-200k) and page size (0.5-4 MB); total = 20 + views × size(MB) / 1000 × 0.09.
- Check values: 50k × 2 MB → 100 GB → $9 → $29; 50k × 1 MB → $4.5 → $24.5; 100k × 2 MB → $18 → $38.
- Check that the three assumptions are shown as assumptions and none is invented.
