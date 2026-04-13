# OpenAver macOS 疑難排解

> 💡 如果您使用上方推薦的**一行安裝**，以下步驟通常不需要。本文件僅適用於手動 ZIP 安裝。

---

## 升級注意事項（ZIP 手動安裝）

覆蓋安裝可能殘留舊版 Python 套件，導致啟動失敗。**升級前請先刪除 `python` 資料夾**：

- **macOS**: 刪除 `~/OpenAver/python/`

刪除後重新解壓新版 ZIP，再執行 `./OpenAver.command` 啟動。

---

## macOS 無法開啟 / 安全性警告

**原因**: macOS Gatekeeper 阻擋未簽名的應用程式。

在終端機依序執行：
```bash
cd ~/Downloads/OpenAver
xattr -dr com.apple.quarantine .
./OpenAver.command
```

設定完成後，之後可直接雙擊 `OpenAver.command` 執行。

**啟動腳本**:
- `OpenAver.command` — 正常啟動
- `OpenAver_Debug.command` — 調試版本，日誌檔案：`~/OpenAver/logs/debug.log`

---

## 回報問題

**回報時請附上**: 問題描述、重現步驟、macOS 版本、日誌檔案（執行 `OpenAver_Debug.command` 取得）。

| 管道 | 適用情境 |
|------|----------|
| [GitHub Issues](https://github.com/slive777/OpenAver/issues) | Bug 回報、功能建議 |
| [Telegram 群組](https://t.me/+J-U2l96gv0FjZTBl) | 隱私敏感問題、截圖/影片直傳 |
