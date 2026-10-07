# Interaction patterns

Pick the pattern that lets the reader do the thing the concept is about. One good interaction is better than many weak ones. Combine two patterns only when the concept has two parts.

| The concept is ... | Pattern |
| --- | --- |
| a process, an algorithm, a sequence of states | Step-through |
| a relation between a number and a result | Parameter slider |
| a structure made of parts or layers | Layer toggles |
| a question, a definition, extra detail | Reveal |

Rules for every pattern:

- Show the key idea before any interaction, in the first paragraph.
- The first state on load must already be meaningful (step 1, a default slider value, all layers on).
- Show the current state in words as well as in the picture (`Step 2 of 4`, the slider value).
- Use native controls. Do not build buttons from `<div>` elements.
- `render_check.py` clicks the first visible, enabled `<button>`. Make sure that this button changes the page. For example, put "Next" before "Back".

Each example below is a complete page that passes `page_check.py`. They use a short version of the skeleton in `design-baseline.md`.

## Step-through

Next and Back buttons move through a list of states. Keep the states as data and draw them with one `show()` function.

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
  #cells { display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0; list-style: none; }
  #cells li { min-width: 2.6rem; padding: 0.4rem; text-align: center; border: 2px solid var(--border); border-radius: 0.3rem; }
  #cells li.out { opacity: 0.35; }
  #cells li.mid { border-color: var(--accent); font-weight: bold; }
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
  let i = 0;
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
  next.addEventListener("click", () => { i += 1; show(); });
  back.addEventListener("click", () => { i -= 1; show(); });
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

`<details>` and `<summary>` hide an answer or extra detail until the reader asks. They need no script and work with the keyboard. Use them for "predict, then check" questions and for definitions.

For a tap detail on a word or a part of a picture, use a `<button aria-expanded="false">` that shows a short note next to it. Do not use hover only: phones and keyboards have no hover.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Predict, then check: binary search</title>
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
  <h1>Predict, then check: binary search</h1>
  <p>Binary search drops half of a sorted list at each check. Guess each answer, then open it.</p>
  <details>
    <summary>A sorted list has 1,000 values. How many checks are necessary at most?</summary>
    <p>10. Each check halves the range: 1,000, 500, 250 and so on, down to 1 value.</p>
  </details>
  <details>
    <summary>What happens if the list is not sorted?</summary>
    <p>The search can drop the half that holds the value. Then it reports "not found" for a value that is in the list.</p>
  </details>
</main>
</body>
</html>
```
