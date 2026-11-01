/* AnyDownloader Companion — floating download button (content script).
 * Enabled/disabled + position live in chrome.storage.local; storage.onChanged
 * updates every open tab instantly. Tap = send page to the app, drag = move. */
(() => {
  const BTN_ID = "anydl-float-btn";
  const BUBBLE_ID = "anydl-float-bubble";
  const BRIDGE = "http://127.0.0.1:7272";
  const Z = 2147483647;

  let dragMoved = false;

  function inject() {
    if (document.getElementById(BTN_ID)) return;
    const btn = document.createElement("div");
    btn.id = BTN_ID;
    Object.assign(btn.style, {
      position: "fixed", zIndex: String(Z), width: "52px", height: "52px",
      borderRadius: "50%", cursor: "grab", touchAction: "none",
      background: "linear-gradient(135deg,#0A84FF,#5E5CE6 60%,#AF52DE)",
      boxShadow: "0 4px 16px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.25)",
      display: "flex", alignItems: "center", justifyContent: "center",
      userSelect: "none", WebkitUserSelect: "none", opacity: "0.92",
      transition: "opacity .15s, transform .15s",
    });
    btn.innerHTML =
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M12 3v12"/><path d="M6 11l6 6 6-6"/><path d="M5 21h14"/></svg>';
    btn.addEventListener("pointerenter", () => (btn.style.opacity = "1"));
    btn.addEventListener("pointerleave", () => (btn.style.opacity = "0.92"));
    document.documentElement.appendChild(btn);
    restorePos(btn);
    wireDrag(btn);
  }

  function remove() {
    document.getElementById(BTN_ID)?.remove();
    document.getElementById(BUBBLE_ID)?.remove();
  }

  function clamp(pos) {
    const m = 8;
    return {
      x: Math.min(Math.max(pos.x, m), window.innerWidth - 60),
      y: Math.min(Math.max(pos.y, m), window.innerHeight - 60),
    };
  }

  function restorePos(btn) {
    chrome.storage.local.get("floatPos", ({ floatPos }) => {
      const pos = floatPos
        ? clamp(floatPos)
        : { x: window.innerWidth - 76, y: Math.round(window.innerHeight * 0.72) };
      btn.style.left = pos.x + "px";
      btn.style.top = pos.y + "px";
    });
  }

  function wireDrag(btn) {
    let startX = 0, startY = 0, origX = 0, origY = 0, dragging = false;
    btn.addEventListener("pointerdown", (e) => {
      dragging = true; dragMoved = false;
      startX = e.clientX; startY = e.clientY;
      origX = btn.offsetLeft; origY = btn.offsetTop;
      btn.setPointerCapture(e.pointerId);
      btn.style.cursor = "grabbing";
    });
    btn.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - startX, dy = e.clientY - startY;
      if (Math.abs(dx) > 6 || Math.abs(dy) > 6) dragMoved = true;
      if (dragMoved) {
        const pos = clamp({ x: origX + dx, y: origY + dy });
        btn.style.left = pos.x + "px";
        btn.style.top = pos.y + "px";
      }
    });
    btn.addEventListener("pointerup", (e) => {
      dragging = false;
      btn.style.cursor = "grab";
      if (dragMoved) {
        chrome.storage.local.set({
          floatPos: { x: btn.offsetLeft, y: btn.offsetTop },
        });
      } else {
        e.preventDefault();
        sendToApp(btn);
      }
    });
  }

  async function sendToApp(btn) {
    let profile = "best";
    try {
      ({ profile = "best" } = await chrome.storage.local.get("profile"));
    } catch {}
    let ok = false, msg = "Sent ✓";
    try {
      const r = await fetch(BRIDGE + "/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: location.href, title: document.title, profile }),
        signal: AbortSignal.timeout(8000),
      });
      ok = r.ok;
      if (!ok) msg = "App refused";
    } catch {
      msg = "App not running";
    }
    bubble(btn, msg, ok);
  }

  function bubble(btn, text, ok) {
    document.getElementById(BUBBLE_ID)?.remove();
    const b = document.createElement("div");
    b.id = BUBBLE_ID;
    Object.assign(b.style, {
      position: "fixed", zIndex: String(Z),
      left: btn.offsetLeft - 46 + "px", top: btn.offsetTop + 12 + "px",
      background: ok ? "rgba(48,209,88,.95)" : "rgba(255,69,58,.95)",
      color: "#fff", font: "600 12px 'Segoe UI', sans-serif",
      padding: "6px 12px", borderRadius: "12px",
      boxShadow: "0 3px 10px rgba(0,0,0,.3)", pointerEvents: "none",
      whiteSpace: "nowrap",
    });
    b.textContent = text;
    document.documentElement.appendChild(b);
    setTimeout(() => b.remove(), 1800);
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local" || !("floatEnabled" in changes)) return;
    if (changes.floatEnabled.newValue) inject();
    else remove();
  });

  chrome.storage.local.get("floatEnabled", ({ floatEnabled }) => {
    if (floatEnabled && document.documentElement) inject();
    else document.addEventListener("DOMContentLoaded", () => {
      chrome.storage.local.get("floatEnabled", ({ floatEnabled: on }) => on && inject());
    });
  });
})();
