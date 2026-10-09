- Language: zh-TW
- Expected diagram type: `stateDiagram-v2`

## Source

一個 pull request（PR）從建立到結束，會經過幾個狀態。通常先以草稿（draft）開啟，表示程式還沒寫完，還不需要別人審查。作者完成後，把它標成可審查，狀態就變成開啟中，審查者開始看程式。審查者可以要求修改，這時作者推送新的提交，PR 回到開啟中，重新審查。如果審查者核准，而且自動檢查都通過，就可以合併。合併後，變更進入主分支，PR 就結束了，不能再重新開啟。另一條路是關閉：作者或維護者認為不需要這個變更時，可以不合併就直接關閉。已關閉但沒有合併的 PR 可以重新開啟。

## Reader should understand

- PR 通常從草稿開始，標成可審查之後才進入開啟中。
- 審查者要求修改時，作者推送新的提交，PR 回到開啟中再審查。
- 核准且檢查通過之後才能合併，合併後的 PR 就結束了，不能重新開啟。
- PR 也可以不合併就關閉，已關閉的 PR 可以重新開啟。

## Diagram hints

- Expected type: `stateDiagram-v2` (the question is "what states does one thing pass through").
- Key states (about 6): Draft, Open, Changes requested, Approved, Merged, Closed. Start arrow into Draft; Merged is a final state.
- Key transitions: Draft to Open (mark ready); Open to Changes requested (review asks for changes); Changes requested to Open (new commits pushed); Open to Approved; Approved to Merged; Draft or Open to Closed; Closed to Open (reopen). Merged has no way back.
- Labels in Traditional Chinese, at most about 10 characters each.
- The caption should point at the two ends: the only way to Merged is through Approved, and Merged cannot reopen, while Closed can.
