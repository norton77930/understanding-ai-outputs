- Language: zh-TW
- Intended interaction: sliders for bucket size, refill rate and request rate; run the requests over time and watch tokens and rejections

## Source

這是 AI 助手對「API 限流用的 token bucket」的說明。每個用戶有一個桶子，最多裝 10 個 token，一開始是滿的。系統每秒補 2 個 token，桶子滿了就不再補。每個請求要拿走 1 個 token；桶子空了，請求就被拒絕。所以用戶可以一次送出 10 個請求（突發），但長期平均每秒只能成功 2 個。如果用戶每秒持續送 5 個請求，桶子每秒淨少 3 個 token，大約 3.3 秒後就空了；之後每秒只有 2 個請求成功，另外 3 個被拒絕，也就是 60% 被拒絕。如果用戶每秒送 2 個以下，就永遠不會被拒絕。

## Reader should understand

- 桶子容量決定能一次突發多少請求（10 個），補充速度決定長期平均能成功多少（每秒 2 個）。
- 每秒 5 個請求時，桶子每秒淨少 3 個，約 3.3 秒後變空。
- 桶子空了以後，每秒 5 個請求中只有 2 個成功，3 個（60%）被拒絕。
- 請求速度不超過補充速度（每秒 2 個以下）時，永遠不會被拒絕。

## Interaction hints

- Default request, no named style. A topic with numbers and a process the reader can run: the Explore stage is expected.
- Pattern ideas: a step-through of the first seconds; an Explore stage with sliders for capacity (5-20), refill rate (1-5 per second) and request rate (1-10 per second), a Run button that plays 10 seconds, and a live chart of tokens and rejected requests.
- Check values: capacity 10, refill 2/s, requests 5/s → empty at 10 / 3 ≈ 3.3 s, then 3 rejected per second (60%); requests 2/s → 0 rejected; a burst of 11 at once on a full bucket → 10 accepted, 1 rejected.
