// GenAI Generated code - Start
// ArogyaAI frontend entry point: wires the sidebar, composer, voice and modals.

import { CONCERNS, LANG_ORDER, pick, setLang, t } from "./i18n.js";
import {
  addAlert, addAssistantMessage, addNotice, addUserMessage, addWelcome,
  clearMessages, renderHistory, streamChat,
} from "./chat.js";
import { openHospitalFinder } from "./hospitals.js";
import { openHelplines } from "./helplines.js";
import { closeModal, openModal } from "./modal.js";
import { createVoice, sttSupported, ttsSupported } from "./voice.js";
import { escapeHtml } from "./markdown.js";
import { apiFetch, getAccessCode, setAccessCode, UnauthorizedError } from "./api.js";

const KEYS = { lang: "arogya.lang", name: "arogya.name", session: "arogya.session" };

const el = {
  sidebar: document.getElementById("sidebar"),
  scrim: document.getElementById("scrim"),
  menuBtn: document.getElementById("menuBtn"),
  langGrid: document.getElementById("langGrid"),
  concernList: document.getElementById("concernList"),
  escalateBtn: document.getElementById("escalateBtn"),
  helplineBtn: document.getElementById("helplineBtn"),
  hospitalsBtn: document.getElementById("hospitalsBtn"),
  voiceToggle: document.getElementById("voiceToggle"),
  newChatBtn: document.getElementById("newChatBtn"),
  profileBtn: document.getElementById("profileBtn"),
  userName: document.getElementById("userName"),
  userSub: document.getElementById("userSub"),
  userAvatar: document.getElementById("userAvatar"),
  modelLabel: document.getElementById("modelLabel"),
  configBanner: document.getElementById("configBanner"),
  composer: document.getElementById("composer"),
  input: document.getElementById("input"),
  sendBtn: document.getElementById("sendBtn"),
  micBtn: document.getElementById("micBtn"),
  imageBtn: document.getElementById("imageBtn"),
  imageInput: document.getElementById("imageInput"),
  attachPreview: document.getElementById("attachPreview"),
  attachThumb: document.getElementById("attachThumb"),
  attachName: document.getElementById("attachName"),
  attachClear: document.getElementById("attachClear"),
};

const state = {
  lang: localStorage.getItem(KEYS.lang) || "en",
  name: localStorage.getItem(KEYS.name) || "",
  sessionId: localStorage.getItem(KEYS.session) || null,
  image: null,
  busy: false,
  maxImageBytes: 4 * 1024 * 1024,
  requiresCode: false,
};

const voice = createVoice({
  onInterim: (text) => {
    el.input.value = text;
    autoGrow();
  },
  onFinal: (text) => {
    el.input.value = text;
    autoGrow();
    refreshSend();
    if (voice.autoSpeak) submit();
  },
  onStateChange: (status) => {
    el.micBtn.classList.toggle("mic-live", status === "listening");
    el.micBtn.setAttribute("aria-pressed", String(status === "listening"));
    if (status === "listening") el.input.placeholder = t("listening");
    else el.input.placeholder = t("placeholder");
  },
  onError: (code) => {
    if (code === "unsupported" || code === "not-allowed" || code === "service-not-allowed") {
      addNotice(t("micUnsupported"));
    }
  },
});

/* ------------------------------ i18n plumbing ----------------------------- */
function applyI18n() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPh);
  });
  // Icon-only controls get localised accessible names from existing keys.
  for (const [node, key] of [
    [el.newChatBtn, "newChat"],
    [el.micBtn, "chipVoice"],
    [el.imageBtn, "chipImage"],
    [el.voiceToggle, "voiceAgent"],
    [el.profileBtn, "profileTitle"],
  ]) {
    node.title = t(key);
    node.setAttribute("aria-label", t(key));
  }
  renderProfileChip();
  renderLangGrid();
  renderConcerns();
}

function renderLangGrid() {
  el.langGrid.replaceChildren();
  for (const code of LANG_ORDER) {
    const label = { en: "English", hi: "हिन्दी (Hindi)", ta: "தமிழ் (Tamil)",
                    te: "తెలుగు (Telugu)", bn: "বাংলা (Bengali)", mr: "मराठी (Marathi)" }[code];
    const btn = document.createElement("button");
    btn.className = "lang-btn";
    btn.type = "button";
    btn.textContent = label;
    btn.setAttribute("aria-pressed", String(code === state.lang));
    btn.addEventListener("click", () => switchLanguage(code));
    el.langGrid.appendChild(btn);
  }
}

function renderConcerns() {
  el.concernList.replaceChildren();
  for (const concern of CONCERNS) {
    const btn = document.createElement("button");
    btn.className = "concern-btn";
    btn.type = "button";
    btn.innerHTML = `<span class="concern-emoji">${concern.emoji}</span><span></span>`;
    btn.lastElementChild.textContent = pick(concern.label);
    btn.addEventListener("click", () => {
      closeDrawer();
      if (concern.id === "no-relief") {
        el.input.value = pick(concern.prompt);
        autoGrow();
        refreshSend();
        submit();
        return;
      }
      el.input.value = pick(concern.prompt);
      autoGrow();
      refreshSend();
      el.input.focus();
    });
    el.concernList.appendChild(btn);
  }
}

function renderProfileChip() {
  const name = state.name || t("guest");
  el.userName.textContent = name;
  el.userAvatar.textContent = (state.name || "A").trim().charAt(0).toUpperCase();
  el.userSub.textContent = state.name
    ? { en: "Signed in locally", hi: "स्थानीय रूप से सहेजा", ta: "உள்ளூரில் சேமிக்கப்பட்டது",
        te: "స్థానికంగా సేవ్ చేయబడింది", bn: "স্থানীয়ভাবে সংরক্ষিত", mr: "स्थानिक जतन" }[state.lang]
    : t("guestSub");
}

function switchLanguage(code) {
  state.lang = setLang(code);
  localStorage.setItem(KEYS.lang, state.lang);
  applyI18n();
  clearMessages();
  addWelcome(state.name || t("guest"), handleChip);
  closeDrawer();
}

/* ------------------------------- composer --------------------------------- */
function autoGrow() {
  el.input.style.height = "auto";
  el.input.style.height = `${Math.min(el.input.scrollHeight, 160)}px`;
}

function refreshSend() {
  const ready = Boolean(el.input.value.trim() || state.image) && !state.busy;
  el.sendBtn.classList.toggle("ready", ready);
  el.sendBtn.disabled = !ready;
}

async function fileToDataUrl(file, maxSide = 1024, quality = 0.82) {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d").drawImage(bitmap, 0, 0, width, height);
    bitmap.close?.();
    return canvas.toDataURL("image/jpeg", quality);
  } catch {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }
}

function setAttachment(dataUrl, label) {
  state.image = dataUrl;
  el.attachThumb.src = dataUrl;
  el.attachName.textContent = label;
  el.attachPreview.hidden = false;
  refreshSend();
}

function clearAttachment() {
  state.image = null;
  el.imageInput.value = "";
  el.attachPreview.hidden = true;
  el.attachThumb.removeAttribute("src");
  refreshSend();
}

/* -------------------------------- sending --------------------------------- */
async function submit() {
  if (state.busy) return;
  const text = el.input.value.trim();
  const image = state.image;
  if (!text && !image) return;

  state.busy = true;
  el.input.value = "";
  autoGrow();
  clearAttachment();
  refreshSend();
  voice.cancelSpeech();

  addUserMessage(text, image);

  let bubble = null;
  const ensureBubble = () => {
    if (!bubble) bubble = addAssistantMessage();
    return bubble;
  };

  await streamChat(
    {
      message: text,
      language: state.lang,
      session_id: state.sessionId,
      user_name: state.name || null,
      image,
    },
    {
      onMeta: (event) => {
        if (event.session_id && event.session_id !== state.sessionId) {
          state.sessionId = event.session_id;
          localStorage.setItem(KEYS.session, event.session_id);
        }
        if (event.emergency) addAlert(event.emergency);
        ensureBubble();
      },
      onDelta: (piece) => ensureBubble().append(piece),
      onError: (message) => ensureBubble().fail(message),
      onUnauthorized: () => {
        ensureBubble().fail(t("gateInvalid"));
        openAccessGate({ retry: true });
      },
    }
  );

  if (bubble) {
    bubble.finish();
    if (voice.autoSpeak && !bubble.failed && bubble.text) {
      voice.speak(bubble.text, state.lang);
    }
  }
  state.busy = false;
  refreshSend();
}

/* --------------------------------- chips ---------------------------------- */
function handleChip(kind) {
  if (kind === "voice") {
    el.micBtn.click();
  } else if (kind === "image") {
    el.imageInput.click();
  } else if (kind === "hospitals") {
    openHospitalFinder("all");
  }
}

/* -------------------------------- drawer ---------------------------------- */
function openDrawer() {
  el.sidebar.classList.add("open");
  el.scrim.hidden = false;
  el.scrim.addEventListener("click", closeDrawer, { once: true });
}
function closeDrawer() {
  el.sidebar.classList.remove("open");
  if (!document.querySelector(".modal")) el.scrim.hidden = true;
}

/* -------------------------------- profile --------------------------------- */
function openProfile() {
  const options = LANG_ORDER.map(
    (code) =>
      `<option value="${code}" ${code === state.lang ? "selected" : ""}>${
        { en: "English", hi: "हिन्दी", ta: "தமிழ்", te: "తెలుగు", bn: "বাংলা", mr: "मराठी" }[code]
      }</option>`
  ).join("");

  const { body } = openModal({
    title: t("profileTitle"),
    icon: "#i-logout",
    body: `
      <div class="field">
        <label for="pfName">${escapeHtml(t("profileName"))}</label>
        <input id="pfName" maxlength="60" value="${escapeHtml(state.name)}" />
      </div>
      <div class="field">
        <label for="pfLang">${escapeHtml(t("profileLang"))}</label>
        <select id="pfLang">${options}</select>
      </div>
      <button class="btn-primary" id="pfSave" type="button">${escapeHtml(t("save"))}</button>
      <button class="btn-ghost" id="pfClear" type="button">${escapeHtml(t("clearChat"))}</button>`,
  });

  body.querySelector("#pfSave").addEventListener("click", () => {
    state.name = body.querySelector("#pfName").value.trim().slice(0, 60);
    localStorage.setItem(KEYS.name, state.name);
    const chosen = body.querySelector("#pfLang").value;
    closeModal();
    if (chosen !== state.lang) switchLanguage(chosen);
    else {
      applyI18n();
      clearMessages();
      addWelcome(state.name || t("guest"), handleChip);
    }
  });

  body.querySelector("#pfClear").addEventListener("click", async () => {
    if (state.sessionId) {
      try {
        await apiFetch(`/api/history/${state.sessionId}`, { method: "DELETE" });
      } catch {
        /* offline or locked is fine - local state still resets */
      }
    }
    closeModal();
    startNewChat();
  });
}

function startNewChat() {
  state.sessionId = null;
  localStorage.removeItem(KEYS.session);
  clearAttachment();
  clearMessages();
  addWelcome(state.name || t("guest"), handleChip);
}

/* ------------------------------ access gate ------------------------------- */
/** Shared-passcode prompt. Not a login - one secret shared by all users. */
function openAccessGate({ retry = false } = {}) {
  const { body } = openModal({
    title: t("gateTitle"),
    icon: "#i-logout",
    body: `
      ${retry ? `<p class="err" style="margin-bottom:12px">${escapeHtml(t("gateInvalid"))}</p>` : ""}
      <p class="muted" style="margin-top:0">${escapeHtml(t("gateHint"))}</p>
      <div class="field">
        <label for="gateCode">${escapeHtml(t("gateLabel"))}</label>
        <input id="gateCode" type="password" autocomplete="current-password" />
      </div>
      <button class="btn-primary" id="gateGo" type="button">${escapeHtml(t("unlock"))}</button>`,
  });

  const input = body.querySelector("#gateCode");
  const submitCode = () => {
    const code = input.value.trim();
    if (!code) return;
    setAccessCode(code);
    closeModal();
    startNewChat();
  };
  body.querySelector("#gateGo").addEventListener("click", submitCode);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") submitCode();
  });
  input.focus();
}

/* --------------------------------- boot ----------------------------------- */
async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    const config = await response.json();
    el.modelLabel.textContent = config.model_label || "";
    state.maxImageBytes = config.max_image_bytes || state.maxImageBytes;
    state.requiresCode = Boolean(config.requires_code);
    if (!config.model_configured) {
      el.configBanner.innerHTML = t("noKey");
      el.configBanner.hidden = false;
    }
  } catch {
    el.modelLabel.textContent = "";
  }
}

async function restoreHistory() {
  if (!state.sessionId) return false;
  try {
    const response = await apiFetch(`/api/history/${state.sessionId}`);
    const data = await response.json();
    if (data.messages && data.messages.length) {
      renderHistory(data.messages);
      return true;
    }
  } catch (error) {
    if (error instanceof UnauthorizedError) return false;
    /* fall through to a fresh welcome */
  }
  return false;
}

function bindEvents() {
  el.composer.addEventListener("submit", (event) => {
    event.preventDefault();
    submit();
  });

  el.input.addEventListener("input", () => {
    autoGrow();
    refreshSend();
  });
  el.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  });

  el.imageBtn.addEventListener("click", () => el.imageInput.click());
  el.imageInput.addEventListener("change", async () => {
    const file = el.imageInput.files?.[0];
    if (!file) return;
    const dataUrl = await fileToDataUrl(file);
    setAttachment(dataUrl, `${t("attached")} · ${file.name}`);
    el.input.focus();
  });
  el.attachClear.addEventListener("click", clearAttachment);

  el.micBtn.addEventListener("click", () => {
    if (!sttSupported) {
      addNotice(t("micUnsupported"));
      return;
    }
    if (voice.listening) voice.stop();
    else voice.start(state.lang);
  });

  el.voiceToggle.addEventListener("click", () => {
    voice.autoSpeak = !voice.autoSpeak;
    el.voiceToggle.setAttribute("aria-pressed", String(voice.autoSpeak));
    if (voice.autoSpeak && !ttsSupported) addNotice(t("micUnsupported"));
  });

  el.hospitalsBtn.addEventListener("click", () => openHospitalFinder("all"));
  el.escalateBtn.addEventListener("click", () => {
    closeDrawer();
    openHospitalFinder("all");
  });
  el.helplineBtn.addEventListener("click", () => {
    closeDrawer();
    openHelplines();
  });
  el.newChatBtn.addEventListener("click", startNewChat);
  el.profileBtn.addEventListener("click", openProfile);
  el.menuBtn.addEventListener("click", openDrawer);
}

async function boot() {
  setLang(state.lang);
  applyI18n();
  bindEvents();
  refreshSend();
  await loadConfig();
  const restored = await restoreHistory();
  if (!restored) addWelcome(state.name || t("guest"), handleChip);
  // Ask for the passcode up front rather than failing on the first message.
  if (state.requiresCode && !getAccessCode()) openAccessGate();
}

boot();
// GenAI Generated code - End
