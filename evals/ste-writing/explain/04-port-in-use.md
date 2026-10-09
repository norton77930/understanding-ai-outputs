- Language: zh-TW
- Type: troubleshooting

## Request

用 STE 解釋：啟動開發伺服器時出現「address already in use」錯誤，原因是什麼，以及怎麼排除。

## Context

執行 `npm run dev` 時，終端機顯示：`Error: listen EADDRINUSE: address already in use :::3000`

## Reader should understand

- 這個錯誤表示另一個處理程序（process）已經在監聽 3000 這個連接埠，所以伺服器無法再使用同一個連接埠。
- 常見原因：上一次啟動的伺服器沒有真正結束（例如還在另一個終端機視窗裡執行），或另一個專案也使用 3000。
- 找出占用連接埠的處理程序：Windows 執行 `netstat -ano | findstr :3000`，看最後一欄的 PID；macOS 或 Linux 執行 `lsof -i :3000`。
- 兩種解法：確認那個處理程序可以結束之後，再結束它；或讓開發伺服器改用另一個連接埠。
