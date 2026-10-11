- Language: zh-TW
- Expected diagram type: `sequenceDiagram`

## Source

使用者忘記密碼時，在登入頁輸入電子郵件並按下「重設密碼」。伺服器不論這個信箱有沒有註冊，都回覆同一句「如果帳號存在，你會收到一封信」，避免別人用這個功能查出誰有帳號。帳號存在時，伺服器產生一個只能用一次的隨機代碼，設定 30 分鐘後失效，資料庫只存代碼的雜湊值，然後透過郵件服務寄出含有代碼的連結。使用者點開連結後，伺服器檢查代碼是否存在、是否過期。代碼有效時，頁面讓使用者輸入新密碼。伺服器存下新密碼的雜湊值，立刻作廢這個代碼，並登出這個帳號在其他裝置上的所有工作階段。

## Reader should understand

- 不論帳號是否存在，伺服器都回同一句話，避免洩漏誰有帳號。
- 重設代碼只能用一次、30 分鐘後失效，資料庫只存它的雜湊值。
- 連結經由郵件服務送到使用者，伺服器在使用前檢查代碼有效。
- 改完密碼後代碼作廢，其他裝置的工作階段都被登出。

## Diagram hints

- Expected type: `sequenceDiagram` (the question is "who talks to whom, in what order"). This topic checks that the
  skill still picks Mermaid for a flow after the SVG change.
- Participants (4): 使用者, 伺服器, 資料庫, 郵件服務.
- Messages (about 10): 送出信箱, 統一回覆, 存代碼雜湊, 寄出連結, 點開連結, 檢查代碼, 輸入新密碼, 存新密碼雜湊, 作廢代碼,
  登出其他工作階段.
- The caption should point at the identical reply and the one-time code.
