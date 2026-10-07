- Language: zh-TW
- Expected diagram type: `flowchart TD` with decisions

## Source

瀏覽器要載入檔案時，會先檢查本機快取有沒有這個檔案。沒有的話，就向伺服器下載。如果有，瀏覽器接著看它是否還新鮮：伺服器的回應若帶有 Cache-Control: max-age，只要還沒超過這段秒數，瀏覽器就直接使用快取，完全不連線。過期的快取不一定要丟掉。如果回應帶有 ETag，瀏覽器會送出附上 If-None-Match 的條件式請求，問伺服器檔案有沒有變。沒變的話，伺服器只回傳 304，不含內容，瀏覽器繼續使用快取。變了的話，伺服器回傳 200 和新內容，瀏覽器改用新的並更新快取。過期的快取若沒有 ETag，就只能重新下載。

## Reader should understand

- 瀏覽器先看快取裡有沒有檔案，再看它是否還在有效期限內。
- 還在有效期限內時，直接用快取，不需要連線到伺服器。
- 過期但有 ETag 時，瀏覽器先問伺服器；回應 304 就繼續用快取，回應 200 就換成新內容。
- 快取裡沒有檔案，或過期又沒有可用來驗證的標頭時，就重新下載。

## Diagram hints

- Expected type: `flowchart TD` with decision diamonds (the question is "which way does the browser go at each check").
- Key nodes (about 9): Request file; In cache?; Still fresh?; Use cache; Has ETag?; Ask server (If-None-Match); 304?; Download; Update cache.
- Three outcomes to make visible: use cache directly, revalidate then use cache (304), download (no cache, no validator, or 200 with new content).
- Decision labels in Traditional Chinese with short edge labels such as "是" and "否". Header names (ETag, 304) stay in English.
- The caption should point at the three exits and note that only the fresh path never contacts the server.
