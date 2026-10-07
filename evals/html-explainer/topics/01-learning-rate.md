- Language: en
- Intended interaction: slider (learning rate)

## Source

Gradient descent finds a low point of a function by taking small steps downhill. At each step, the program measures the slope at the current point, then moves in the opposite direction. The learning rate is a number that scales each step: the new position is the old position minus the learning rate times the slope. If the learning rate is too small, every step is tiny, and the program needs very many steps to reach the bottom. If it is well chosen, the steps are large at first and shrink as the slope flattens, so the point settles into the minimum. If it is too large, one step can jump over the bottom and land higher up the other side. The point then bounces from side to side and may even climb away from the minimum. In practice, people try several values and watch the loss curve to pick one that falls quickly and steadily.

## Reader should understand

- Each step moves the point downhill by the learning rate times the slope.
- A learning rate that is too small reaches the bottom, but only after very many steps.
- A well-chosen learning rate gives big steps at first and smaller steps near the bottom.
- A learning rate that is too large overshoots the bottom and can bounce or move away from the minimum.

## Interaction hints

- Pattern: a parameter slider with live output. The slider sets the learning rate; the page shows a bowl-shaped curve with the point and its path.
- Suggested model: f(x) = x^2 with the start at x = 4 and about 10 steps, so each step multiplies x by (1 - 2 x learning rate). With 0.01 the point barely moves (x is still about 3.3 after 10 steps). With 0.1 it falls smoothly. With 0.9 it jumps to the other side each step but still settles slowly. At 1.0 it bounces between 4 and -4 forever. Above 1.0 it climbs away.
- Slider range about 0.01 to 1.1. Label the zones "too small", "good" and "too large" and update a one-line status as the slider moves.
- Show the step count and the final position as text, so the key idea is readable before any interaction (start the slider at a good value such as 0.1).
- A "Reset" or "Run again" button is optional.
