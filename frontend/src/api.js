// Client API : jetons dans localStorage, rafraîchissement automatique sur 401.
const KEY = "djinzin.tokens";

export const tokens = {
  get() {
    try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch { return null; }
  },
  set(t) { try { localStorage.setItem(KEY, JSON.stringify(t)); } catch { /* navigation privée */ } },
  clear() { try { localStorage.removeItem(KEY); } catch { /* ignore */ } },
};

export class ApiError extends Error {
  constructor(status, data) {
    super(messageFrom(data) || `Erreur ${status}`);
    this.status = status;
    this.data = data;
  }
}

// DRF renvoie {detail: "..."} ou {champ: ["..."]} : on garde le premier message lisible.
function messageFrom(data) {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (data.detail) return String(data.detail);
  const first = Object.values(data)[0];
  if (Array.isArray(first)) return String(first[0]);
  if (first && typeof first === "object") return messageFrom(first);
  return first ? String(first) : "";
}

let onAuthLost = () => {};
export const setAuthLostHandler = (fn) => { onAuthLost = fn; };

async function refresh() {
  const t = tokens.get();
  if (!t?.refresh) return false;
  const res = await fetch("/api/auth/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: t.refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  tokens.set({ access: data.access, refresh: data.refresh || t.refresh });
  return true;
}

async function request(path, { method = "GET", body, auth = true } = {}, retry = true) {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  const headers = isForm ? {} : { "Content-Type": "application/json" }; // le navigateur fixe la limite du multipart
  const t = tokens.get();
  if (auth && t?.access) headers.Authorization = `Bearer ${t.access}`;
  let res;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : isForm ? body : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, { detail: "Pas de connexion au serveur. Vérifie ton réseau." });
  }
  if (res.status === 401 && auth && retry && (await refresh())) return request(path, { method, body, auth }, false);
  if (res.status === 401 && auth) onAuthLost();
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

// Télécharge un fichier protégé (CSV) : un simple lien ne pourrait pas envoyer le jeton de connexion.
export async function downloadFile(path, filename) {
  const t = tokens.get();
  const res = await fetch(`/api${path}`, { headers: t?.access ? { Authorization: `Bearer ${t.access}` } : {} });
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null));
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: "POST", body: body ?? {} }),
  patch: (p, body) => request(p, { method: "PATCH", body }),
  put: (p, body) => request(p, { method: "PUT", body }),
  del: (p) => request(p, { method: "DELETE" }),
  upload: (p, formData) => request(p, { method: "POST", body: formData }),
  public: { post: (p, body) => request(p, { method: "POST", body, auth: false }) },
};
