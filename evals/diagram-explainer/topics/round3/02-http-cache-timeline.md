- Language: zh-TW
- Expected diagram type: `svg`

## Source

伺服器回應時加上 `Cache-Control: max-age=600, stale-while-revalidate=60`，瀏覽器就會依時間決定怎麼用這份快取。從收到回應開始算，前 600 秒是「新鮮」期間：再次需要這個檔案時，瀏覽器直接用快取，完全不連伺服器。600 秒到 660 秒之間，快取已經「過期」，但還在寬限期內：瀏覽器先把舊的內容拿給頁面用，同時在背景問伺服器有沒有新版本。超過 660 秒後，寬限期也過了，瀏覽器必須先問到伺服器的答覆才能使用，使用者就要等一次網路來回。伺服器如果回答 304 Not Modified，表示內容沒變，瀏覽器不必重新下載，而且計時從這一刻重新開始。

## Reader should understand

- 0 到 600 秒是新鮮期間，直接用快取，不連伺服器。
- 600 到 660 秒是寬限期，先用舊內容，同時在背景向伺服器確認。
- 超過 660 秒要先問伺服器，使用者要等。
- 伺服器回 304 時不用重新下載，計時重新開始。

## Diagram hints

- Expected output: hand-written SVG (a timeline question), not a flowchart.
- A time axis from 0 s with marks at 600 s and 660 s; three bands (fresh, stale-while-revalidate, must revalidate)
  with what the browser does in each.
- A marker for a 304 answer that restarts the timer helps the fourth point.
- The caption should point at the grace period where the user does not wait.
