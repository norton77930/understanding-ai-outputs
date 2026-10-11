- Language: zh-TW
- Intended interaction: sliders (prevalence, false-positive rate) with a population grid

## Source

一種疾病的檢驗結果是陽性，不代表這個人一定有病。假設一萬人裡有 1% 的人有病，也就是 100 人。檢驗能抓出 90% 的病人，所以 100 人裡有 90 人是陽性。可是沒病的 9,900 人裡，檢驗也會誤判 5% 為陽性，大約 495 人。全部陽性一共 585 人，其中真的有病的只有 90 人，大約 15%。也就是說，檢驗結果是陽性時，有病的機率只有大約 15%，不是 90%。關鍵在於沒病的人非常多，就算誤判率不高，誤判的人數也會超過真正的病人。如果疾病比較常見，例如 10% 的人有病，陽性的人裡真的有病的比例會提高到大約 67%。

## Reader should understand

- 檢驗會漏掉一部分病人，也會把一部分沒病的人誤判成陽性。
- 疾病很少見時，誤判的陽性人數可能比真正有病的陽性人數還多。
- 所以陽性結果代表有病的機率，可能遠低於檢驗本身的準確率。
- 疾病越常見，陽性結果代表有病的機率就越高。

## Interaction hints

- Pattern: parameter sliders for prevalence (0.1% to 30%), detection rate and false-positive rate, with a grid of dots for the population (for example 1,000 or 10,000 people grouped) colored by true positive, false positive, false negative and true negative.
- Show the result as counts and as one sentence: "陽性的人裡，真的有病的比例是 15%".
- Predict-then-reveal: before showing the answer, ask the reader to guess the chance at 1% prevalence (most people guess near 90%).
- Suggested check values: prevalence 1%, detection 90%, false positive 5% gives 90 / 585 ≈ 15.4%; prevalence 10% gives 900 / 1,350 ≈ 66.7%.
