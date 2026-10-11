- Language: zh-TW
- Expected diagram type: `svg`

## Source

資料表有一百萬筆資料時，資料庫通常用 B+ 樹當索引，避免一筆一筆找。B+ 樹的每個節點不是只放一個鍵，而是放好幾百個排好序的鍵，把範圍切成很多段。查詢 id = 734512 時，資料庫從根節點開始，看這個值落在哪一段，就往那一段的子節點走。下一層再切得更細，一直走到葉節點。葉節點存著鍵和那一筆資料的位置，找到後就能直接讀那一筆。因為每個節點能分出幾百條路，一百萬筆資料通常只要三層，也就是讀三個節點就找到。葉節點之間還依順序串在一起，所以查「id 介於 1000 和 2000 之間」時，找到第一筆後沿著葉節點往右讀就好，不必回到根節點。

## Reader should understand

- 每個節點放很多排好序的鍵，把範圍切成很多段。
- 查詢從根節點一層層往下，每一層都把範圍縮小，最後到葉節點。
- 因為一個節點分出很多條路，一百萬筆通常三層就到。
- 葉節點依順序串在一起，範圍查詢沿著葉節點往右讀。

## Diagram hints

- Expected output: hand-written SVG (a concept and spatial question: how the range narrows level by level).
- Three levels (root, internal, leaf) with a few sample keys per node and an ellipsis for the rest; the path for
  734512 highlighted; leaves linked left to right.
- Showing the range shrinking at each level (for example a bar under each level) helps the second point.
- The caption should point at three reads for a million rows.
