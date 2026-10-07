- Language: zh-TW
- Output preset: `explainer` (16:9, 720p)
- Target length: 60–90 s, 4–6 scenes

## Source

二分搜尋是在已排序的資料裡找目標值的方法。假設有十六個由小到大排好的數字，要找其中的三十七。先看正中間的數字，把它和三十七比較。如果中間的數字比三十七小，目標一定在右半邊，左半邊就可以整個丟掉。如果中間的數字比三十七大，就丟掉右半邊。每比較一次，要找的範圍就縮小一半。剩下的範圍再取中間，重複同樣的步驟，直到找到三十七，或範圍變成空的，表示資料裡沒有這個數字。十六個數字最多只要比較四次，一百萬個數字也只要二十次左右。不過二分搜尋有個前提：資料必須先排好順序，否則「丟掉一半」就不成立。

## Viewer should understand

- The method compares the target with the middle item, then discards the half that cannot contain it.
- Each comparison halves the remaining range, so the number of steps grows very slowly (about 4 for 16 items, about 20 for a million).
- It stops when it finds the target or the range is empty (the number is not in the data).
- It only works if the data is sorted first.

## Visual hints

- A row of 16 boxes with the search range shown as a bracket that shrinks on each step; discarded boxes dim out.
- A pointer jumping to the middle box, with a "too small" or "too large" label.
- A simple counter or bar comparing the steps for 16 items versus one million items.
