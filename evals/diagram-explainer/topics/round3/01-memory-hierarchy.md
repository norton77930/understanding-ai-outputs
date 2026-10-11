- Language: zh-TW
- Expected diagram type: `svg`

## Source

程式讀一筆資料時，CPU 會先找離自己最近的地方。最近的是 L1 快取，每個核心只有幾十 KB，大約 1 奈秒就能讀到。找不到就往下找 L2 快取，容量是幾百 KB 到幾 MB，大約 4 奈秒。再下一層是 L3 快取，由所有核心共用，有幾十 MB，大約 10 到 20 奈秒。快取都找不到時，才去主記憶體（RAM）拿，容量是幾十 GB，但要大約 100 奈秒。如果資料根本不在記憶體裡，就要從 SSD 讀，容量是幾 TB，時間卻要幾十到一百微秒，也就是比 L1 慢上萬倍。每往下一層，容量變大，速度卻慢一個數量級左右。所以程式如果反覆存取同一小塊資料，大部分讀取都會停在上面幾層，跑起來就快很多。

## Reader should understand

- 從 L1、L2、L3、RAM 到 SSD，每往下一層容量變大、速度變慢。
- 速度差距是數量級的差距：SSD 比 L1 慢上萬倍。
- CPU 由上往下找，上一層找不到才去下一層。
- 反覆存取同一小塊資料時，讀取多半停在快取，所以程式比較快。

## Diagram hints

- Expected output: hand-written SVG (a proportion question: sizes and speeds side by side), not boxes and arrows.
- Five levels (L1, L2, L3, RAM, SSD), each with capacity and access time; a log-scale bar or a widening stack shows the
  order-of-magnitude gaps.
- A "look up, miss, go down" path helps the third point.
- The caption should point at the gap between the caches and the SSD.
