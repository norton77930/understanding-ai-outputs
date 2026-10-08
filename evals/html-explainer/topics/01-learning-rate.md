- Language: zh-TW
- Intended interaction: slider (learning rate)

## Source

梯度下降是一種找函數低點的方法：每次往下坡走一小步。每一步，程式先量目前位置的斜率，再往相反的方向移動。學習率是決定步伐大小的數字：新位置等於舊位置減去學習率乘以斜率。學習率太小時，每一步都很小，程式要走非常多步才會到底。學習率選得好時，一開始步伐很大，越接近底部、斜率越平，步伐就越小，最後停在最低點。學習率太大時，一步就可能跨過底部，落在另一邊更高的地方。接著它會左右來回跳，甚至越跳離最低點越遠。實務上，大家會試幾個不同的值，觀察損失曲線，挑一個下降得又快又穩的。

## Reader should understand

- 每一步往下坡移動的距離是學習率乘以斜率。
- 學習率太小也會到底，但要走非常多步。
- 學習率選得好時，一開始步伐大，接近底部時步伐變小。
- 學習率太大會跨過底部，可能來回跳動，甚至離最低點越來越遠。

## Interaction hints

- Pattern: a parameter slider with live output. The slider sets the learning rate; the page shows a bowl-shaped curve with the point and its path.
- Suggested model: f(x) = x^2 with the start at x = 4 and about 10 steps, so each step multiplies x by (1 - 2 x learning rate). With 0.01 the point barely moves (x is still about 3.3 after 10 steps). With 0.1 it falls smoothly. With 0.9 it jumps to the other side each step but still settles slowly. At 1.0 it bounces between 4 and -4 forever. Above 1.0 it climbs away.
- Slider range about 0.01 to 1.1. Label the zones "太小", "剛好" and "太大" and update a one-line status as the slider moves.
- Show the step count and the final position as text, so the key idea is readable before any interaction (start the slider at a good value such as 0.1).
- A "Reset" or "Run again" button is optional.
