- Language: zh-TW
- Request: 把以下內容整理成一張總覽圖，一張圖看懂 HTTPS。
- Expected diagram type: `svg`

## Source

HTTPS 就是 HTTP 加上 TLS 加密。瀏覽器連到網站時，先做 TLS 握手：瀏覽器送出它支援的加密方式，伺服器選一種，並送回自己的憑證。憑證裡有網站的網域和公開金鑰，由憑證機構簽名；瀏覽器沿著憑證鏈往上檢查，直到找到內建信任的根憑證，確認這張憑證真的屬於這個網域、而且還沒過期。接著雙方用金鑰交換算出同一把「工作階段金鑰」，之後所有資料都用這把對稱金鑰加密，因為對稱加密比公開金鑰加密快很多。HTTPS 保護三件事：別人看不到內容（加密）、內容沒被改過（完整性）、對方真的是這個網站（身分驗證）。它不保護的是：網站本身是不是可信，以及你連到哪個網域這件事，旁人仍可能從 DNS 或連線資訊看出來。

## Reader should understand

- TLS 握手時，伺服器送出憑證，瀏覽器沿著憑證鏈檢查到內建信任的根憑證。
- 握手後雙方得到同一把工作階段金鑰，之後用速度快的對稱加密傳資料。
- HTTPS 保護內容不被看到、不被竄改，並確認對方身分。
- HTTPS 不保證網站本身可信，也不完全隱藏你連到哪個網域。

## Diagram hints

- Expected output: one overview sheet (hand-written SVG, 3-6 panels with letter tabs, title block, one legend).
- Likely panels: handshake steps (small flow), certificate chain (tree), what is protected vs not (status table), why
  symmetric after handshake (comparison or value bars).
- Both arms get the same overview request.
