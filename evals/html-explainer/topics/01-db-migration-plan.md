- Language: zh-TW
- Request: 用工程圖紙（blueprint）風格做一個互動網頁，說明以下這份計畫。
- Intended interaction: step-through of the phases, reveal per assumption

## Source

這是 AI 助手寫的資料庫搬遷計畫：把訂單系統從 MySQL 搬到 PostgreSQL，分四個階段。第一階段，建立新的 PostgreSQL，用複寫工具把現有資料持續同步過去。第二階段，讓程式同時寫入兩邊，每天比對兩邊的資料筆數和金額總和。第三階段，在週日凌晨的維護時段把讀取切到 PostgreSQL，觀察一週。第四階段，停止寫入 MySQL，保留唯讀備份三十天後刪除。計畫有兩個假設：資料量約 200 GB，複寫在一天內追得上；週日凌晨停機三十分鐘，客戶可以接受。還有一件事沒有決定：每晚跑的報表工作在切換那一週要不要暫停，要問負責報表的團隊。

## Reader should understand

- 搬遷分四個階段：同步、雙寫加比對、切換讀取、停用舊資料庫。
- 「資料量 200 GB、一天內追得上」和「週日凌晨停機三十分鐘可接受」是假設，不是已確認的事。
- 報表工作在切換週要不要暫停還沒決定，要問報表團隊。
- 舊資料庫會先保留唯讀備份三十天，之後才刪除。

## Interaction hints

- Named style: blueprint (the request names it). The baseline gets the same request.
- Pattern: step-through of the four phases on one figure; status strokes for done / assumed / future.
- The "make the assumptions visible" pattern fits: two assumptions and one open decision, each with who to ask
  ("報表團隊" for the open decision; "not stated" for the two assumptions).
- Check that no assumption is invented beyond the two in the source.
