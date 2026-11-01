/* AnyDownloader Companion — popup logic (MV3) */
const BRIDGE = "http://127.0.0.1:7272";

const statusEl = document.getElementById("status");
const sendBtn = document.getElementById("sendPage");
const listEl = document.getElementById("mediaList");
const mediaSection = document.getElementById("mediaSection");
const emptyEl = document.getElementById("empty");
const helpEl = document.getElementById("help");

async function pingApp() {
  try {
    const r = await fetch(BRIDGE + "/ping", { signal: AbortSignal.timeout(2500) });
    const d = await r.json();
    statusEl.textContent = "app connected · v" + d.version;
    statusEl.className = "status ok";
    return true;
  } catch {
    statusEl.textContent = "app not running";
    statusEl.className = "status bad";
    helpEl.hidden = false;
    sendBtn.disabled = true;
    return false;
  }
}

async function sendUrl(url, title) {
  const r = await fetch(BRIDGE + "/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title }),
    signal: AbortSignal.timeout(4000),
  });
  if (!r.ok) throw new Error("app rejected: " + r.status);
}

function flashSent(text) {
  const p = document.createElement("p");
  p.className = "sent";
  p.textContent = text;
  document.body.appendChild(p);
  setTimeout(() => window.close(), 900);
}

sendBtn.addEventListener("click", async () => {
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending…";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await sendUrl(tab.url, tab.title || "");
    flashSent("Sent to AnyDownloader ✓");
  } catch (e) {
    sendBtn.textContent = "Failed — is the app open?";
    setTimeout(() => { sendBtn.textContent = "⬇ Send this page to AnyDownloader"; sendBtn.disabled = false; }, 1800);
  }
});

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return null;
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const abs = (u) => { try { return new URL(u, location.href).href; } catch { return null; } };
        const found = new Map();
        const add = (url, kind) => {
          if (!url || !/^https?:/i.test(url)) return;
          if (found.has(url)) { found.get(url).kinds.add(kind); return; }
          found.set(url, { url, kinds: new Set([kind]), dur: null });
        };
        document.querySelectorAll("video, audio").forEach((el) => {
          const src = el.currentSrc || el.src || (el.querySelector("source") || {}).src;
          add(abs(src), el.tagName.toLowerCase());
          const d = el.duration;
          if (Number.isFinite(d)) { found.get(abs(src)).dur = Math.round(d); }
        });
        document.querySelectorAll("source[src], a[href]").forEach((el) => {
          const u = el.src || el.href || "";
          if (/\.(mp4|webm|mkv|m4a|mp3|flac|ogg|opus|wav|mov)(\?|#|$)/i.test(u)) {
            add(abs(u), el.tagName.toLowerCase());
          }
        });
        return {
          media: [...found.values()].map((m) => ({
            url: m.url,
            kind: [...m.kinds][0],
            dur: m.dur,
          })),
        };
      },
    });
    return res && res.result;
  } catch {
    return null;
  }
}

function fmtDur(s) {
  if (!Number.isFinite(s)) return "";
  const m = Math.floor(s / 60), r = Math.round(s % 60);
  return m + ":" + String(r).padStart(2, "0");
}

async function main() {
  const ok = await pingApp();
  if (!ok) return;
  const data = await activeTab();
  const media = (data && data.media) || [];
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
      try { await sendUrl(m.url, name.textContent); btn.textContent = "Sent ✓"; setTimeout(() => window.close(), 700); }
      catch { btn.textContent = "Failed"; }
    });
    li.append(name, meta, btn);
    listEl.appendChild(li);
  });
}

main();
