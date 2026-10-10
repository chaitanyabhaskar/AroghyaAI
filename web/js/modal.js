// GenAI Generated code - Start
// Single reusable modal shell: one at a time, Esc to close, focus restored on exit.

const root = document.getElementById("modalRoot");
const scrim = document.getElementById("scrim");

let active = null;
let lastFocus = null;

function onKeydown(event) {
  if (event.key === "Escape") closeModal();
}

export function openModal({ title, icon = "#i-pin", body = "", footer = "" }) {
  closeModal();
  lastFocus = document.activeElement;

  const el = document.createElement("div");
  el.className = "modal";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.setAttribute("aria-label", title);
  el.innerHTML = `
    <div class="modal-head">
      <svg class="ico"><use href="${icon}"/></svg>
      <h2></h2>
      <button class="icon-btn" data-close type="button" aria-label="Close">
        <svg class="ico"><use href="#i-close"/></svg>
      </button>
    </div>
    <div class="modal-body"></div>
    ${footer ? '<div class="modal-foot"></div>' : ""}`;

  el.querySelector("h2").textContent = title;
  const bodyEl = el.querySelector(".modal-body");
  if (body instanceof Node) bodyEl.appendChild(body);
  else bodyEl.innerHTML = body;
  if (footer) el.querySelector(".modal-foot").textContent = footer;

  el.querySelector("[data-close]").addEventListener("click", closeModal);
  root.appendChild(el);
  scrim.hidden = false;
  scrim.addEventListener("click", closeModal, { once: true });
  document.addEventListener("keydown", onKeydown);

  active = el;
  const focusable = el.querySelector("input, select, button:not([data-close]), a");
  (focusable || el.querySelector("[data-close]")).focus();
  return { el, body: bodyEl };
}

export function closeModal() {
  if (!active) return;
  document.removeEventListener("keydown", onKeydown);
  active.remove();
  active = null;
  scrim.hidden = true;
  if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
  lastFocus = null;
}

export function isModalOpen() {
  return Boolean(active);
}
// GenAI Generated code - End
