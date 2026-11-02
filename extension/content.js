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
    try {
      btn.animate(
        [{ transform: "scale(1)" }, { transform: "scale(1.07)" }, { transform: "scale(1)" }],
        { duration: 2400, iterations: Infinity, easing: "ease-in-out" });
    } catch {}
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
    if (ok) flyToDownloads(btn);
    bubble(btn, msg, ok);
  }

  /* A little file that arcs to the browser's download button (top-right). */
  function flyToDownloads(btn) {
    try {
      const fly = document.createElement("div");
      fly.innerHTML =
        '<svg width="36" height="44" viewBox="0 0 36 44">' +
        '<path d="M4 4a3 3 0 0 1 3-3h16l9 9v30a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z" ' +
        'fill="#fff" stroke="#c9c9d1" stroke-width="1.2"/>' +
        '<path d="M23 1l9 9h-7a2 2 0 0 1-2-2z" fill="#e6e6ec" stroke="#c9c9d1" ' +
        'stroke-width="1"/>' +
        '<g stroke="#0A84FF" stroke-width="2.4" stroke-linecap="round" ' +
        'stroke-linejoin="round" fill="none">' +
        '<path d="M18 16v12"/><path d="M12.5 23l5.5 5.5L23.5 23"/></g></svg>';
      Object.assign(fly.style, {
        position: "fixed", zIndex: String(Z + 1),
        left: btn.offsetLeft + 8 + "px", top: btn.offsetTop + 4 + "px",
        pointerEvents: "none", filter: "drop-shadow(0 3px 8px rgba(0,0,0,.3))",
      });
      document.documentElement.appendChild(fly);
      const dx = window.innerWidth - 46 - btn.offsetLeft - 8;
      const dy = 12 - btn.offsetTop - 4;
      fly.animate(
        [
          { transform: "translate(0,0) scale(1) rotate(0deg)", opacity: 1 },
          { transform: `translate(${dx * 0.45}px, ${dy * 0.28 - 70}px) scale(0.92) rotate(-9deg)`, opacity: 1, offset: 0.45 },
          { transform: `translate(${dx}px, ${dy}px) scale(0.3) rotate(7deg)`, opacity: 0.15 },
        ],
        { duration: 900, easing: "cubic-bezier(.42,.05,.58,1)" },
      ).onfinish = () => fly.remove();
    } catch {}
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
