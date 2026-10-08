- Language: zh-TW
- Intended interaction: step-through (next / back) with preset access sequences

## Source

快取是一塊小而快的儲存空間，用來存放最近用過的資料。程式要讀資料時，先看快取裡有沒有：有的話叫做命中，可以直接拿；沒有的話叫做未命中，要去比較慢的地方讀，再放進快取。快取的空間有限，滿了就必須丟掉一筆資料。LRU（最近最少使用）的規則是：丟掉最久沒有被用到的那一筆。每次命中，那筆資料就變成「最近剛用過」，排到最新的位置。例如容量是 3，依序讀取 A、B、C、A、D、B、E：讀到 D 時快取已滿，最久沒用的是 B，所以丟掉 B。這個順序只有第二次讀 A 時命中。如果程式常常重複讀同一小批資料，LRU 的命中率就會很高。

## Reader should understand

- 命中是資料已經在快取裡；未命中要去慢的地方讀，再放進快取。
- 快取滿了以後，LRU 會丟掉最久沒有被用到的資料。
- 每次命中，那筆資料會變成最近剛用過，不容易被丟掉。
- 讀取順序常常重複同一小批資料時，命中率比較高。

## Interaction hints

- Pattern: step-through. Show the access sequence and the cache slots ordered from "least recent" to "most recent". Each step shows hit or miss and, on a miss with a full cache, which item is evicted.
- Suggested example: capacity 3, sequence A B C A D B E. States: [A], [A B], [A B C], hit A → [B C A], miss D evicts B → [C A D], miss B evicts C → [A D B], miss E evicts A → [D B E]. One hit, six misses.
- Preset scenarios: a repeating pattern (A B A B A C A B) with a high hit rate, and a scan (A B C D E F G) with no hits. Show a running hit-rate counter.
- Optional: a capacity slider (2 to 5) that replays the sequence.
