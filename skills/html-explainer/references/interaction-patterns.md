# Interaction patterns

A page has one section per key point. For each section, pick the pattern that lets the reader do the thing the point is about. Several patterns on one page are normal. A section can have no control when a picture and text show its point clearly.

| The point is ... | Pattern |
| --- | --- |
| a process, an algorithm, a sequence of states | Step-through |
| a relation between a number and a result | Parameter slider |
| a structure made of parts or layers | Layer toggles |
| a definition or extra detail | Reveal |
| a result the reader can guess first | Predict-then-reveal |
| a behavior that depends on the input (best case, worst case, edge case) | Preset scenarios |

Rules for every pattern:

- Show the point of the section before any interaction, in its first sentence.
- The first state on load must already be meaningful (step 1, a default slider value, all layers on).
- Show the current state in words as well as in the picture (`Step 2 of 4`, the slider value).
- Use native controls. Do not build buttons from `<div>` elements.
- When the point is about change, animate the state change with a CSS transition. Turn the transition off in a `prefers-reduced-motion: reduce` override.
- `render_check.py` clicks the first visible, enabled `<button>` on the page. Make sure that this button changes the page. For example, put "Next" before "Back".

Each example below is a complete page that passes `page_check.py`. They show the mechanics with plain styles; do not copy their look (see "Design" in `design-baseline.md`). On a real page, each example is one section.

## Step-through

Next and Back buttons move through a list of states. Play steps forward on a timer and stops at the last state. Keep the states as data and draw them with one `show()` function. A CSS transition lifts the current cell, so the reader sees the change happen.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Binary search, step by step</title>
<style>
  :root { --bg: #fff; --fg: #1a1a1a; --accent: #0b62c4; --panel: #eef1f5; --border: #c4cad3; color-scheme: light dark; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #121417; --fg: #e8eaed; --accent: #6fb1ff; --panel: #1f242b; --border: #3b424c; }
  }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 1rem/1.5 system-ui, sans-serif; }
  main { max-width: 42rem; margin: 0 auto; padding: 1rem; }
  button { font: inherit; padding: 0.4rem 0.9rem; background: var(--panel); color: var(--fg);
           border: 1px solid var(--border); border-radius: 0.4rem; }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  #cells { display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0.8rem 0 0; list-style: none; }
  #cells li { min-width: 2.6rem; padding: 0.4rem; text-align: center; border: 2px solid var(--border); border-radius: 0.3rem;
              transition: opacity 0.3s, transform 0.3s, border-color 0.3s; }
  #cells li.out { opacity: 0.35; text-decoration: line-through; }
  #cells li.mid { border-color: var(--accent); font-weight: bold; transform: translateY(-0.5rem); }
  @media (prefers-reduced-motion: reduce) {
    #cells li { transition: none; }
  }
</style>
</head>
<body>
<main>
  <h1>Binary search, step by step</h1>
  <p>Binary search checks the middle value and drops half of the list each time. A sorted list of 1,000 values needs 10 checks or fewer.</p>
  <ol id="cells" aria-label="Sorted list"></ol>
  <p id="count"></p>
  <p id="note" aria-live="polite"></p>
  <button type="button" id="next">Next</button>
  <button type="button" id="back">Back</button>
  <button type="button" id="play">Play</button>
</main>
<script>
  const values = [3, 8, 12, 17, 23, 31, 42, 56];
  const steps = [
    { lo: 0, hi: 7, mid: -1, text: "Find 42. The search range is the whole list." },
    { lo: 0, hi: 7, mid: 3, text: "The middle value is 17. 42 is larger, so drop the left half." },
    { lo: 4, hi: 7, mid: 5, text: "The middle value is 31. 42 is larger, so drop the left half again." },
    { lo: 6, hi: 7, mid: 6, text: "The middle value is 42. The search found it after 3 checks." }
  ];
  const list = document.getElementById("cells");
  const cells = values.map((v) => {
    const li = document.createElement("li");
    li.textContent = v;
    list.append(li);
    return li;
  });
  const next = document.getElementById("next");
  const back = document.getElementById("back");
  const play = document.getElementById("play");
  let i = 0;
  let timer = null;
  function show() {
    const s = steps[i];
    cells.forEach((c, k) => {
      c.classList.toggle("out", k < s.lo || k > s.hi);
      c.classList.toggle("mid", k === s.mid);
    });
    document.getElementById("count").textContent = `Step ${i + 1} of ${steps.length}`;
    document.getElementById("note").textContent = s.text;
    next.disabled = i === steps.length - 1;
    back.disabled = i === 0;
  }
  function stop() {
    clearInterval(timer);
    timer = null;
    play.textContent = "Play";
  }
  next.addEventListener("click", () => { stop(); i += 1; show(); });
  back.addEventListener("click", () => { stop(); i -= 1; show(); });
  play.addEventListener("click", () => {
    if (timer) { stop(); return; }
    if (i === steps.length - 1) { i = 0; show(); }
    play.textContent = "Pause";
    timer = setInterval(() => {
      i += 1;
      show();
      if (i === steps.length - 1) stop();
    }, 1200);
  });
  show();
</script>
</body>
</html>
```

## Parameter slider

An `<input type="range">` changes one number. An `<output>` shows the value and the result in words. Draw the result as bars or an inline SVG.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compound interest</title>
<style>
  :root { --bg: #fff; --fg: #1a1a1a; --accent: #0b62c4; --other: #8a5a00; --panel: #eef1f5; color-scheme: light dark; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #121417; --fg: #e8eaed; --accent: #6fb1ff; --other: #f0b44c; --panel: #1f242b; }
  }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 1rem/1.5 system-ui, sans-serif; }
  main { max-width: 42rem; margin: 0 auto; padding: 1rem; }
  input[type="range"] { width: 100%; accent-color: var(--accent); }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .track { background: var(--panel); border-radius: 0.3rem; margin: 0.2rem 0 0.8rem; }
  .bar { height: 1.2rem; border-radius: 0.3rem; }
  #compound { background: var(--accent); }
  #simple { background: var(--other); }
</style>
</head>
<body>
<main>
  <h1>Compound interest</h1>
  <p>With compound interest, the interest also earns interest. The gap to simple interest grows every year.</p>
  <label for="years">Years at 5% interest, starting with 1,000:</label>
  <input type="range" id="years" min="0" max="40" value="10">
  <p><output id="result" for="years"></output></p>
  <div>Compound interest</div>
  <div class="track"><div class="bar" id="compound"></div></div>
  <div>Simple interest</div>
  <div class="track"><div class="bar" id="simple"></div></div>
</main>
<script>
  const years = document.getElementById("years");
  const lang = document.documentElement.lang;
  const largest = 1000 * 1.05 ** 40;
  function show() {
    const n = Number(years.value);
    const compound = 1000 * 1.05 ** n;
    const simple = 1000 + 50 * n;
    const fmt = (x) => Math.round(x).toLocaleString(lang);
    document.getElementById("result").textContent =
      `After ${n} years: ${fmt(compound)} with compound interest, ${fmt(simple)} with simple interest.`;
    document.getElementById("compound").style.width = `${(compound / largest) * 100}%`;
    document.getElementById("simple").style.width = `${(simple / largest) * 100}%`;
  }
  years.addEventListener("input", show);
  show();
</script>
</body>
</html>
```

## Layer toggles

Checkboxes switch the parts of one picture on and off. Start with all layers on. Each checkbox toggles one class.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Layers of a web request</title>
<style>
  :root { --bg: #fff; --fg: #1a1a1a; --accent: #0b62c4; --border: #6b7480; color-scheme: light dark; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #121417; --fg: #e8eaed; --accent: #6fb1ff; --border: #8a94a1; }
  }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 1rem/1.5 system-ui, sans-serif; }
  main { max-width: 42rem; margin: 0 auto; padding: 1rem; }
  fieldset { display: flex; flex-wrap: wrap; gap: 0.3rem 1rem; border: 1px solid var(--border); }
  input { accent-color: var(--accent); }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .layer { border: 2px solid var(--border); border-radius: 0.4rem; padding: 0.5rem; margin-top: 0.4rem; }
  .layer > span { display: block; font-size: 0.9rem; }
  .layer.off { border-color: transparent; padding: 0; }
  .layer.off > span { display: none; }
  .payload { border: 2px dashed var(--accent); padding: 0.5rem; margin-top: 0.4rem; }
</style>
</head>
<body>
<main>
  <h1>Layers of a web request</h1>
  <p>Each layer wraps the one inside it with its own header. Only the innermost part is the request you wrote.</p>
  <fieldset>
    <legend>Show layers</legend>
    <label><input type="checkbox" value="ip" checked> IP</label>
    <label><input type="checkbox" value="tcp" checked> TCP</label>
    <label><input type="checkbox" value="tls" checked> TLS</label>
  </fieldset>
  <div class="layer" id="ip"><span>IP header: source and destination address</span>
    <div class="layer" id="tcp"><span>TCP header: ports and sequence number</span>
      <div class="layer" id="tls"><span>TLS record: encrypts what is inside</span>
        <div class="payload">HTTP request: GET /index.html</div>
      </div>
    </div>
  </div>
</main>
<script>
  document.querySelectorAll("fieldset input").forEach((box) => {
    box.addEventListener("change", () => {
      document.getElementById(box.value).classList.toggle("off", !box.checked);
    });
  });
</script>
</body>
</html>
```

## Reveal

`<details>` and `<summary>` hide a definition or extra detail until the reader asks. They need no script and work with the keyboard.

For a tap detail on a word or a part of a picture, use a `<button aria-expanded="false">` that shows a short note next to it. Do not use hover only: phones and keyboards have no hover.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Terms in binary search</title>
<style>
  :root { --bg: #fff; --fg: #1a1a1a; --accent: #0b62c4; --panel: #eef1f5; color-scheme: light dark; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #121417; --fg: #e8eaed; --accent: #6fb1ff; --panel: #1f242b; }
  }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 1rem/1.5 system-ui, sans-serif; }
  main { max-width: 42rem; margin: 0 auto; padding: 1rem; }
  details { background: var(--panel); border-radius: 0.4rem; padding: 0.6rem 0.8rem; margin: 0.6rem 0; }
  summary { cursor: pointer; font-weight: bold; }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
</style>
</head>
<body>
<main>
  <h1>Terms in binary search</h1>
  <p>Binary search uses two terms: the search range and the middle value. Open a term to see its meaning.</p>
  <details>
    <summary>Search range</summary>
    <p>The part of the list that can still hold the value. Each check makes it half as long.</p>
  </details>
  <details>
    <summary>Middle value</summary>
    <p>The value in the center of the search range. The search compares it with the value it looks for.</p>
  </details>
</main>
</body>
</html>
```

## Predict-then-reveal

The reader picks an answer first. Then the page shows the correct answer and why. Use one button per answer. Mark the result with a word ("Correct", "Not correct") as well as a color.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guess first: binary search</title>
<style>
  :root { --bg: #fff; --fg: #1a1a1a; --accent: #0b62c4; --panel: #eef1f5; --border: #c4cad3;
          --done: #1b7a3a; --changed: #a04a00; color-scheme: light dark; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #121417; --fg: #e8eaed; --accent: #6fb1ff; --panel: #1f242b; --border: #3b424c;
            --done: #6fd38d; --changed: #ffb26b; }
  }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 1rem/1.5 system-ui, sans-serif; }
  main { max-width: 42rem; margin: 0 auto; padding: 1rem; }
  .choices { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  button { font: inherit; padding: 0.4rem 0.9rem; background: var(--panel); color: var(--fg);
           border: 2px solid var(--border); border-radius: 0.4rem; }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  #answer { border-left: 4px solid var(--border); padding-left: 0.8rem; }
  #answer.right { border-color: var(--done); }
  #answer.wrong { border-color: var(--changed); }
</style>
</head>
<body>
<main>
  <h1>Guess first: binary search</h1>
  <p>Binary search drops half of a sorted list at each check. Guess the answer, then compare it with the result.</p>
  <p>A sorted list has 1,000 values. How many checks are necessary at most?</p>
  <div class="choices">
    <button type="button" data-guess="10">10</button>
    <button type="button" data-guess="100">100</button>
    <button type="button" data-guess="500">500</button>
  </div>
  <p id="answer" aria-live="polite">Pick an answer.</p>
</main>
<script>
  const answer = document.getElementById("answer");
  document.querySelectorAll("[data-guess]").forEach((b) => {
    b.addEventListener("click", () => {
      const right = b.dataset.guess === "10";
      answer.className = right ? "right" : "wrong";
      answer.textContent = (right ? "Correct. " : `Not correct: ${b.dataset.guess}. `) +
        "The answer is 10. Each check halves the range: 1,000, 500, 250 and so on, down to 1 value.";
    });
  });
</script>
</body>
</html>
```

## Preset scenarios

Buttons load a prepared input: the best case, the worst case and an edge case. The page runs the same code on each input and shows the result. Mark the loaded preset with `aria-pressed` and a visible style. Load a preset on start that is not the first button, so the first button changes the page.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Insertion sort: best and worst case</title>
<style>
  :root { --bg: #fff; --fg: #1a1a1a; --accent: #0b62c4; --panel: #eef1f5; --border: #c4cad3; color-scheme: light dark; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #121417; --fg: #e8eaed; --accent: #6fb1ff; --panel: #1f242b; --border: #3b424c; }
  }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 1rem/1.5 system-ui, sans-serif; }
  main { max-width: 42rem; margin: 0 auto; padding: 1rem; }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  button { font: inherit; padding: 0.4rem 0.9rem; background: var(--panel); color: var(--fg);
           border: 2px solid var(--border); border-radius: 0.4rem; }
  button[aria-pressed="true"] { border-color: var(--accent); font-weight: bold; }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  #list { display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0; list-style: none; }
  #list li { min-width: 2.4rem; padding: 0.3rem; text-align: center; border: 2px solid var(--border); border-radius: 0.3rem; }
  .track { background: var(--panel); border-radius: 0.3rem; }
  #bar { height: 1.2rem; border-radius: 0.3rem; background: var(--accent); transition: width 0.4s; }
  @media (prefers-reduced-motion: reduce) {
    #bar { transition: none; }
  }
</style>
</head>
<body>
<main>
  <h1>Insertion sort: best and worst case</h1>
  <p>Insertion sort is fast on a list that is almost sorted and slow on a reversed list. Load a list to compare.</p>
  <div class="row">
    <button type="button" data-preset="best">Best case: sorted</button>
    <button type="button" data-preset="worst">Worst case: reversed</button>
    <button type="button" data-preset="edge">Edge case: one pair swapped</button>
    <button type="button" data-preset="mixed">Mixed order</button>
  </div>
  <ol id="list" aria-label="Input list"></ol>
  <p id="result" aria-live="polite"></p>
  <div class="track"><div id="bar"></div></div>
</main>
<script>
  const presets = {
    best: [1, 2, 3, 4, 5, 6, 7, 8],
    worst: [8, 7, 6, 5, 4, 3, 2, 1],
    edge: [1, 2, 3, 5, 4, 6, 7, 8],
    mixed: [5, 2, 7, 1, 8, 3, 6, 4]
  };
  const most = 28;
  function comparisons(input) {
    const a = [...input];
    let count = 0;
    for (let i = 1; i < a.length; i += 1) {
      let j = i;
      while (j > 0) {
        count += 1;
        if (a[j - 1] <= a[j]) break;
        [a[j - 1], a[j]] = [a[j], a[j - 1]];
        j -= 1;
      }
    }
    return count;
  }
  const buttons = document.querySelectorAll("[data-preset]");
  function load(name) {
    const input = presets[name];
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.preset === name)));
    document.getElementById("list").replaceChildren(...input.map((v) => {
      const li = document.createElement("li");
      li.textContent = v;
      return li;
    }));
    const n = comparisons(input);
    document.getElementById("result").textContent = `Insertion sort needs ${n} comparisons for this list of 8 values.`;
    document.getElementById("bar").style.width = `${(n / most) * 100}%`;
  }
  buttons.forEach((b) => b.addEventListener("click", () => load(b.dataset.preset)));
  load("mixed");
</script>
</body>
</html>
```

## Combine patterns on one page

- Give each key point its own `<section>` with an `<h2>` that states the point. Put the main conclusion in the lead, above the first section.
- Choose the pattern per section. One page can have a step-through, a slider and a predict-then-reveal.
- Keep the state of each section in its own variables and its own `show()` function. Give each element a unique `id`, for example `bs-next` and `sort-next`.
- Use the same term for one thing in every section.
- The first button on the page belongs to the first interactive section. Make it change the page.
