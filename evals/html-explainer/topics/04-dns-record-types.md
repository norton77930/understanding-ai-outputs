- Language: zh-TW
- Intended interaction: reveal or layer toggles for each record type; a grouped view of one domain's records

## Source

這是 AI 助手對「DNS 記錄有哪幾種」的說明。一個網域名稱底下可以有好幾筆不同類型的記錄，每種類型回答一個不同的問題。A 記錄說這個名稱對應哪個 IPv4 位址；AAAA 記錄說它對應哪個 IPv6 位址。CNAME 記錄說這個名稱是另一個名稱的別名，例如 www.example.com 是 example.com 的別名。MX 記錄說寄給這個網域的電子郵件要送到哪台郵件伺服器。TXT 記錄放任意文字，常用來向外部服務證明這個網域是你的。NS 記錄說哪幾台伺服器負責回答這個網域的問題。要注意：一個名稱如果有 CNAME 記錄，就不能再有其他類型的記錄。

## Reader should understand

- 一個網域名稱可以有好幾筆不同類型的記錄，每種類型回答不同的問題。
- A 對應 IPv4，AAAA 對應 IPv6，CNAME 是別名，MX 是收信伺服器，TXT 是任意文字（常用來驗證網域），NS 是負責的伺服器。
- 有 CNAME 記錄的名稱，不能再有其他類型的記錄。

## Interaction hints

- Default request, no named style. A purely definitional topic: no number changes a result and the source describes no process to run. This is the control topic for the skip rule: the Explore stage is expected to be skipped, with the reason in the delivery line ("No Explore stage: ...").
- Pattern ideas: reveal per record type, layer toggles over one domain's record list, a predict-then-reveal ("which record answers: where does mail go?").
- Check: the page does not invent a lookup process, TTLs or numbers the source does not state, and states the CNAME rule correctly.
