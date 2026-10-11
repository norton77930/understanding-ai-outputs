- Language: zh-TW
- Expected diagram type: `sequenceDiagram`

## Source

在網路商店用信用卡付款時，會經過好幾方。使用者在結帳頁輸入卡號後，卡號直接送到支付閘道，商店的伺服器只拿到一個代表這張卡的代碼，不會保存卡號。商店用這個代碼請支付閘道發起授權。支付閘道把授權請求轉給發卡銀行。發卡銀行檢查卡片是否有效、額度夠不夠，以及這筆交易看起來是否有風險，然後回覆核准或拒絕。核准時，銀行會先保留這筆金額，但還沒有真正扣款。結果依序從支付閘道傳回商店，商店再顯示「付款成功」或「付款失敗」給使用者。等商店出貨之後，才向支付閘道請款，這時金額才真正從卡片扣除。

## Reader should understand

- 卡號由支付閘道處理，商店只拿到代碼，不保存卡號。
- 授權由發卡銀行決定：檢查卡片、額度和風險，核准時先保留金額。
- 核准或拒絕的結果依序傳回商店，再顯示給使用者。
- 真正扣款（請款）通常在出貨之後才發生。

## Diagram hints

- Expected type: `sequenceDiagram` (the question is "who talks to whom, in what order").
- Participants (4): 使用者, 商店, 支付閘道, 發卡銀行.
- Messages (about 9): 輸入卡號 (使用者→支付閘道), 回傳代碼 (支付閘道→商店), 發起授權, 轉送授權請求, 檢查卡片與額度 (self or note), 核准並保留金額, 回覆結果 ×2, 顯示結果; later 請款 after 出貨 (a separate phase).
- A visible phase split (授權 / 出貨後請款) helps the fourth point.
- The caption should point at the card number never reaching the shop and at the late capture.
