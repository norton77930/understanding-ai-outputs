- Language: zh-TW
- Request: 把以下內容整理成一張總覽圖，一張圖看懂 Docker 映像和容器。
- Expected diagram type: `svg`

## Source

Docker 映像是一份唯讀的檔案系統範本，由好幾層堆起來。Dockerfile 的每一個指令（例如安裝套件、複製程式碼）會產生一層；建置時，沒改到的層會直接沿用快取，所以把很少變動的指令放前面、常變動的程式碼放後面，重新建置會快很多。容器是用映像跑起來的執行個體：Docker 在映像最上面加一層可寫入的層，程式在容器裡寫的檔案都放在這一層。同一個映像可以同時跑很多個容器，它們共用底下的唯讀層，只有各自的可寫入層不同。容器刪掉時，可寫入層也跟著消失；要保留資料，就要把資料放在掛載進去的磁碟區。映像可以推到映像倉庫，別台機器再拉下來使用。

## Reader should understand

- 映像由好幾層唯讀層組成，Dockerfile 的每個指令產生一層。
- 沒改到的層會沿用快取，所以少變動的指令要放前面。
- 容器是在映像上面加一層可寫入層；多個容器共用同一份唯讀層。
- 容器刪掉時可寫入層會消失，要保留資料就用磁碟區。

## Diagram hints

- Expected output: one overview sheet (hand-written SVG, 3-6 panels with letter tabs, title block, one legend).
- Likely panels: layer stack (image layers + writable layer), Dockerfile line to layer mapping (annotated code),
  cache reuse when one line changes, many containers on one image, image lifecycle (build, push, pull, run) as a small
  flow, volume vs writable layer (status table).
- Both arms get the same overview request.
