# OpenAver Windows 疑難排解

> 💡 如果您使用上方推薦的**一行安裝**，以下步驟通常不需要。本文件僅適用於手動 ZIP 安裝。

---

## 升級注意事項（ZIP 手動安裝）

覆蓋安裝可能殘留舊版 Python 套件，導致啟動失敗。**升級前請先刪除 `python` 資料夾**：

- **Windows**: 刪除 `%USERPROFILE%\OpenAver\python\`

刪除後重新解壓新版 ZIP，再雙擊 `OpenAver.bat` 啟動。

---

## Windows 程式無法啟動 / 閃退

**原因**: Windows Mark of the Web 封鎖了從網路下載的執行檔。

**解法**:
1. 對下載的 ZIP 點擊 **右鍵** → **內容**
2. 勾選 **「解除封鎖 (Unblock)」** → 確定
3. 重新解壓縮並執行 `OpenAver.bat`

*或者使用 7-Zip 解壓縮，通常可避開此問題。*

**啟動腳本**:
- `OpenAver.bat` — 正常啟動
- `OpenAver_Debug.bat` — 調試版本（顯示詳細日誌），日誌檔案：`%USERPROFILE%\OpenAver\logs\debug.log`

---

## 介面顯示異常 / 空白

**原因**: 缺少 WebView2 Runtime（常見於 Windows 10 或虛擬機）。

**解法**: 下載並安裝 [Microsoft Edge WebView2 Runtime](https://go.microsoft.com/fwlink/p/?LinkId=2124703)。

---

## 回報問題

**回報時請附上**: 問題描述、重現步驟、OS 版本、日誌檔案（執行 `OpenAver_Debug.bat` 取得）。

| 管道 | 適用情境 |
|------|----------|
| [GitHub Issues](https://github.com/slive777/OpenAver/issues) | Bug 回報、功能建議 |
| [Telegram 群組](https://t.me/+J-U2l96gv0FjZTBl) | 隱私敏感問題、截圖/影片直傳 |
