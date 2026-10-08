- Language: en
- Output preset: `explainer` (16:9, 720p)
- Target length: 60–90 s, 4–6 scenes

## Source

Gradient descent is a way to find the input that makes a function as small as possible. Picture a hilly landscape in thick fog. You cannot see the lowest valley, but you can feel the slope under your feet. So you take a small step downhill, feel the slope again, and repeat. In a machine-learning model, the landscape is the loss: a number that says how wrong the model is. Your position is the set of model weights. The gradient tells you which direction is steepest uphill, so you move the weights the opposite way. The learning rate sets the step size. If it is too small, training takes forever. If it is too large, you overshoot the valley and bounce around, or even drift away. After many steps, the loss stops falling, and the weights settle near a low point.

## Viewer should understand

- The goal is to make a loss value (how wrong the model is) as small as possible by changing the weights.
- The gradient points uphill, so each step moves the opposite way, downhill.
- The learning rate controls the step size: too small is slow, too large overshoots or bounces.
- The process repeats until the loss stops improving, which may be a low point and not necessarily the lowest.

## Visual hints

- A 2D curve (a loss valley) with a dot that rolls downhill in steps, and a small arrow showing the slope.
- Side-by-side runs with a small and a large learning rate: a slow crawl versus bouncing across the valley.
- A loss-versus-steps line that falls and flattens.
