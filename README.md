<!-- OpenAver: free open-source desktop GUI JAV metadata scraper & manager.
No Docker, no CLI, one-line install (Windows/macOS). Scans folders already organized by
JavSP / EverAver / MDCX / Jellyfin / Emby and reuses their NFO + cover art without re-scraping.
A cover-wall browser built for how this genre is actually browsed — navigate by cover + tag,
actress as a first-class entity (profile cards, cup/age/height sort, cross-language alias).
8 built-in scrape sources (JavBus/Jav321/JavDB/DMM/D2Pass/HEYZO/FC2/AVSOX) plus optional
Metatube federation (30+ providers). Optionally exports NFO + cover art (poster/fanart) to
Jellyfin / Emby / Kodi. AI-operable REST API with capabilities manifest, 8,000+ tests, MIT license. -->

<h1 align="center">OpenAver</h1>

<p align="center">
  <strong>你的番號收藏，用封面逛、用女優找。</strong><br>
  Windows / Mac 裝好就能用，不用 Docker、用的時候不用打指令 · 以前整理好的片直接拿來逛，不必重新抓資料
</p>

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-0078D6.svg)
![GitHub Release](https://img.shields.io/github/v/release/slive777/OpenAver)
![Downloads](https://img.shields.io/github/downloads/slive777/OpenAver/total?color=success)
![Stars](https://img.shields.io/github/stars/slive777/OpenAver)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Tests](https://img.shields.io/github/actions/workflow/status/slive777/OpenAver/test.yml?label=tests%208%2C000%2B)

**[English](README_EN.md)** | 繁體中文

把放片的資料夾指給 OpenAver，它會做成一面封面牆。點封面看劇照和標籤，點女優看她的所有片，點標籤找同類。哪部片資料不全，按一下就從網路補上。

**已經整理過的片，不用重新抓資料。** 影片旁邊如果已經有資料檔（NFO，記著片名、女優、標籤的小檔案）和封面圖，掃描時直接讀進來，檔案原封不動。不管是 JavSP、EverAver、MDCX，還是 Jellyfin／Emby 整理的，都一樣。

**可以只用這一個，也可以跟電視上的播放軟體一起用。** 想在客廳看，整理時順便產出 Jellyfin／Emby／Kodi 要的資料檔和封面；不想裝那些，在 OpenAver 裡就能把收藏逛完。

**預設不改、不搬、不刪你的影片。** 補資料只會在影片旁邊新增資料檔和圖。只有你按「整理」，才會依你定的規則改名或搬家，而且絕不刪除。程式在你自己的電腦跑，不用註冊。

**100% 本地運行** — 不蒐集資料、不上傳任何檔案資訊，網路請求僅用於刮削公開元數據。

⚡ **[Live Demo → openaver.slive.uk](https://openaver.slive.uk/)**

*裡面只有 mecha 反派與虛構電影海報，零 NSFW。老闆從你身後走過也沒事。*

## 規格速覽

| 項目 | 內容 |
|------|------|
| **平台** | Windows 10/11 · macOS（Apple 晶片 M1 之後） |
| **安裝** | 一行指令或雙擊安裝，免 Docker；裝好後全程圖形介面 |
| **接手既有收藏** | 影片旁已有的資料檔（NFO）和封面圖直接讀，掃描不改你的檔 |
| **收藏瀏覽** | 封面牆逛影片，條件可疊加篩選；女優另有一面牆，可依罩杯／年齡／身高排序 |
| **手機平板** | 同 Wi-Fi 的手機／平板用瀏覽器就能逛；預設不對外，可設密碼 |
| **抓資料的來源** | 同時查 8 家（JavBus / Jav321 / JavDB / DMM / D2Pass / HEYZO / FC2 / AVSOX）；另 2 家備份站要手動點驗證；進階可接 Metatube，合計 30+ |
| **給播放軟體用** | 整理時可產出 Jellyfin / Emby / Kodi 要的 NFO 與封面；NAS 上的片不搬也能用 |
| **AI 操作** | Claude Code / Cursor 等 AI 工具可以直接下指令整理片庫 |
| **AI 翻譯** | Ollama（本地免費）/ Gemini / OpenAI 相容端點 |
| **授權** | MIT，100% 本機，無帳號、無雲端 |

## 截圖預覽

| 搜尋頁 | 女優收藏 |
|--------|---------|
| ![Search](docs/screenshots/home.png) | ![Actress](docs/screenshots/showcase-actress.png) |

<details>
<summary>更多截圖</summary>

| Search Demo | 女優搜尋 Gallery |
|-------------|------------------|
| ![Search Demo](docs/screenshots/demo2.gif) | ![Search](docs/screenshots/search-detail.png) |

| Showcase 影片模式 | Showcase 詳細 |
|-------------------|---------------|
| ![Grid](docs/screenshots/showcase-grid.png) | ![Detail](docs/screenshots/showcase-detail.png) |

</details>

---

## 安裝

### 一行安裝

**macOS**（打開「終端機」貼上）:
```bash
curl -fsSL https://raw.githubusercontent.com/slive777/OpenAver/main/install.sh | bash
```

**Windows**（打開 PowerShell 貼上）:
```powershell
irm https://raw.githubusercontent.com/slive777/OpenAver/main/install.ps1 | iex
```

> 💡 Windows 不想開 PowerShell：到 [Releases](https://github.com/slive777/OpenAver/releases/latest) 下載 `OpenAver-Windows-Setup.bat`，雙擊就是同一套安裝。

安裝指令會自動下載最新版、解除系統的安全限制、建立桌面捷徑（Windows），升級時保留你的設定。安裝畫面跟著系統語言走（繁中／簡中／日文／英文）。

### 手動下載 ZIP

從 [GitHub Releases](https://github.com/slive777/OpenAver/releases/latest) 下載：

| 平台 | 檔案 |
|------|------|
| **Windows x64** | `OpenAver-vX.X.X-Windows-x64.zip` |
| **macOS arm64** | `OpenAver-vX.X.X-macOS-arm64.zip` |

> ⚠️ 手動 ZIP 要多一步解除安全限制，見 ZIP 內附的疑難排解文件。macOS 只支援 Apple 晶片。

第一次打開會有新手導覽，帶你指定資料夾、按下「產生網頁」，不用先讀文件。

> 🐧 **Linux**：沒有官方安裝程式，但可以自己架成區網伺服器用瀏覽器操作，步驟見 [`docs/linux-server.md`](docs/linux-server.md)（需要命令列）。

---

## 三個頁面

OpenAver 只有三個主要頁面，照順序用就對了：

1. **📋 Scanner（掃描）**：把放片的資料夾加進來，按「產生網頁」。有資料檔的片直接入庫，缺資料的列出來，一鍵補完。
2. **🎬 Showcase（瀏覽）**：封面牆。逛收藏、篩選、看劇照、找相似、管理女優。
3. **🔍 Search（搜尋）**：新下載的片從這裡處理。拖進來，查資料，按「整理」改名搬到收藏。

---

## 核心功能

### 📋 Scanner：先把現有收藏接進來

- **認得別人整理過的東西**：影片旁有 `.nfo` 就讀它的片名、女優、標籤、片商、系列、日期。封面認同名圖、`-poster`／`-fanart` 後綴、資料夾裡的 `poster`／`fanart`／`cover`／`folder`，還有 NFO 裡寫的圖片路徑；`extrafanart/` 劇照夾一併讀。
- **掃描只讀不寫**：來源資料夾一個位元組都不動。
- **缺什麼補什麼**：掃完列出「缺 NFO」「缺封面」的片，一鍵從網路補齊。補完只填空的欄位，已有的資料不覆蓋；新增的 NFO 與封面放在影片旁，影片本身不動。
- **女優／標籤別名**：在畫面裡直接加別名，不用手改設定檔。搜尋時中日英同義詞自動展開（「女僕＝Maid＝メイド」），同一人的藝名與退休名收成一張卡。
- **來源順序自己排**：拖曳排出你偏好的來源順序（想要哪家的封面就排前面）；一鍵切「無碼模式」只用無碼來源。
- **搬檔時帶走字幕、保留 VR 標籤**：整理時同目錄的字幕檔跟著走；VR 檔名裡的投影標籤（`_180_LR`、`mkx200`）保留，Skybox / DeoVR / HereSphere 才認得。

### 🎬 Showcase：用封面逛、用女優找

**播放軟體用片名和資料夾找片；這裡用封面、標籤、女優。**

- **封面牆＋大圖**：點封面看劇照、標籤、女優資料。無碼片的封面自動對準人臉裁切，不會切掉半張臉；不滿意可以手動拖。
- **條件可以疊**：大圖裡點女優、標籤、片商、導演、系列，搜尋框就多一枚可按掉的條件，多枚同時存在時取交集。點出來的是精準比對（點「巨乳」不會撈到「巨乳痴女」），自己打字才是模糊比對。
- **橫式封面↔直式卡片一鍵切**：JAV 橫式封面的正面在右半邊，切成直式卡片一列放更多。只是畫面變形，不會多產生檔案。
- **女優模式**：女優自己一面牆。資料卡有身高、罩杯、三圍、年齡、別名歷史；可依罩杯／年齡／身高／片數排序，也能用「165 以下」「B 罩杯」直接篩。
- **從自己的片庫補女優牆**：按 `+` 就是一份「庫裡有誰、各幾片」的清單，別名自動合併成同一人，逐列點愛心加入。
- **相似探索**：大圖點魔杖，同類的片環繞主圖，點任一顆繼續往下鑽。純本機規則比對（標籤、系列、片商、女優），離線即時、免 GPU。
- **整理完馬上出現**：在 Search 整理成功的片，目標在掃描範圍內就直接飛進 Showcase，不必重掃。
- **連不到的位置會說**：片庫放 NAS 或外接碟，連不到時底部狀態列直接寫出是哪一個。
- **手機、平板也能逛**：設定裡一鍵切「伺服器」，同 Wi-Fi 的裝置用瀏覽器打開網址就能逛；用完切回「單機」立刻關閉對外。介面為觸控重做，封面可左右滑。

### 🔍 Search：新片從這裡進來

- **8 家一次查**：JavBus、Jav321、JavDB、DMM、D2Pass、HEYZO、FC2、AVSOX 同時查，結果自動比對片庫、標示已收藏。JavDB 走它官方 App 用的資料通道，被擋、安裝路徑含中日韓文字的情況大多也查得到，封面沒有浮水印。
- **拖檔案或資料夾進來**：自動認番號、批次查資料、拉封面和劇照。番號、女優名、系列、片商都能搜；UC / LEAK / 4K 這類版本自動變成標籤。
- **看完再整理**：查到的資料先看大圖（封面、劇照、演員、標籤），確認了才按「整理」改名、建資料夾、寫 NFO、下載封面。
- **書籤**：想看但還沒入手的片先收起來，封面當下存本機，原站掛了也不破圖。片子入庫後書籤自動消失。
- **定時整理**：「我的最愛」（你指定的下載完成資料夾）旁一顆開關，開著之後每 12 小時自動對那個資料夾跑一輪「查資料 → 整理」，人不必在場；也能按「立刻執行一次」。
- **進階重刮**：刮錯片或想換來源時，改番號、指定來源重抓，先看預覽再決定要不要覆蓋。

### 📀 唯讀來源：NAS 上的片不搬、不改，也能進播放軟體

想把 NAS、雲端掛載，或任何「不想被工具碰」的收藏掛進 Jellyfin／Emby／Kodi，又不想複製幾 TB 的原檔：把那個來源標成**唯讀**。

- **來源一個位元組都不動**：只讀。抓好的 NFO、封面、劇照全部寫到你指定的本地輸出夾。
- **`.strm` 直接餵播放軟體**：`.strm` 是一個只寫著「影片在哪裡」的小檔案，Emby / Jellyfin / Kodi 掃到就能直接播原檔，不用複製。
- **兩台電腦路徑不一樣也行**：OpenAver 這台看到的路徑跟播放軟體那台不一樣時（不同掛載點、Windows 網芳路徑 UNC、Windows 裡的 Linux 路徑 WSL），設一組替換規則自動改寫；改規則時既有的 `.strm` 一併更新。

### 🌐 AI 翻譯

- 日文片名一鍵翻成你的介面語言（繁中／簡中／英文）。
- 支援 **Ollama**（本地 GPU，免費）、**Gemini Flash**（有免費額度）、**OpenAI 相容端點**（OpenRouter 等）。

### ⚙️ Settings

- 四種語言即時切換（繁中／簡中／日文／英文）。
- 命名規則自己定：資料夾層級、檔名格式、變數，設定頁即時預覽結果。
- 「我的最愛資料夾」：指向下載器的已完成夾（不是女優收藏），Search 頁按「我的最愛」一鍵載入裡面全部影片。
- 播放軟體模式（選配）：選 Jellyfin / Emby / Kodi，整理時自動產出它們認得的 poster＋fanart 檔名與 NFO。（`{stem}-fanart` 只有 Jellyfin／Kodi 讀，Emby 不認。）
- 靜態 HTML 匯出：產生一個獨立的 HTML 檔，不開程式也能離線翻。

### 🔌 Metatube 聯邦（進階選配）

內建 8 家開箱即用。想要更多來源：在進階設定接上你自架的 [Metatube](https://github.com/metatube-community/metatube-sdk-go)，來源合計就有 **30+ 個社群維護的 provider**，無碼與小眾片商一次補強。Metatube 要自己架（Docker 或執行檔）；不啟用完全不影響預設體驗。

### 🤖 AI-Ready API

本機提供一份說明檔（capabilities manifest），AI 工具讀完就能自己串多個步驟，做那些人做起來瑣碎到放棄的事：

- **「幫我把片子最多的 top 20 女優加入收藏，跳過已收藏的。」**
  <sub>SQL 統計 → 查重 → 批次收藏 → 下載照片</sub>
- **「橋本ありな 跟 新ありな 是同一人而且退休了，幫我加 tag。」**
  <sub>建立別名 → 搜出兩個名字的所有片 → 批次加「引退」標籤</sub>
- **「這篇文章提到的番號，做成有封面的 HTML 頁面。」**
  <sub>解析番號 → 批次搜尋 → 下載封面 → 生成 Gallery HTML</sub>

一行 curl 讓 AI 自學所有端點（Port 在 Settings 頁的「AI API」區塊）：

```bash
curl http://localhost:<port>/api/capabilities
```

<details>
<summary>支援的 AI 工具 · 進階用法 · 玩家彩蛋</summary>

支援任何 function-calling 相容的 AI 工具：

| 使用方式 | 工具 | 說明 |
|----------|------|------|
| **CLI** | Claude Code, Codex CLI, Gemini CLI, Aider 等 | 終端機直接 `curl`，所有 CLI agent 皆支援 |
| **IDE** | Cursor, GitHub Copilot in VS Code, Windsurf, Trae 等 | Agent 模式呼叫本地 REST API |
| **桌面 App** | Codex App, Google Antigravity 2.0, Claude Cowork, OpenClaw | 不需開發環境，開箱即用 |

> 💡 對話內想看到封面：**Codex App（對話內嵌）** 或 **Google Antigravity 2.0（artifact 面板）** 兩款桌面 app 都能在對話中向你展示封面。

> ⚡ **小模型友善**：capabilities manifest 已針對輕量模型優化，Gemini Flash / GPT mini / Claude Haiku 皆可正確操作所有端點。

> 💻 **想讓 AI 預讀 repo、或自己擴充端點？** 所有端點定義在 [`web/routers/capabilities.py`](web/routers/capabilities.py)，AI agent clone repo 時會優先讀這個檔，不需要啟動服務就能學會所有工具。

> 🪄 **進階玩家彩蛋：FC2 自動找女優。** FC2 影片幾乎都沒女優標記，但其中不少是後來轉有碼出道的熟面孔（白上咲花就是經典案例）。SQL 撈 actress 為空的片 → DeepFace（RetinaFace + ArcFace）對 Gfriends 庫比對 → `POST /api/user-tags` 寫回標記。50 行 Python 一個週末跑完全庫，發現喜歡的手動加收藏；未識別素人 DBSCAN 自建群組下次直接配對。

</details>

---

## 常見問題（FAQ）

**從 JavSP、MDCX 或 EverAver 換過來，已經整理好的資料夾會怎樣？**
不用重刮，影片旁的資料檔（NFO）和封面會直接讀進來，已有的內容不會被覆蓋。把原資料夾加進 Scanner、按一次「產生網頁」就好。

**用 OpenAver 整理好的片，可以直接給 Jellyfin / Emby / Kodi 用嗎？**
可以。整理時一併產出它們要讀的 NFO 和封面圖（poster / fanart），影片留在原地，Jellyfin / Emby / Kodi 掃到那個資料夾就會正確顯示封面和資料。

**OpenAver 可以和 Jellyfin / Emby / Kodi 一起用嗎？**
可以一起用。OpenAver 負責找片、抓資料、用封面和女優逛收藏；它們負責在電視上播放。不裝它們也行，OpenAver 本身就能把收藏逛完。

**片子在 NAS 或雲端硬碟上，不想搬也不想被改，可以用嗎？**
可以，把那個資料夾設成「唯讀」，原檔不搬不改、不寫入任何東西，抓好的資料檔和封面另外放到本機輸出夾，還能產生 `.strm` 讓播放軟體直接串流原檔。NAS、掛載成磁碟的雲端硬碟、外接碟都適用。

**OpenAver 會搬移、改名或刪除我的檔案嗎？**
只有你主動按「整理」才會依你設定的規則搬移或重新命名影片檔，而且絕不刪除；目標位置已有同名檔會先提醒你。搜尋、瀏覽、掃描都是純讀取；補資料只在影片旁新增 NFO 與封面，影片本身不動。

**Mac 可以用嗎？要裝 Docker 嗎？**
Mac 可以用，限 Apple 晶片（M1 之後），一行指令或下載 ZIP 就裝好。不需要 Docker，Windows 與 Mac 都是桌面程式，裝好後用滑鼠操作。

**有沒有可以靠封面和女優找片、不用翻資料夾的 JAV 管理軟體？**
OpenAver 就是為這個做的：收藏做成封面牆，點封面看劇照和標籤，點女優看她的全部片子；檔名和資料夾不再是主要找片方式。

**電腦裡的片子可以用手機或平板逛嗎？**
可以，同一個 Wi-Fi 下在設定裡打開「伺服器」，手機瀏覽器打開那個網址就能逛；用完關掉，預設不會暴露到外網。

**如果內建的刮削來源（Scraper）失效了怎麼辦？**
內建 8 家來源彼此備援，一家暫時失效其他家會補上；JavDB 另有官方 App 用的資料通道，被擋時多半仍查得到。進階玩家可接自架的 Metatube 聯邦再擴 30+ 家，等於替片庫多買一份保險。

**官方站已經下架的片還查得到資料嗎？**
查得到，桌面版接了 JavLibrary 與 FC2-javten 兩個備份站。它們在 Cloudflare 人機驗證後面，OpenAver 選擇尊重它：會彈出一個真的瀏覽器視窗讓你手動點一次，之後自動重試回填。所以這兩家只支援桌面版的手動精確番號查詢，不參與批次搜尋、也不開放給 AI。

**可以讓 AI 工具操作 OpenAver 嗎？**
可以，本機提供一份說明檔（capabilities manifest），Claude Code、Cursor 等 AI 工具用一行 curl 讀完就能下指令整理片庫、批次收藏女優、加標籤。

**會收集隱私或上傳我的檔案嗎？**
不會上傳你的影片或片庫清單，也沒有帳號和遙測；連網只為了抓公開的片名、封面、女優資料。

**Windows 關閉視窗後可以在背景跑嗎？**
可以縮到右下角系統匣繼續跑，點圖示再打開。點右上角 X 時會問你要退出還是縮小，可勾「不再顯示」記住；之後到「設定 → 系統設定 → 關閉視窗時」調整。

---

## 開發者指南

<details>
<summary>技術架構 · 從原始碼執行 · 目錄結構 · 打包</summary>

### 技術架構

| 層級 | 技術 |
|------|------|
| **Backend** | FastAPI (Python 3.12) |
| **Frontend** | Jinja2 + DaisyUI + Tailwind CSS + Alpine.js 3.x + Fluent Design 2 |
| **Animation** | GSAP 3.14+ + Motion Adapter (reduced-motion support) |
| **Desktop** | PyWebView (Windows/macOS) |
| **Database** | SQLite (WAL mode) |
| **Testing** | Pytest (8,000+ tests) |

### 從原始碼執行

**前置需求**: Python 3.12（與打包版本一致）、Chrome/Edge、[WebView2 Runtime](https://go.microsoft.com/fwlink/p/?LinkId=2124703) (Windows 10/VM)

```bash
git clone https://github.com/slive777/OpenAver.git
cd OpenAver
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 開發模式 (Hot Reload)
uvicorn web.app:app --reload --reload-include 'locales/*.json' --host 127.0.0.1 --port 8000

# 桌面模式 (Windows)
python windows/launcher.py
```

### 執行測試

```bash
source venv/bin/activate
pytest
```

### 目錄結構

```
OpenAver/
├── web/                # Web GUI (FastAPI)
│   ├── routers/
│   │   ├── capabilities.py  # 🌟 AI Manifest — 所有端點的自描述定義（單檔全貌）
│   │   └── ...              # 其餘業務端點（search / scanner / scraper / actress / ...）
│   ├── templates/      # HTML Templates (DaisyUI + Fluent Design 2)
│   └── static/         # CSS/JS Assets (Modular JS, Theme CSS)
├── core/               # 核心邏輯
│   ├── scrapers/       # 模組化爬蟲 (JavBus/JavDB/Jav321/FC2/AVSOX/DMM/D2Pass/HEYZO + 手動來源 JavLibrary/FC2-javten)
│   ├── database/       # SQLite 資料層套件 (connection/video/actress/alias/tag_alias/migrate, WAL)
│   ├── metatube/       # Metatube 聯邦整合
│   ├── similar/        # 規則式相似片排序 (tag IDF + 系列/片商/女優)
│   ├── focal/          # 無碼封面人臉對焦裁切
│   ├── gallery_scanner.py    # 資料夾掃描入庫（讀既有 NFO/封面）
│   ├── organizer.py    # 檔案整理 + fallback 空值防護
│   ├── readonly_producer.py  # 唯讀來源 → NFO/封面/.strm 輸出
│   ├── path_utils.py   # 跨平台路徑處理 (file:// URI)
│   ├── i18n.py         # 多語系翻譯核心 (t() / fallback chain)
│   └── translate_service.py  # AI 翻譯 (Ollama/Gemini/OpenAI Compatible)
├── locales/            # 四語系 JSON (zh_TW/zh_CN/ja/en)
├── tests/              # 測試代碼 (Pytest)
└── windows/            # Windows 啟動器 (PyWebView)
```

### 打包應用程式

```bash
source venv/bin/activate
python build.py          # Windows
python build_macos.py    # macOS
```

</details>

---

## 疑難排解

> 💡 疑難排解請參閱打包版 ZIP 內附的「疑難排解」文件，或查看 [GitHub Wiki](https://github.com/slive777/OpenAver/wiki)。

---

## 社群與回報問題

加入 [Telegram 群組](https://t.me/+J-U2l96gv0FjZTBl) 與其他使用者交流討論！

| 管道 | 適用情境 |
|------|----------|
| [GitHub Issues](https://github.com/slive777/OpenAver/issues) | Bug 回報、功能建議、開發討論 |
| [Telegram 群組](https://t.me/+J-U2l96gv0FjZTBl) | 隱私敏感問題、截圖/影片直傳 |

**回報時請附上**: 問題描述、重現步驟、OS 版本、日誌檔案（執行 Debug 版啟動腳本取得）。

---

## 致謝

OpenAver 使用並感謝以下開源專案：

- **[FastAPI](https://fastapi.tiangolo.com/)** - 現代化的 Python Web 框架
- **[PyWebView](https://pywebview.flowrl.com/)** - 輕量級的跨平台桌面應用框架
- **[GSAP](https://gsap.com/)** - 高效能 JavaScript 動畫引擎
- **[DaisyUI](https://daisyui.com/)** - Tailwind CSS 元件庫
- **[Tailwind CSS](https://tailwindcss.com/)** - Utility-first CSS 框架
- **[Alpine.js](https://alpinejs.dev/)** - 輕量級 JavaScript 框架

完整的第三方套件版本與授權清單見 [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md)。

## License

MIT License

---

<details>
<summary>⚠️ 免責聲明</summary>

本專案僅供個人學習研究使用，請使用者遵守：
- 尊重網站服務條款
- 合理控制請求頻率
- 不用於商業目的

使用本專案造成的任何後果由使用者自行承擔。

</details>
