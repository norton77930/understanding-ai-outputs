- Language: zh-TW
- Expected diagram type: `flowchart LR` (a chain of stages with checks)

## Source

使用者上傳一支影片後，影音平台會讓它依序經過幾個處理階段，每個階段完成才會進入下一個。第一步是檢查格式：檔案損壞或格式不支援時，流程立刻停止，並通知上傳者。格式沒問題，就進行轉檔，產生 360p、720p、1080p 等多種解析度，讓網速不同的觀眾都能順暢播放。接著從影片中擷取畫面，產生縮圖。然後進行自動內容審查，檢查是否有違反規定的內容。審查通過的影片會發布，出現在頻道上；沒通過的影片不會發布，而是交給人工複審，由審查人員決定要發布還是下架。

## Reader should understand

- 每支影片依序經過檢查格式、轉檔、產生縮圖、內容審查，才會發布。
- 格式不支援或檔案損壞時，流程立刻停止並通知上傳者。
- 轉檔會產生多種解析度，讓網速不同的觀眾都能播放。
- 自動審查沒通過的影片不會發布，而是交給人工複審。

## Diagram hints

- Expected type: `flowchart LR`: a chain of stages read left to right, with two checks that branch off (format check fails; automatic review fails).
- Key nodes (about 10): 上傳影片, 檢查格式, 通知上傳者 (stop), 轉檔 (360p / 720p / 1080p as a second line), 產生縮圖, 自動審查, 發布, 人工複審, 發布 or 下架.
- Color can mark pass and fail paths, with a legend.
- The caption should point at the two places where a video leaves the main line.
