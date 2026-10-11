- Language: zh-TW
- Request: 把以下內容整理成一張總覽圖，一張圖看懂 JWT。
- Expected diagram type: `svg`

## Source

JWT 是一種登入後用來證明身分的權杖，看起來是用兩個點隔開的三段文字：標頭、內容和簽章。標頭寫用哪種演算法簽名；內容放使用者編號、權限和到期時間等資料；簽章是伺服器用自己的密鑰，對前兩段算出來的結果。前兩段只是編碼，不是加密，任何人都能解開來看，所以不能放密碼之類的祕密。伺服器收到 JWT 時，用同一把密鑰重算簽章，跟收到的簽章比對：一樣就代表內容沒被改過，再檢查到期時間有沒有過。因為驗證只需要密鑰，伺服器不用查資料庫就能確認身分，這是 JWT 的優點；缺點是權杖發出去之後很難提早作廢，所以到期時間通常設得很短，再搭配一個存活較久的更新權杖來換新的 JWT。

## Reader should understand

- JWT 分成標頭、內容、簽章三段；前兩段只是編碼，任何人都看得到，不能放祕密。
- 伺服器用自己的密鑰重算簽章來確認內容沒被改過，並檢查到期時間。
- 驗證不用查資料庫，是 JWT 的優點。
- JWT 很難提早作廢，所以到期時間設短，再用更新權杖換新的。

## Diagram hints

- Expected output: one overview sheet (hand-written SVG, 3-6 panels with letter tabs, title block, one legend).
- Likely panels: the token split into three parts (annotated line), what each part holds (table), verification steps
  (small flow), visible vs secret (status table), short-lived JWT plus refresh token (timeline).
- Both arms get the same overview request.
