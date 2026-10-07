- Language: en
- Intended interaction: toggles (justify-content choice and per-item flex-grow)

## Source

A flex container lays its items in a row and decides what to do with the leftover room. Free space is the container's width minus the combined width of all items. Two settings share it out. The justify-content property moves the items as a group: flex-start packs them at the start, center puts the free space on both sides, and space-between puts it only in the gaps between items. Space-around and space-evenly also give room at the ends, in different amounts. The flex-grow property works on single items instead: an item with flex-grow set to 2 gets twice as much of the free space as an item set to 1, and it grows wider. The default is 0, so items do not grow. Once the growing items take all the free space, none is left, so justify-content has no visible effect.

## Reader should understand

- Free space is what is left in the container after the items take their own width.
- justify-content moves the items as a group and decides where the free space goes.
- flex-grow makes an item wider, in proportion to its value, by giving it a share of the free space.
- When items with flex-grow take all the free space, justify-content no longer changes anything.

## Interaction hints

- Pattern: layer toggles. One group of buttons (radio style) picks the justify-content value: flex-start, center, flex-end, space-between, space-around, space-evenly. Three toggles set flex-grow for each item to 0 or 1, or a small number input per item.
- Suggested numbers: a 600 px container with three 100 px items, so the free space is 300 px. center puts 150 px on each side. space-between puts 150 px in each of the two gaps. space-around gives 100 px per item (50 px on each side of it). space-evenly gives 75 px in each of the four gaps. flex-grow of 1, 2 and 1 gives widths of 175, 250 and 175 px.
- Mark the free space visually (hatched or colored areas) and show the generated CSS as text, so the idea reads before any click.
- Use the real CSS flexbox for the demo, so the page itself is the proof. Keep controls keyboard-operable.
