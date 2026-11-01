/* AnyDownloader Companion 1.1 — popup logic (MV3) */
const BRIDGE = "http://127.0.0.1:7272";

const statusEl = document.getElementById("status");
const sendBtn = document.getElementById("sendPage");
const openBtn = document.getElementById("openApp");
const openRow = document.getElementById("openRow");
const listEl = document.getElementById("mediaList");
const mediaSection = document.getElementById("mediaSection");
const emptyEl = document.getElementById("empty");
const helpEl = document.getElementById("help");
const qualitySel = document.getElementById("quality");

let currentUrl = null;
let currentTitle = "";

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "status" + (cls ? " " + cls : "");
}

async function loadQuality() {
  const { profile } = await chrome.storage.local.get("profile");
  if (profile && qualitySel.querySelector(`option[value="${profile}"]`)) {
    qualitySel.value = profile;
  }
}

qualitySel.addEventListener("change", () => {
  chrome.storage.local.set({ profile: qualitySel.value });
});

async function pingApp(timeoutMs = 2500) {
  try {
    const r = await fetch(BRIDGE + "/ping", { signal: AbortSignal.timeout(timeoutMs) });
    const d = await r.json();
    return d;
  } catch {
    return null;
  }
}

async function sendUrl(url, title) {
  const payload = JSON.stringify({ url, title, profile: qualitySel.value });
  let lastErr = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const r = await fetch(BRIDGE + "/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        signal: AbortSignal.timeout(8000),
      });
      if (r.ok) return;
      lastErr = new Error("app rejected: " + r.status);
    } catch (e) {
      lastErr = e;
      await new Promise((res) => setTimeout(res, 400));
    }
  }
  throw lastErr || new Error("send failed");
}

function flashSent(text) {
  const p = document.createElement("p");
  p.className = "sent";
  p.textContent = text;
  document.body.appendChild(p);
  setTimeout(() => window.close(), 1100);
}

/* ---- app running: send directly ---- */
sendBtn.addEventListener("click", async () => {
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending…";
  try {
    await sendUrl(currentUrl, currentTitle);
    flashSent("Sent to AnyDownloader ✓");
  } catch {
    sendBtn.textContent = "Failed — is the app still open?";
    setTimeout(() => {
      sendBtn.textContent = "⬇ Send this page to AnyDownloader";
      sendBtn.disabled = false;
    }, 1800);
  }
});

/* ---- app closed: launch via protocol, then wait for it ---- */
openBtn.addEventListener("click", async () => {
  openBtn.disabled = true;
  openBtn.textContent = "Starting AnyDownloader…";
  const link = "anydownloader://add?url=" + encodeURIComponent(currentUrl) +
               "&profile=" + encodeURIComponent(qualitySel.value);
  // The app picks the URL up from its command line on launch and starts
  // downloading by itself; here we just wait until it is reachable.
  window.location.href = link;
  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    const pong = await pingApp(1200);
    if (pong) {
      setStatus("app connected · v" + pong.version, "ok");
      flashSent("Sent to AnyDownloader ✓");
      return;
    }
    openBtn.textContent = `Starting AnyDownloader… (${(20 - i) * 1.5 | 0}s)`;
  }
  openBtn.textContent = "Couldn't reach the app";
  helpEl.hidden = false;
  setTimeout(() => {
    openBtn.disabled = false;
    openBtn.textContent = "🚀 Open AnyDownloader & download";
  }, 2000);
});

/* ---- find media on the page ---- */
async function activeTabMedia() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return [];
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const abs = (u) => {
          try { return new URL(u, location.href).href; } catch { return null; }
        };
        const found = new Map();
        const add = (url, kind) => {
          if (!url || !/^https?:/i.test(url)) return;
          if (found.has(url)) { found.get(url).kinds.add(kind); return; }
          found.set(url, { url, kinds: new Set([kind]), dur: null });
        };
        document.querySelectorAll("video, audio").forEach((el) => {
          const src = el.currentSrc || el.src || (el.querySelector("source") || {}).src;
          const a = abs(src);
          add(a, el.tagName.toLowerCase());
          if (a && Number.isFinite(el.duration)) found.get(a).dur = Math.round(el.duration);
        });
        document.querySelectorAll("source[src], a[href]").forEach((el) => {
          const u = el.src || el.href || "";
          if (/\.(mp4|webm|mkv|m4a|mp3|flac|ogg|opus|wav|mov)(\?|#|$)/i.test(u)) {
            add(abs(u), el.tagName.toLowerCase());
          }
        });
        return [...found.values()].map((m) => ({
          url: m.url, kind: [...m.kinds][0], dur: m.dur,
        }));
      },
    });
    return (res && res.result) || [];
  } catch {
    return [];
  }
}

function fmtDur(s) {
  if (!Number.isFinite(s)) return "";
  const m = Math.floor(s / 60), r = Math.round(s % 60);
  return m + ":" + String(r).padStart(2, "0");
}

async function main() {
  await loadQuality();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentUrl = tab && tab.url || "";
  currentTitle = (tab && tab.title) || "";
  if (!/^https?:/i.test(currentUrl)) {
    setStatus("open a web page first", "bad");
    sendBtn.disabled = true;
    return;
  }
  const pong = await pingApp();
  if (!pong) {
    setStatus("app not running", "bad");
    document.getElementById("sendPageRow").hidden = true;
    openRow.hidden = false;
    return;
  }
  setStatus("app connected · v" + pong.version, "ok");
  const media = await activeTabMedia();
  if (!media.length) return;
  emptyEl.hidden = true;
  mediaSection.hidden = false;
  media.slice(0, 12).forEach((m) => {
    const li = document.createElement("li");
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = m.url.split("/").pop().split("?")[0] || m.url;
    name.title = m.url;
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = (m.kind || "") + (m.dur ? " · " + fmtDur(m.dur) : "");
    const btn = document.createElement("button");
    btn.className = "mini";
    btn.textContent = "Download";
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "…";
      try {
        await sendUrl(m.url, name.textContent);
        btn.textContent = "Sent ✓";
        setTimeout(() => window.close(), 700);
      } catch {
        btn.textContent = "Failed";
      }
    });
    li.append(name, meta, btn);
    listEl.appendChild(li);
  });
}

main();
