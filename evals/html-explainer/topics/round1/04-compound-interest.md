- Language: zh-TW
- Intended interaction: sliders (years and annual rate)

## Source

複利是指利息也會再生利息。假設你存入本金 P 元，年利率是 r，每年結算一次，而且利息留在帳戶裡。一年後，帳戶有 P×(1+r) 元；第二年是拿這個新金額再乘以 (1+r)。所以 n 年後的金額是 A = P×(1+r)^n。例如存一萬元，年利率 5%，十年後約有 16,289 元。如果是單利，只有本金生利息，十年後只有 15,000 元，兩者差 1,289 元。年數越長，差距越大：二十年後，複利約 26,533 元，單利是 20,000 元。利率也有很大的影響：同樣十年，年利率 7% 約變成 19,672 元。這個算法假設利率固定，也不計手續費和稅金。

## Reader should understand

- 複利是利息也會再生利息，所以每年的成長都建立在更大的金額上。
- n 年後的金額是 A = P×(1+r)^n。
- 年數越長，複利和單利的差距越大。
- 利率只高一點，長期下來的結果就差很多。

## Interaction hints

- Pattern: parameter sliders with live output. One slider for years (1 to 40), one for the annual rate (1% to 10%). The principal is fixed at 10,000 (an optional number input is fine).
- Show a chart (inline SVG or canvas) with two lines: compound growth and simple interest (P x (1 + r x n)). The final amounts appear as text next to the chart.
- Check values for the default view: 10,000 at 5% for 10 years gives 16,289 (simple: 15,000). At 20 years it gives 26,533 (simple: 20,000). At 7% for 10 years it gives 19,672. At 7% for 30 years it gives 76,123.
- Show the formula A = P x (1 + r)^n with the current numbers filled in. Start the sliders at 5% and 10 years so the key idea is readable before any interaction.
- Assumptions to state on the page: annual compounding, a fixed rate, no fees or tax. Keep the text in Traditional Chinese (Taiwan wording).
