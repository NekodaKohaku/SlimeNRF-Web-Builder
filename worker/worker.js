/**
 * Cloudflare Worker —— 中間的「後台員工」（GitHub App 版）
 *
 * 職責：
 *   1. 用 GitHub App 私鑰即時簽出短效的 installation token（絕不外流到瀏覽器）
 *   2. 收到網站送來的板子設定 → 觸發 GitHub Actions 編譯
 *   3. 讓網站查詢編譯狀態 / 取得下載連結
 *   4. 用 KV 做簡單 rate limit，防止有人狂觸發燒掉你的額度
 *
 * 為什麼用 App 而不是 PAT：App 的權限只綁在你指定的 repo、
 * 換出來的 token 一小時就過期，就算外洩傷害也很有限。
 *
 * 需要在 Cloudflare 設定的環境變數 / 綁定（見 wrangler.toml 與 README）：
 *   GITHUB_APP_ID          (Var)    App 的 App ID（數字）
 *   GITHUB_INSTALLATION_ID (Var)    App 安裝到你 repo 後的 Installation ID（數字）
 *   GITHUB_APP_PRIVATE_KEY (Secret) App 私鑰，需先轉成 PKCS#8 PEM（見 README）
 *   GITHUB_REPO            (Var)    "你的帳號/你的repo"
 *   WORKFLOW_FILE          (Var)    workflow 檔名，預設 "build-single.yml"
 *   GIT_REF                (Var)    要觸發的分支，預設 "main"
 *   ALLOWED_ORIGIN         (Var)    允許呼叫的網站網址，例如 "https://myname.github.io"
 *   RATE_LIMIT             (KV, 選用) 綁定後才會啟用 rate limit
 */

const GITHUB_API = "https://api.github.com";

// installation token 的暫存（同一個 Worker 執行個體會沿用，避免每次都重簽）
let tokenCache = { token: null, exp: 0 };

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return cors(env, new Response(null, { status: 204 }));
    }

    try {
      if (url.pathname === "/build" && request.method === "POST") {
        return cors(env, await handleBuild(request, env));
      }
      if (url.pathname === "/status" && request.method === "GET") {
        return cors(env, await handleStatus(url, env));
      }
      return cors(env, json({ error: "not found" }, 404));
    } catch (err) {
      return cors(env, json({ error: String((err && err.message) || err) }, 500));
    }
  },
};

// ---------------------------------------------------------------------------
// 路由處理
// ---------------------------------------------------------------------------

async function handleBuild(request, env) {
  // 1) rate limit（每個 IP 每分鐘最多 3 次；需綁定 KV 才啟用）
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (env.RATE_LIMIT) {
    const key = `rl:${ip}`;
    const count = parseInt((await env.RATE_LIMIT.get(key)) || "0", 10);
    if (count >= 3) return json({ error: "太頻繁了，請稍後再試" }, 429);
    await env.RATE_LIMIT.put(key, String(count + 1), { expirationTtl: 60 });
  }

  // 2) 讀取並驗證設定
  const cfg = await request.json();
  const required = [
    "type", "board_target", "repository_url", "repository_revision",
    "sdk_url", "sdk_revision", "zephyr_sdk_version", "fileformat", "filename",
  ];
  for (const k of required) {
    if (!cfg[k]) return json({ error: `缺少欄位: ${k}` }, 400);
  }
  // 白名單：只允許已知來源網域，避免被拿去編任意 repo
  const allowedHosts = ["github.com"];
  for (const u of [cfg.repository_url, cfg.sdk_url]) {
    try {
      if (!allowedHosts.includes(new URL(u).host)) {
        return json({ error: `不允許的來源網址: ${u}` }, 400);
      }
    } catch {
      return json({ error: `無效的網址: ${u}` }, 400);
    }
  }
  // tracker：驗證腳位格式與必填腳
  if (cfg.type === "tracker") {
    const pins = cfg.pins || {};
    for (const [k, v] of Object.entries(pins)) {
      if (!/^P\d\.\d+$/.test(v)) return json({ error: `無效的腳位 ${k}: ${v}` }, 400);
    }
    if (!pins.int) return json({ error: "缺少 IMU INT 腳" }, 400);
    if (cfg.bus === "i2c" && (!pins.sda || !pins.scl)) return json({ error: "I2C 需 SDA/SCL" }, 400);
    if (cfg.bus === "spi" && (!pins.sck || !pins.mosi || !pins.miso || !pins.cs)) {
      return json({ error: "SPI 需 SCK/MOSI/MISO/CS" }, 400);
    }
  }

  // 3) 產生唯一編號並觸發 workflow
  const buildId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);

  const resp = await gh(
    env,
    `/repos/${env.GITHUB_REPO}/actions/workflows/${env.WORKFLOW_FILE || "build-single.yml"}/dispatches`,
    {
      method: "POST",
      body: JSON.stringify({
        ref: env.GIT_REF || "main",
        inputs: { config: JSON.stringify(cfg), build_id: buildId },
      }),
    }
  );

  if (resp.status !== 204) {
    const text = await resp.text();
    return json({ error: `觸發編譯失敗 (${resp.status}): ${text}` }, 502);
  }

  return json({ build_id: buildId, status: "queued" });
}

async function handleStatus(url, env) {
  const buildId = url.searchParams.get("build_id");
  if (!buildId || !/^[a-f0-9]{6,40}$/.test(buildId)) {
    return json({ error: "無效的 build_id" }, 400);
  }

  const tag = `fw-${buildId}`;
  const resp = await gh(env, `/repos/${env.GITHUB_REPO}/releases/tags/${tag}`);

  if (resp.status === 404) return json({ status: "queued" });
  if (!resp.ok) return json({ error: `查詢狀態失敗 (${resp.status})` }, 502);

  const release = await resp.json();
  const body = release.body || "";
  const asset = (release.assets || [])[0];

  if (asset) {
    return json({ status: "done", filename: asset.name, download_url: asset.browser_download_url });
  }
  if (body.includes("STATUS:FAILED")) return json({ status: "failed" });
  return json({ status: "building" });
}

// ---------------------------------------------------------------------------
// GitHub App 認證：JWT → installation token
// ---------------------------------------------------------------------------

async function getInstallationToken(env) {
  const now = Math.floor(Date.now() / 1000);
  if (tokenCache.token && tokenCache.exp - 60 > now) return tokenCache.token;

  const jwt = await makeAppJwt(env);
  const res = await fetch(
    `${GITHUB_API}/app/installations/${env.GITHUB_INSTALLATION_ID}/access_tokens`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${jwt}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "slimenrf-web-builder-worker",
      },
    }
  );
  if (!res.ok) {
    throw new Error(`取得 installation token 失敗 (${res.status}): ${await res.text()}`);
  }
  const data = await res.json();
  tokenCache = {
    token: data.token,
    exp: Math.floor(new Date(data.expires_at).getTime() / 1000),
  };
  return tokenCache.token;
}

async function makeAppJwt(env) {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "RS256", typ: "JWT" };
  const payload = { iat: now - 60, exp: now + 540, iss: String(env.GITHUB_APP_ID) };

  const enc = (obj) => b64url(new TextEncoder().encode(JSON.stringify(obj)));
  const signingInput = `${enc(header)}.${enc(payload)}`;

  const key = await importPkcs8(env.GITHUB_APP_PRIVATE_KEY);
  const sig = await crypto.subtle.sign(
    { name: "RSASSA-PKCS1-v1_5" },
    key,
    new TextEncoder().encode(signingInput)
  );
  return `${signingInput}.${b64url(new Uint8Array(sig))}`;
}

async function importPkcs8(pem) {
  const body = pem
    .replace(/-----BEGIN [^-]+-----/, "")
    .replace(/-----END [^-]+-----/, "")
    .replace(/\s+/g, "");
  const der = Uint8Array.from(atob(body), (c) => c.charCodeAt(0));
  return crypto.subtle.importKey(
    "pkcs8",
    der.buffer,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"]
  );
}

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------

async function gh(env, path, init = {}) {
  const token = await getInstallationToken(env);
  return fetch(`${GITHUB_API}${path}`, {
    ...init,
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "slimenrf-web-builder-worker",
      ...(init.headers || {}),
    },
  });
}

function b64url(bytes) {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function cors(env, resp) {
  const h = new Headers(resp.headers);
  h.set("Access-Control-Allow-Origin", env.ALLOWED_ORIGIN || "*");
  h.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  h.set("Access-Control-Allow-Headers", "Content-Type");
  return new Response(resp.body, { status: resp.status, headers: h });
}
