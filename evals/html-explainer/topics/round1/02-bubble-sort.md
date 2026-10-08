- Language: zh-TW
- Intended interaction: step-through (next / back)

## Source

泡沫排序（也稱氣泡排序）是很簡單的排序方法。它從資料的最左邊開始，每次比較相鄰的兩個數字：如果左邊的比右邊的大，就交換它們，否則維持原樣。接著往右移一格，再比較下一對，直到走到最右邊。走完這一輪之後，最大的數字一定已經被推到最右邊，不用再處理。然後從頭再來一輪，這次只需要處理剩下的部分。每一輪都會讓下一個最大的數字就定位，就像泡沫一個個浮到水面。如果某一輪完全沒有發生交換，表示資料已經排好，可以提早結束。泡沫排序容易理解，但資料量變成兩倍時，比較次數大約變成四倍，所以只適合少量資料。

## Reader should understand

- 每次只比較相鄰的兩個數字，左邊比右邊大就交換。
- 每走完一輪，目前最大的數字就會到達最右邊的正確位置。
- 某一輪沒有發生任何交換，就表示已經排好，可以停止。
- 資料量越大，比較次數增加得越快，所以只適合少量資料。

## Interaction hints

- Pattern: step-through with "Next" and "Back" buttons (plus "Reset"). Each press shows one comparison, and the page says in one line what happened ("compare 5 and 1: swap" or "no swap").
- Suggested example: the list 5, 1, 4, 2, 8. Pass 1 swaps give 1 5 4 2 8, then 1 4 5 2 8, then 1 4 2 5 8, and the last pair (5, 8) needs no swap. Pass 2 swaps give 1 2 4 5 8. Pass 3 has no swap, so the sort stops.
- Show the list as boxes (or bars). Highlight the pair being compared, and mark the numbers that are already in their final place at the right end.
- Show a step counter and a comparison counter. The page text is readable before the first click (show the starting list and a short rule).
- Keep every control reachable by keyboard, and keep the text in Traditional Chinese.
