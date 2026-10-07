- Language: zh-TW
- Output preset: `youtube` (16:9, 1080p)
- Target length: 90–120 s, 5–8 scenes

## Source

在 Git 裡，merge 和 rebase 都能把一個分支的修改整合進另一個分支，但留下的歷史不一樣。假設 main 和 feature 兩個分支從同一個提交分開，各自又有了新的提交。merge 會建立一個新的合併提交，同時指向兩邊的最新提交。原本的提交都不會變，缺點是圖會愈來愈分岔。rebase 則把 feature 的提交一個一個拿起來，接到 main 最新的提交後面，歷史看起來就像一直線。但這些提交會被重新建立，雜湊值也跟著改變。所以已經推送、別人也在用的分支，不要隨便 rebase，否則同事的紀錄會對不上。準則是：自己的本地分支可以 rebase 來整理，共用的分支用 merge。

## Viewer should understand

- Both commands bring one branch's work into another, but they leave a different history.
- Merge adds a new merge commit with two parents and keeps the original commits unchanged.
- Rebase replays the feature commits on top of the latest main, giving a straight line but creating new commits (new hashes).
- Do not rebase shared, already-pushed branches; rebase local personal branches, and merge shared ones.

## Visual hints

- A commit graph drawn as dots and lines: the same starting state, then two different results (a diamond with a merge commit versus a straight line).
- Feature commits lifting off and landing after main's tip, with their labels changing from A to A'.
- A warning marker appearing on a shared remote branch.
