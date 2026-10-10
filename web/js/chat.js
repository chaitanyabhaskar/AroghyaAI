// GenAI Generated code - Start
// Chat transport (SSE over fetch) plus the message DOM builders.

import { apiFetch, UnauthorizedError } from "./api.js";
import { t } from "./i18n.js";
import { renderMarkdown } from "./markdown.js";

const messagesEl = document.getElementById("messages");

const ASSISTANT_AVATAR = '<span class="bubble-avatar"><svg class="ico"><use href="#i-leaf"/></svg></span>';

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function nearBottom() {
  const gap = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight;
  return gap < 160;
}

export function scrollToBottom(force = false) {
  if (force || nearBottom()) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

export function clearMessages() {
  messagesEl.replaceChildren();
}

/** Welcome card. ``onChip`` receives the chip id for the two actionable chips. */
export function addWelcome(name, onChip) {
  const row = document.createElement("div");
  row.className = "row assistant";
  row.innerHTML = `
    ${ASSISTANT_AVATAR}
    <div class="bubble">
      <p><strong>${t("welcomeTitle", { name })}</strong></p>
      ${renderMarkdown(t("welcomeIntro"))}
      <div class="chips">
        <span class="chip chip-static">🌿 ${t("chipRemedies")}</span>
        <button class="chip" type="button" data-chip="voice">🎙️ ${t("chipVoice")}</button>
        <button class="chip" type="button" data-chip="image">📷 ${t("chipImage")}</button>
        <button class="chip" type="button" data-chip="hospitals">🏥 ${t("chipHospitals")}</button>
      </div>
      <p>${t("welcomeAsk")}</p>
      <div class="msg-time">${nowLabel()}</div>
    </div>`;
  row.querySelectorAll("[data-chip]").forEach((btn) => {
    btn.addEventListener("click", () => onChip && onChip(btn.dataset.chip));
  });
  messagesEl.appendChild(row);
  scrollToBottom(true);
}

export function addUserMessage(text, imageDataUrl) {
  const row = document.createElement("div");
  row.className = "row user";
  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (imageDataUrl) {
    const img = document.createElement("img");
    img.className = "bubble-img";
    img.src = imageDataUrl;
    img.alt = t("attached");
    bubble.appendChild(img);
  }
  if (text) {
    const p = document.createElement("p");
    p.textContent = text;
    bubble.appendChild(p);
  }
  const time = document.createElement("div");
  time.className = "msg-time";
  time.textContent = nowLabel();
  bubble.appendChild(time);

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom(true);
}

/** Streaming assistant bubble. Returns a small handle to drive it. */
export function addAssistantMessage() {
  const row = document.createElement("div");
  row.className = "row assistant";
  row.innerHTML = `${ASSISTANT_AVATAR}<div class="bubble"><span class="typing" role="status" aria-label="${t(
    "thinking"
  )}"><i></i><i></i><i></i></span></div>`;
  messagesEl.appendChild(row);
  scrollToBottom(true);

  const bubble = row.querySelector(".bubble");
  let text = "";
  let started = false;
  let failed = false;

  return {
    get text() {
      return text;
    },
    get failed() {
      return failed;
    },
    append(piece) {
      if (failed) return;
      text += piece;
      if (!started) {
        bubble.replaceChildren();
        started = true;
      }
      bubble.innerHTML = renderMarkdown(text);
      scrollToBottom();
    },
    finish() {
      // An error box is terminal - never overwrite it with the (empty) stream.
      if (failed) return;
      if (!started) {
        bubble.replaceChildren();
        started = true;
      }
      bubble.innerHTML = renderMarkdown(text);
      const time = document.createElement("div");
      time.className = "msg-time";
      time.textContent = nowLabel();
      bubble.appendChild(time);
      scrollToBottom();
    },
    fail(message) {
      failed = true;
      bubble.replaceChildren();
      const box = document.createElement("div");
      box.className = "err";
      box.innerHTML = renderMarkdown(message || t("errGeneric"));
      bubble.appendChild(box);
      scrollToBottom(true);
    },
  };
}

/** Red emergency banner injected above the model reply. */
export function addAlert({ message, numbers = [] }) {
  const box = document.createElement("div");
  box.className = "alert";
  box.setAttribute("role", "alert");
  box.innerHTML = `
    <div class="alert-title"><svg class="ico"><use href="#i-phone"/></svg>${t("emergencyTitle")}</div>
    <div>${renderMarkdown(message)}</div>
    <div class="alert-numbers">${numbers
      .map(
        (n) =>
          `<a class="call-btn" href="tel:${n.replace(/[^\d+]/g, "")}">
             <svg class="ico"><use href="#i-phone"/></svg>${n}</a>`
      )
      .join("")}</div>`;
  messagesEl.appendChild(box);
  scrollToBottom(true);
}

export function addNotice(text) {
  const row = document.createElement("div");
  row.className = "row assistant";
  row.innerHTML = `${ASSISTANT_AVATAR}<div class="bubble"><p class="muted"></p></div>`;
  row.querySelector("p").textContent = text;
  messagesEl.appendChild(row);
  scrollToBottom(true);
}

/** Replay stored history (used after a page reload). */
export function renderHistory(items) {
  for (const item of items) {
    if (item.role === "user") {
      addUserMessage(item.content, null);
    } else if (item.role === "assistant") {
      const row = document.createElement("div");
      row.className = "row assistant";
      row.innerHTML = `${ASSISTANT_AVATAR}<div class="bubble">${renderMarkdown(item.content)}</div>`;
      messagesEl.appendChild(row);
    }
  }
  scrollToBottom(true);
}

/**
 * POST /api/chat and consume the SSE stream.
 * handlers: { onMeta, onDelta, onError }
 */
export async function streamChat(payload, { onMeta, onDelta, onError, onUnauthorized } = {}) {
  let response;
  try {
    response = await apiFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      onUnauthorized && onUnauthorized();
      return;
    }
    onError && onError(t("errGeneric"));
    return;
  }

  if (!response.ok || !response.body) {
    let message = t("errGeneric");
    try {
      const data = await response.json();
      if (data && data.error) message = data.error;
    } catch {
      /* non-JSON error body */
    }
    onError && onError(message);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let event;
      try {
        event = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }
      if (event.type === "meta") onMeta && onMeta(event);
      else if (event.type === "delta") onDelta && onDelta(event.text);
      else if (event.type === "error") onError && onError(event.message);
    }
  }
}
// GenAI Generated code - End
