- Language: zh-TW
- Output preset: `explainer` (16:9, 720p)
- Mode: `deep`
- Request: 用 3Blue1Brown 風格，把下面這段說明做成一支深入的解說影片。

## Source

二分搜尋是在已排序的資料裡找目標值的方法。先想一個遊戲：我心裡想一個一到一百之間的數字，你每猜一次，我只回答「太大」或「太小」。聰明的猜法是每次都猜剩下範圍的正中間，因為不管答案是什麼，都能刪掉一半的可能。二分搜尋就是這個想法。

假設有十六個由小到大排好的數字，要找其中的三十七。先看正中間的數字，把它和三十七比較。如果中間的數字比三十七小，目標一定在右半邊，因為左半邊的數字都更小，可以整個丟掉。如果中間的數字比三十七大，就丟掉右半邊。剩下的範圍再取中間，重複同樣的步驟。範圍從十六個變成八個、四個、兩個、一個，所以十六個數字最多只要比較五次。找到三十七就停止；如果範圍變成空的，表示資料裡沒有這個數字。

和從頭一個一個找相比，差距會隨資料量拉大。一個一個找，一百萬個數字最壞要比較一百萬次；二分搜尋每次減半，大約二十次就夠，因為二的二十次方已經超過一百萬。資料量變成兩倍，二分搜尋只多比較一次。

不過二分搜尋有個前提：資料必須先排好順序。如果資料沒排序，中間的數字比目標小，並不代表左半邊都更小，「丟掉一半」就不成立，可能會把目標丟掉。所以資料常常要查詢、很少變動時，先花時間排序，之後每次查詢都很快。

## Viewer should understand

- 每次挑剩下範圍的中間來比較，不管結果是大是小，都能刪掉一半（就像猜數字遊戲）。
- 拿目標和中間的數字比較，再丟掉不可能有目標的那一半；找到目標，或範圍變成空的（資料裡沒有這個數字）時就停止。
- 每比較一次範圍就減半：十六個數字最多五次；一百萬個數字逐一找最壞要一百萬次，二分搜尋大約二十次；資料量加倍只多一次。
- 資料必須先排好順序，否則「丟掉一半」不成立，可能把目標丟掉。

## Visual hints

- A 1-100 range bar for the guessing game, halving on each "too large / too small".
- A row of 16 boxes with the search range shown as a bracket that shrinks on each step; discarded boxes dim out; a pointer jumps to the middle box.
- A step counter that counts up for linear search vs binary search (one million vs about twenty).
- An unsorted row where the "discard half" step throws the target away.
