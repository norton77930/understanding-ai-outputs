- Language: zh-TW
- Intended interaction: step-through of inserts, slider or input for the load-factor threshold

## Source

雜湊表用一組「桶子」存資料。放一個鍵時，先算出它的雜湊值，再除以桶子數取餘數，決定放進哪個桶子。兩個鍵落到同一個桶子叫做碰撞，這時同一個桶子裡會串起好幾個鍵，查詢就要多比對幾次。為了讓碰撞不要太多，雜湊表會看「負載因子」，也就是鍵的數量除以桶子數。假設桶子有 8 個、門檻是 0.75：放到第 6 個鍵時，負載因子剛好 0.75，還不用動；放第 7 個鍵時會超過門檻，雜湊表就把桶子加倍成 16 個，並把所有的鍵重新算一次位置放進去。加倍這一次比較慢，但之後的查詢又會變快。

## Reader should understand

- 鍵的位置由雜湊值除以桶子數的餘數決定。
- 兩個鍵落到同一個桶子就是碰撞，碰撞越多查詢越慢。
- 負載因子是鍵的數量除以桶子數；8 個桶子、門檻 0.75 時，第 7 個鍵會讓它超過門檻。
- 超過門檻時桶子加倍，所有的鍵重新放一次；這一次慢，之後查詢變快。

## Interaction hints

- No named style: this topic checks that default pages do not regress after #55. The request is the default one.
- Pattern: step-through that inserts keys one by one into 8 buckets, shows collisions as chains, and shows the load
  factor; at the 7th key (7 / 8 = 0.875 > 0.75) the table doubles to 16 buckets and re-places every key.
- Check values: 6 keys → 0.75 (no resize); 7 keys → 0.875 (resize); after resize 7 / 16 = 0.4375.
