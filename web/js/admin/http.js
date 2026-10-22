import { ApiError } from '../api.js';

const TOKEN_KEY = 'plantando-ideias:token';

export function getToken() {
  try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token) {
  try { token ? sessionStorage.setItem(TOKEN_KEY, token) : sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}

async function request(path, { method = 'GET', json, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  const response = await fetch(path, { method, headers, body, cache: 'no-store' });
  if (response.status === 401 && !path.endsWith('/login')) {
    setToken(null);
    location.hash = '#/login';
  }
  return response;
}

async function errorFrom(response) {
  let data = null;
  try { data = await response.json(); } catch { /* not json */ }
  if (data && Array.isArray(data.detail)) {
    data = { detail: data.detail.map((d) => d.msg.replace(/^Value error, /, '')).join(' ') };
  }
  return new ApiError(response.status, data);
}

export async function adminApi(path, options) {
  const response = await request(path, options);
  if (!response.ok) throw await errorFrom(response);
  return response.status === 204 ? null : response.json();
}

export async function adminBlob(path) {
  const response = await request(path);
  if (!response.ok) throw await errorFrom(response);
  return response.blob();
}

export async function download(path, filename) {
  const url = URL.createObjectURL(await adminBlob(path));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
