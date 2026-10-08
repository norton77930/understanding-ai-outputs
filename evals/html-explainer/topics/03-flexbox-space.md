- Language: zh-TW
- Intended interaction: toggles (justify-content choice and per-item flex-grow)

## Source

flex 容器會把子項目排成一列，再決定剩下的空間怎麼處理。剩餘空間等於容器寬度減去所有子項目寬度的總和。有兩個設定會分配這些空間。justify-content 屬性把子項目當成一整組移動：flex-start 把它們靠在開頭，center 把剩餘空間平分在兩側，space-between 只把空間放在子項目之間的間隔。space-around 和 space-evenly 也會在兩端留空間，只是分量不同。flex-grow 屬性則是作用在單一子項目上：flex-grow 設成 2 的子項目，分到的剩餘空間是設成 1 的兩倍，寬度也跟著變大。預設值是 0，所以子項目不會變寬。一旦會變寬的子項目把剩餘空間全部分完，就沒有空間可以分配，justify-content 也就看不出任何效果。

## Reader should understand

- 剩餘空間是容器扣掉所有子項目本身寬度之後，剩下的部分。
- justify-content 把子項目當成一整組移動，決定剩餘空間放在哪裡。
- flex-grow 依照數值的比例分走剩餘空間，讓子項目變寬。
- 當設了 flex-grow 的子項目分完所有剩餘空間，justify-content 就不再有任何作用。

## Interaction hints

- Pattern: layer toggles. One group of buttons (radio style) picks the justify-content value: flex-start, center, flex-end, space-between, space-around, space-evenly. Three toggles set flex-grow for each item to 0 or 1, or a small number input per item.
- Suggested numbers: a 600 px container with three 100 px items, so the free space is 300 px. center puts 150 px on each side. space-between puts 150 px in each of the two gaps. space-around gives 100 px per item (50 px on each side of it). space-evenly gives 75 px in each of the four gaps. flex-grow of 1, 2 and 1 gives widths of 175, 250 and 175 px.
- Mark the free space visually (hatched or colored areas) and show the generated CSS as text, so the idea reads before any click.
- Use the real CSS flexbox for the demo, so the page itself is the proof. Keep controls keyboard-operable. Keep CSS property names in English; the page text is in Traditional Chinese.
