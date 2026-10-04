const tokenKey = "desk_token";

export function getToken() {
  return localStorage.getItem(tokenKey);
}

export function setToken(token) {
  localStorage.setItem(tokenKey, token);
}

export function clearToken() {
  localStorage.removeItem(tokenKey);
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    clearToken();
  }
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

export const api = {
  login: (email, password) => request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request("/api/auth/me"),
  requests: () => request("/api/requests"),
  createRequest: (body) => request("/api/requests", { method: "POST", body: JSON.stringify(body) }),
  getRequest: (id) => request(`/api/requests/${id}`),
  transition: (id, status) =>
    request(`/api/requests/${id}/transition`, { method: "POST", body: JSON.stringify({ status }) }),
  assign: (id, episode_ids) =>
    request(`/api/requests/${id}/assignments`, { method: "POST", body: JSON.stringify({ episode_ids }) }),
  unassign: (id, episode_ids) =>
    request(`/api/requests/${id}/assignments`, { method: "DELETE", body: JSON.stringify({ episode_ids }) }),
  episodes: (params) => {
    const q = new URLSearchParams(params).toString();
    return request(`/api/episodes?${q}`);
  },
  importCsv: (file) => {
    const body = new FormData();
    body.append("file", file);
    return request("/api/episodes/import", { method: "POST", body });
  },
  users: () => request("/api/users"),
  updateUser: (id, body) => request(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
};
