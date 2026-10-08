- Language: zh-TW
- Intended interaction: predict-then-reveal plus a repeated simulation

## Source

蒙提霍爾問題是一個機率遊戲。台上有三扇門，一扇門後面是汽車，另外兩扇後面是山羊。你先選一扇門。主持人知道汽車在哪裡，他會從你沒選的兩扇門裡，打開一扇有山羊的門。接著他問你：要不要換到剩下那扇沒開的門？很多人覺得剩兩扇門，換不換都是一半一半。其實換門贏的機率是三分之二，不換只有三分之一。原因是你第一次選中汽車的機率只有三分之一；如果你一開始選到山羊（機率三分之二），主持人只能打開另一扇山羊門，剩下那扇一定是汽車。重複玩很多次，換門的勝率會越來越接近三分之二。

## Reader should understand

- 主持人知道汽車在哪裡，而且一定打開一扇有山羊的門。
- 第一次選中汽車的機率是三分之一，所以不換門的勝率是三分之一。
- 第一次選到山羊時，換門一定會贏，所以換門的勝率是三分之二。
- 重複很多次之後，實際的勝率會接近理論值。

## Interaction hints

- Pattern: predict-then-reveal (ask "switch or stay?" and the reader's guess of the win rate), then a playable round: pick a door, the host opens a goat door, choose switch or stay, see the result.
- Add a simulation: buttons that play 10, 100 or 1000 rounds for "always switch" and "always stay", with running win rates shown as numbers and bars.
- A case table or tree of the three first picks (car, goat 1, goat 2) shows why switching wins in two of three cases.
- Suggested check values: after many rounds, switch about 66.7%, stay about 33.3%.
