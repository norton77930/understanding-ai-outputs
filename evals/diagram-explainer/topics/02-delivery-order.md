- Language: zh-TW
- Expected diagram type: `stateDiagram-v2`

## Source

外送平台上的一張訂單會經過幾個狀態。顧客送出訂單後，訂單是「已下單」。店家接單後，訂單變成「準備中」；店家也可以拒單，訂單就變成「已取消」。在店家接單之前，顧客可以自己取消訂單；店家接單之後，顧客就不能自行取消，只能聯絡客服。餐點做好、外送員取餐之後，訂單變成「外送中」。外送員把餐點交給顧客，訂單就「已完成」。如果外送途中找不到顧客或發生意外，訂單會進入「異常處理」，由客服決定重新配送，或取消並退款。已完成和已取消的訂單都不會再改變。

## Reader should understand

- 訂單從已下單開始，店家接單後進入準備中。
- 店家接單前，顧客可以取消，店家也可以拒單；接單後顧客不能自行取消。
- 外送員取餐後是外送中，交給顧客後訂單就完成。
- 送達失敗時進入異常處理，之後重新配送，或取消並退款。

## Diagram hints

- Expected type: `stateDiagram-v2` (the question is "what states does one order go through").
- States (6): 已下單, 準備中, 外送中, 已完成, 異常處理, 已取消; start and end markers.
- Transitions with short labels: 店家接單, 店家拒單, 顧客取消, 外送員取餐, 交給顧客, 送達失敗, 重新配送 (異常處理→外送中), 取消並退款.
- Color can mark the two end states (完成 vs 取消) and the exception path.
- The caption should point at where the customer can still cancel.
