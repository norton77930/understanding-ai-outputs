- Language: zh-TW
- Intended interaction: step-through of the retries, sliders for the first wait and the cap, a jitter toggle with many clients

## Source

這是 AI 助手對「呼叫失敗時怎麼重試」的建議。不要失敗就馬上重試，要用指數退避：第 1 次重試前等 1 秒，之後每次等待時間加倍，也就是 1、2、4、8 秒。每次等待最多 10 秒，所以第 5 次重試前等的是 10 秒，不是 16 秒。最多重試 5 次，總共最多等 1 + 2 + 4 + 8 + 10 = 25 秒；如果沒有 10 秒上限，會是 31 秒。另外要加隨機抖動（jitter）：每次實際等待時間在 0 和算出來的等待時間之間隨機取。這樣伺服器恢復時，100 個用戶端不會在同一秒一起重試，把伺服器又打掛。

## Reader should understand

- 每次重試前的等待時間加倍：1、2、4、8 秒。
- 上限讓等待時間不超過 10 秒，所以 5 次重試總共最多等 25 秒（沒有上限是 31 秒）。
- 沒有抖動時，所有用戶端在同一個時間點一起重試。
- 抖動把重試分散到一段時間裡，伺服器恢復時不會被同時湧入的請求打掛。

## Interaction hints

- Default request, no named style. A topic with numbers and a process the reader can run: the Explore stage is expected.
- Pattern ideas: a step-through of the five retries on a timeline; an Explore stage with sliders for the first wait (0.5-4 s), the cap (2-30 s) and the number of clients (1-200), a jitter on/off toggle, a Run button, and a live chart of retries per second at the server.
- Check values: first wait 1 s, cap 10 s, 5 retries → waits 1, 2, 4, 8, 10, total 25 s; cap 30 s → 1, 2, 4, 8, 16, total 31 s; first wait 2 s, cap 10 s → 2, 4, 8, 10, 10, total 34 s.
