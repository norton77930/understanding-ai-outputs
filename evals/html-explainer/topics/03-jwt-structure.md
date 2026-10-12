- Language: zh-TW
- Intended interaction: layer toggles or reveal for the three parts; edit the payload and see the signature check fail

## Source

這是 AI 助手對「JWT（JSON Web Token）長什麼樣子」的說明。一個 JWT 是三段文字，用兩個點隔開：header.payload.signature。header 說明簽章用的演算法，例如 HS256。payload 放聲明（claims），例如用戶 ID（sub）和過期時間（exp）。這兩段都只是用 Base64URL 編碼，不是加密，任何人拿到 token 都能解開來看，所以不要在 payload 裡放密碼。第三段 signature 是伺服器用只有自己知道的密鑰，對「header.payload」這串文字算出來的簽章。有人改了 payload，例如把用戶 ID 換成別人的，簽章就對不上，伺服器會拒絕這個 token。

## Reader should understand

- JWT 由 header、payload、signature 三段組成，用點隔開。
- header 和 payload 只是 Base64URL 編碼，不是加密，任何人都能讀，所以不要放密碼。
- signature 是伺服器用密鑰對 header.payload 算出來的。
- 改動 payload 會讓簽章對不上，伺服器就拒絕這個 token。

## Interaction hints

- Default request, no named style. A purely structural topic: no number changes a result and there is no process to run. This is the control topic: the Explore stage is expected to be skipped, with the reason in the delivery line.
- Pattern ideas: layer toggles or reveal that decode each part; a button that changes the user ID in the payload and shows the signature check failing.
- Check: the page never says the payload is encrypted, and it does not invent claims the source does not name beyond common examples.
