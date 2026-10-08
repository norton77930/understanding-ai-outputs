- Language: zh-TW
- Output preset: `youtube` (16:9, 1080p)
- Target length: 90–120 s, 5–8 scenes

## Source

在 Git 裡，merge 和 rebase 都能把一個分支的修改整合進另一個分支，但留下的歷史不一樣。假設 main 和 feature 兩個分支從同一個提交分開，各自又有了新的提交。merge 會建立一個新的合併提交，同時指向兩邊的最新提交。原本的提交都不會變，缺點是圖會愈來愈分岔。rebase 則把 feature 的提交一個一個拿起來，接到 main 最新的提交後面，歷史看起來就像一直線。但這些提交會被重新建立，雜湊值也跟著改變。所以已經推送、別人也在用的分支，不要隨便 rebase，否則同事的紀錄會對不上。準則是：自己的本地分支可以 rebase 來整理，共用的分支用 merge。

## Viewer should understand

- 兩個指令都能把一個分支的修改整合進另一個分支,但留下的歷史不一樣。
- merge 會新增一個有兩個父提交的合併提交,原本的提交都不變。
- rebase 把 feature 的提交依序接到 main 最新的提交後面,歷史變成一直線,但這些提交是重新建立的(雜湊值改變)。
- 已推送、別人也在用的共用分支不要 rebase;自己的本地分支可以 rebase,共用分支用 merge。

## Visual hints

- A commit graph drawn as dots and lines: the same starting state, then two different results (a diamond with a merge commit versus a straight line).
- Feature commits lifting off and landing after main's tip, with their labels changing from A to A'.
- A warning marker appearing on a shared remote branch.
