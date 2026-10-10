// GenAI Generated code - Start
// Shared API helper: attaches the access code header and surfaces 401s so the
// UI can re-prompt. The code is a single shared secret, not a user login.

const STORAGE_KEY = "arogya.code";

export class UnauthorizedError extends Error {
  constructor() {
    super("unauthorized");
    this.name = "UnauthorizedError";
  }
}

export function getAccessCode() {
  return localStorage.getItem(STORAGE_KEY) || "";
}

export function setAccessCode(code) {
  if (code) localStorage.setItem(STORAGE_KEY, code);
  else localStorage.removeItem(STORAGE_KEY);
}

export function clearAccessCode() {
  localStorage.removeItem(STORAGE_KEY);
}

/** fetch() with the access code attached. Throws UnauthorizedError on 401. */
export async function apiFetch(url, options = {}) {
  const code = getAccessCode();
  const headers = { ...(options.headers || {}) };
  if (code) headers["X-Access-Code"] = code;

  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    clearAccessCode();
    throw new UnauthorizedError();
  }
  return response;
}
// GenAI Generated code - End
