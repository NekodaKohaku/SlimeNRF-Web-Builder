# SlimeNRF 網頁固件產生器（引腳配置器版）

一個給**不懂 GitHub 的一般使用者**用的線上固件產生器。使用者在網頁上選模組、選 tracker/dongle、指定自己板子上每支腳接什麼（IMU、LED、INT…），按一下就會在 GitHub Actions 上依這些腳位**動態生成 board overlay**、編譯出專屬固件並提供下載。

## 三塊怎麼串起來

```
使用者瀏覽器（引腳配置器）
   │  ①選模組 + 指定腳位 → POST 設定
   ▼
Cloudflare Worker（保管 GitHub 鑰匙 / GitHub App）
   │  ②觸發編譯
   ▼
GitHub Actions（build-single.yml）
   │  ③依腳位生成 overlay → 編一個固件 → 建立 release「fw-<編號>」並上傳
   ▼
Worker 查 release 狀態 → 網頁顯示下載連結
```

- **網站** 放 GitHub Pages（免費）
- **Worker** 放 Cloudflare（免費）
- **編譯** 跑 GitHub Actions（公開 repo 免費）

## 檔案結構

```
.github/workflows/build-single.yml   編譯引擎：收 JSON 設定 → 生成 overlay → 編譯
.github/scripts/gen_overlay.py       依腳位生成 Zephyr board overlay
web/index.html                       引腳配置器網頁
web/modules.json                     模組目錄（腳位池、基底 board、SDK 資訊）→ 要加模組改這裡
worker/worker.js                     Cloudflare Worker（後台，保管鑰匙）
worker/wrangler.toml                 Worker 設定
web/boards.json                      （已停用，可刪）
```

> 運作原理：MS88SF2 本質是「自訂腳位的 nRF52840 + USB」，所以用官方相近的 `promicro_uf2/nrf52840` 當基底 board，再把使用者指定的腳位生成 overlay 疊上去覆寫（pinctrl、cs-gpios、zephyr,user 等）。這樣不必為每塊自製板手寫完整 board 定義。

---

## 部署步驟

### 步驟 1：建立你自己的 GitHub repo
把這整個資料夾的內容放進一個新的 GitHub repo（例如 `slimenrf-web-builder`），推上去。

### 步驟 2：建立 GitHub App
用 App（而不是個人 token）好處是：權限只綁在你指定的 repo，而且 Worker 每次換出來的權杖一小時就過期，外洩傷害有限。

1. GitHub → **Settings → Developer settings → GitHub Apps → New GitHub App**。
2. 基本欄位：
   - **GitHub App name**：隨便取一個唯一名稱。
   - **Homepage URL**：填你的 GitHub Pages 網址或 repo 網址皆可。
   - **Webhook**：把 **Active** 取消勾選（本專案用不到）。
3. **Repository permissions** 給：
   - `Actions` → **Read and write**（觸發編譯要用）
   - `Contents` → **Read and write**（建立 release / 上傳固件要用）
4. **Where can this GitHub App be installed?** 選 **Only on this account**。
5. 按 **Create GitHub App**。建立後：
   - 記下頁面上的 **App ID**（數字）。
   - 往下捲到 **Private keys → Generate a private key**，會下載一個 `.pem` 檔（只會給一次，保管好）。
6. 左側 **Install App** → 安裝到你的帳號 → 選 **Only select repositories** → 選你這個 repo → Install。
7. 取得 **Installation ID**：安裝完成後看網址列，
   `https://github.com/settings/installations/【這串數字就是 Installation ID】`。

**把私鑰轉成 PKCS#8 格式**（Cloudflare 的 Web Crypto 只吃這種）。GitHub 下載的是 PKCS#1，用 openssl 轉一次：

```bash
openssl pkcs8 -topk8 -inform PEM -outform PEM -nocrypt \
  -in 你下載的私鑰.pem -out app-key-pkcs8.pem
```

轉出來的 `app-key-pkcs8.pem`（開頭是 `-----BEGIN PRIVATE KEY-----`）等下要貼給 Worker。

### 步驟 3：部署 Cloudflare Worker
先安裝 Node.js，然後在 `worker/` 資料夾裡：

```bash
cd worker
npx wrangler login    # 用瀏覽器登入 Cloudflare
# 編輯 wrangler.toml：填入 GITHUB_APP_ID、GITHUB_INSTALLATION_ID、GITHUB_REPO、ALLOWED_ORIGIN

# 貼上步驟 2 轉好的 PKCS#8 私鑰全文（可用 < 直接餵檔案）
npx wrangler secret put GITHUB_APP_PRIVATE_KEY < app-key-pkcs8.pem

npx wrangler deploy
```

部署完會給你一個網址，例如 `https://slimenrf-web-builder.你的名稱.workers.dev`，記下來。

（選用）要開啟防濫用的 rate limit：
```bash
npx wrangler kv namespace create RATE_LIMIT
# 把回傳的 id 填進 wrangler.toml 並取消該段註解，再 deploy 一次
```

### 步驟 4：設定網站並開啟 GitHub Pages
1. 編輯 `web/index.html`，把最上面的 `WORKER_URL` 改成步驟 3 的 Worker 網址。
2. GitHub repo → **Settings → Pages**，Source 選你的分支、資料夾選 `/web`（或把 web 內容放到 repo 根目錄）。
3. 等幾分鐘，GitHub 會給你網站網址，例如 `https://你的名稱.github.io/slimenrf-web-builder/`。
4. 回到 `worker/wrangler.toml` 把 `ALLOWED_ORIGIN` 設成這個網址（只到網域，不含路徑），再 `npx wrangler deploy` 一次。

### 步驟 5：測試
打開你的 GitHub Pages 網址 → 選模組、指定腳位 → 按「產生固件」→ 等 3–8 分鐘 → 出現下載連結。
可同時在 repo 的 **Actions** 分頁看到編譯進度（含生成的 overlay）、在 **Releases** 看到產出的 `fw-xxxx`。

---

## 加 / 改模組

編輯 `web/modules.json`，每個模組一筆：

```json
{
  "id": "MS88SF2",
  "label": "顯示在選單的名稱",
  "supported": true,
  "mcu": "nrf52840",
  "has_usb": true,
  "fileformat": "uf2",
  "base_board": "promicro_uf2/nrf52840",
  "repository_url": "https://github.com/SlimeVR/SlimeVR-Tracker-nRF.git",
  "repository_revision": "main",
  "sdk_url": "https://github.com/nrfconnect/sdk-nrf.git",
  "sdk_revision": "v3.1-branch",
  "zephyr_sdk_version": "0.17.4",
  "receiver": { "repository_url": "...-Receiver.git", "repository_revision": "main" },
  "pins": ["P0.02", "P0.04", "..."],
  "analog_pins": ["P0.02", "P0.29"],
  "defaults": { "spi": { "sck": "P0.08", "...": "" }, "i2c": { "sda": "P0.06", "...": "" } }
}
```

`pins` 是這個模組拉出來、使用者可指定的 GPIO；`base_board` 用官方相近的板當基底；`defaults` 是每種匯流排的預設腳（使用者可改）。MS88SF2 的腳位已依 datasheet 填好。

---

## 重要提醒 / 已知限制

- **overlay 可能需要 1–2 次實測微調。** 本環境無法在此先跑完整 Zephyr 編譯（要幾分鐘且需 nRF SDK）。`gen_overlay.py` 是照官方 `promicro_uf2.dts` 的節點結構生成的，覆蓋 pinctrl / cs-gpios / zephyr,user / sw0；第一次用你的真實腳位編譯若失敗，Actions log 會顯示生成的 overlay 與錯誤，通常是某支腳的節點細節要調（例如 ADC 分壓、某 IMU 專屬設定）。把 log 給我就能快速修。
- **電池量測**：預設用 nRF 內部 VDDHDIV5（跟官方 ProMicro 一樣），不佔用 GPIO。若你的板子用外部分壓到 AIN 腳，需另外調 `battery-divider` 節點。
- **nRF54L15（ME54BS01）**：已在模組清單標「尚未支援」（無官方韌體、無 USB）。等官方發佈再啟用。
- **安全**：使用 **GitHub App**（權限只綁此 repo、權杖一小時過期），Worker 另做「只允許 github.com 來源」+ 腳位格式檢查。對外公開建議啟用 rate limit。私鑰只放 Cloudflare secret。
- **免費額度**：公開 repo 的 GitHub Actions 免費；私有 repo 每月有上限。

---

## 資料流欄位對照（給維護者）

| 欄位 | 網站 (index.html) | Worker | Workflow |
|---|---|---|---|
| 設定整包 | `collectConfig()` 組成物件 | `config` (JSON 字串) | `inputs.config` → jq / python 解析 |
| 腳位 | `pins:{sda,scl,sck,...}` | 格式驗證 `^P\d\.\d+$` | `gen_overlay.py` 生成 overlay |
| board 目標 | `board_target`（基底 + 匯流排） | 透傳 | `west build --board` |
| 唯一編號 | — | `crypto.randomUUID` → `build_id` | `inputs.build_id` |
| 狀態看板 | 輪詢 `/status` | 查 release `fw-<build_id>` | 建立/更新該 release（BUILDING/DONE/FAILED）|
| 下載 | `download_url` | release asset 的 `browser_download_url` | `gh release upload` |
