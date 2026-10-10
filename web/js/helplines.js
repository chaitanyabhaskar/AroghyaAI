// GenAI Generated code - Start
// India emergency helpline list, fetched once from /api/helplines.

import { t } from "./i18n.js";
import { openModal } from "./modal.js";
import { escapeHtml } from "./markdown.js";

let cached = null;

function row(item) {
  const tel = item.number.replace(/[^\d+]/g, "");
  return `
    <div class="helpline-row">
      <div class="place-body">
        <p class="place-name ${item.urgent === "true" ? "helpline-urgent" : ""}">
          ${escapeHtml(item.name)}
        </p>
        <div class="place-meta">${escapeHtml(item.note)}</div>
      </div>
      <a class="call-btn" href="tel:${tel}">
        <svg class="ico"><use href="#i-phone"/></svg>${escapeHtml(item.number)}
      </a>
    </div>`;
}

export async function openHelplines() {
  const { body } = openModal({
    title: t("helplinesTitle"),
    icon: "#i-phone",
    body: '<div class="center"><div class="spinner"></div></div>',
    footer: t("helplinesNote"),
  });

  if (!cached) {
    try {
      const response = await fetch("/api/helplines");
      const data = await response.json();
      cached = data.helplines || [];
    } catch {
      body.innerHTML = `<p class="muted center">${escapeHtml(t("errGeneric"))}</p>`;
      return;
    }
  }
  body.innerHTML = cached.map(row).join("");
}
// GenAI Generated code - End
