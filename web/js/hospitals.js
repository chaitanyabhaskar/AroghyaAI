// GenAI Generated code - Start
// "Nearby Hospitals" finder: browser GPS + /api/hospitals (OpenStreetMap Overpass).

import { apiFetch, UnauthorizedError } from "./api.js";
import { t } from "./i18n.js";
import { openModal } from "./modal.js";
import { escapeHtml } from "./markdown.js";

const CATEGORY_KEYS = {
  all: "catAll",
  ayurveda: "catAyurveda",
  homeopathy: "catHomeopathy",
  general: "catGeneral",
  pharmacy: "catPharmacy",
};

const RADIUS_OPTIONS = [2, 5, 10, 20];

let cache = null; // { lat, lon, radius, payload }

function getPosition() {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("unsupported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve(pos.coords),
      (err) => reject(err),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 120000 }
    );
  });
}

function spinner(label) {
  return `<div class="center"><div class="spinner"></div><p class="muted">${escapeHtml(label)}</p></div>`;
}

function placeRow(place) {
  const tagKey = CATEGORY_KEYS[place.category] || "catGeneral";
  const meta = [
    `${place.distance_km} ${t("away")}`,
    place.address,
    place.open_hours,
    place.emergency ? t("emergencyUnit") : "",
  ]
    .filter(Boolean)
    .map(escapeHtml)
    .join(" · ");

  const callBtn = place.phone
    ? `<a class="mini-btn" href="tel:${escapeHtml(place.phone.replace(/[^\d+]/g, ""))}">
         <svg class="ico"><use href="#i-phone"/></svg>${t("call")}</a>`
    : "";

  return `
    <div class="place">
      <div class="place-body">
        <p class="place-name">
          <span class="place-tag tag-${place.category}">${t(tagKey)}</span>
          ${escapeHtml(place.name)}
        </p>
        <div class="place-meta">${meta}</div>
      </div>
      <div class="place-actions">
        <a class="mini-btn" href="${escapeHtml(place.maps_url)}" target="_blank" rel="noopener noreferrer">
          <svg class="ico"><use href="#i-pin"/></svg>${t("directions")}
        </a>
        ${callBtn}
      </div>
    </div>`;
}

function render(bodyEl, state, reload) {
  const { payload, category, radius } = state;
  const list = payload.results.filter(
    (p) => category === "all" || p.category === category
  );

  const tabs = Object.keys(CATEGORY_KEYS)
    .map((key) => {
      const count = key === "all" ? payload.results.length : payload.counts[key] || 0;
      return `<button class="tab" type="button" data-cat="${key}" aria-pressed="${
        key === category
      }">${t(CATEGORY_KEYS[key])}${count ? ` (${count})` : ""}</button>`;
    })
    .join("");

  const radiusSelect = RADIUS_OPTIONS.map(
    (km) => `<option value="${km}" ${km === radius ? "selected" : ""}>${km} km</option>`
  ).join("");

  bodyEl.innerHTML = `
    <div class="tabs">${tabs}</div>
    <div class="field" style="flex-direction:row;align-items:center;gap:8px;margin-bottom:10px">
      <label for="radiusSel" style="margin:0">${t("radius")}</label>
      <select id="radiusSel" style="flex:1">${radiusSelect}</select>
    </div>
    ${
      list.length
        ? list.map(placeRow).join("")
        : `<p class="muted center">${escapeHtml(t("noResults"))}</p>`
    }`;

  bodyEl.querySelectorAll("[data-cat]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.category = btn.dataset.cat;
      render(bodyEl, state, reload);
    });
  });
  bodyEl.querySelector("#radiusSel").addEventListener("change", (event) => {
    reload(Number(event.target.value), state.category);
  });
}

function geoErrorMessage(error) {
  if (error && error.code === 1) return t("locationDenied");
  return t("locationUnavailable");
}

/** Open the finder modal. ``category`` preselects a tab. */
export async function openHospitalFinder(category = "all") {
  const { body } = openModal({
    title: t("hospitalsTitle"),
    icon: "#i-pin",
    body: spinner(t("locating")),
    footer: t("osmNote"),
  });

  const load = async (radius, cat) => {
    body.innerHTML = spinner(t("searching"));
    try {
      let coords;
      if (cache) {
        coords = { latitude: cache.lat, longitude: cache.lon };
      } else {
        const position = await getPosition();
        coords = position;
      }

      const params = new URLSearchParams({
        lat: coords.latitude.toFixed(6),
        lon: coords.longitude.toFixed(6),
        radius_km: String(radius),
        category: "all",
        limit: "60",
      });
      const response = await apiFetch(`/api/hospitals?${params}`);
      const payload = await response.json();
      if (!response.ok) {
        body.innerHTML = `<p class="muted center">${escapeHtml(payload.error || t("errGeneric"))}</p>`;
        return;
      }
      cache = { lat: coords.latitude, lon: coords.longitude, radius, payload };
      render(body, { payload, category: cat, radius }, load);
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        body.innerHTML = `<p class="muted center">${escapeHtml(t("gateInvalid"))}</p>`;
        return;
      }
      body.innerHTML = `<p class="muted center">${escapeHtml(geoErrorMessage(error))}</p>`;
    }
  };

  await load(cache?.radius || 5, category);
}
// GenAI Generated code - End
