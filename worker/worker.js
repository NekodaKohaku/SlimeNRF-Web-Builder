const GITHUB_API = "https://api.github.com";

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

async function handleBuild(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (env.RATE_LIMIT) {
    const key = `rl:${ip}`;
    const count = parseInt((await env.RATE_LIMIT.get(key)) || "0", 10);
    if (count >= 3) return json({ error: "太頻繁了，請稍後再試" }, 429);
    await env.RATE_LIMIT.put(key, String(count + 1), { expirationTtl: 60 });
  }

  const cfg = await request.json();
  const required = [
    "type", "board_target", "repository_url", "repository_revision",
    "sdk_url", "sdk_revision", "zephyr_sdk_version", "fileformat", "filename",
  ];
  for (const k of required) {
    if (!cfg[k]) return json({ error: `缺少欄位: ${k}` }, 400);
  }
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

  if (cfg.repository_url && cfg.repository_revision) {
    const sha = await resolveRef(env, cfg.repository_url, cfg.repository_revision);
    if (sha) cfg.repository_revision = sha;
  }

  const buildId = await configHash(cfg);

  if (!cfg.force) {
    const rel = await gh(env, `/repos/${env.GITHUB_REPO}/releases/tags/fw-${buildId}`);
    if (rel.ok) {
      const r = await rel.json();
      const asset = (r.assets || []).find(a => /\.(hex|uf2)$/i.test(a.name));
      if (asset) {
        return json({ build_id: buildId, status: "done", cached: true, filename: asset.name, download_url: asset.browser_download_url });
      }
    }
  }

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
  const asset = (release.assets || []).find(a => /\.(hex|uf2)$/i.test(a.name));
  if (asset) return json({ status: "done", filename: asset.name, download_url: asset.browser_download_url });
  if ((release.body || "").includes("STATUS:FAILED")) return json({ status: "failed" });
  return json({ status: "building" });
}

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

async function resolveRef(env, repoUrl, ref) {
  const m = /github\.com\/([^/]+)\/([^/]+?)(?:\.git)?$/.exec(repoUrl);
  if (!m) return null;
  const res = await gh(env, `/repos/${m[1]}/${m[2]}/commits/${encodeURIComponent(ref)}`);
  if (!res.ok) return null;
  const d = await res.json();
  return d && d.sha ? d.sha : null;
}

function canonicalize(v) {
  if (Array.isArray(v)) return "[" + v.map(canonicalize).join(",") + "]";
  if (v && typeof v === "object") return "{" + Object.keys(v).sort().map(k => JSON.stringify(k) + ":" + canonicalize(v[k])).join(",") + "}";
  return JSON.stringify(v);
}
async function configHash(cfg) {
  const c = { ...cfg }; delete c.force; delete c.filename;
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalize(c)));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 12);
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
