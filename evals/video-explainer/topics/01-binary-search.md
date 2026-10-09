- Language: zh-TW
- Output preset: `explainer` (16:9, 720p)
- Mode: `deep`
- Request: 用 3Blue1Brown 風格，把下面這段說明做成一支深入的解說影片。

## Source

二分搜尋是在已排序的資料裡找目標值的方法。假設有十六個由小到大排好的數字，要找其中的三十七。先看正中間的數字，把它和三十七比較。如果中間的數字比三十七小，目標一定在右半邊，左半邊就可以整個丟掉。如果中間的數字比三十七大，就丟掉右半邊。每比較一次，要找的範圍就縮小一半。剩下的範圍再取中間，重複同樣的步驟，直到找到三十七，或範圍變成空的，表示資料裡沒有這個數字。十六個數字最多只要比較五次，一百萬個數字也只要二十次左右。不過二分搜尋有個前提：資料必須先排好順序，否則「丟掉一半」就不成立。

## Viewer should understand

- 每次拿目標和中間的數字比較,再丟掉不可能有目標的那一半。
- 每比較一次,範圍就縮小一半,所以步驟數增加得很慢:十六個數字最多五次,一百萬個數字大約二十次。
- 找到目標,或範圍變成空的(資料裡沒有這個數字)時就停止。
- 資料必須先排好順序,這個方法才成立。

## Visual hints

- A row of 16 boxes with the search range shown as a bracket that shrinks on each step; discarded boxes dim out.
- A pointer jumping to the middle box, with a "too small" or "too large" label.
- A simple counter or bar comparing the steps for 16 items versus one million items.
