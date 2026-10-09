- Language: zh-TW
- Type: procedure

## Request

用 STE 解釋：如何為一個 Python 專案建立虛擬環境，並安裝專案需要的套件。

## Context

專案資料夾裡已經有 `requirements.txt`。讀者可能用 Windows（PowerShell），也可能用 macOS 或 Linux。

## Reader should understand

- 虛擬環境讓每個專案有自己的一組套件，不會影響其他專案，也不會影響系統的 Python。
- 第一步：在專案資料夾執行 `python -m venv .venv`，建立虛擬環境。
- 先啟用虛擬環境，再安裝套件：Windows（PowerShell）執行 `.venv\Scripts\Activate.ps1`，macOS 或 Linux 執行 `source .venv/bin/activate`；接著執行 `pip install -r requirements.txt`。
- 不要把 `.venv` 資料夾加入版本控制。其他人用 `requirements.txt` 在自己的電腦上重建環境。
