- Language: zh-TW
- Request: 用工程圖紙（blueprint）風格做一個互動網頁，說明以下這份提案。
- Intended interaction: toggle cache on / off, slider for hit rate

## Source

這是 AI 助手對商品頁變慢的改善提案：在商品 API 前面加一層 Redis 快取。目前每次開商品頁，API 都要查資料庫，平均 200 毫秒。加了快取之後，查得到快取的請求只要約 5 毫秒，查不到的才去資料庫，然後把結果存進快取，十分鐘後過期。如果九成請求都查得到快取，平均時間會降到約 24.5 毫秒（0.9 × 5 + 0.1 × 200）。提案有兩個假設：商品資料晚十分鐘更新，使用者可以接受；九成的請求集中在熱門商品，所以快取命中率能到九成。還有一件事沒有決定：商品改價時要不要立刻清掉那筆快取，要由產品負責人決定。

## Reader should understand

- 快取命中時約 5 毫秒，沒命中時去資料庫，約 200 毫秒，並把結果存十分鐘。
- 命中率九成時，平均約 24.5 毫秒；命中率越低，平均越接近 200 毫秒。
- 「晚十分鐘更新可接受」和「命中率能到九成」是假設。
- 改價時要不要立刻清快取還沒決定，由產品負責人決定。

## Interaction hints

- Named style: blueprint (the request names it). The baseline gets the same request.
- Pattern: a slider for hit rate (0-100%) that updates the average: average = r × 5 + (1 − r) × 200 ms
  (r = 0.9 → 24.5 ms; r = 0.5 → 102.5 ms; r = 0 → 200 ms); a toggle that shows the request path with and without the
  cache.
- The "make the assumptions visible" pattern fits: two assumptions and one open decision ("產品負責人").
- Check values: 24.5 ms at 90%, 102.5 ms at 50%.
