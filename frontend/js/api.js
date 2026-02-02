/**
 * API client — handles authentication headers and base URL.
 */

const API_BASE = '/api';

function getToken() {
  return localStorage.getItem('ito_token');
}

function setAuth(data) {
  localStorage.setItem('ito_token', data.access_token);
  localStorage.setItem('ito_user_id', data.user_id);
  localStorage.setItem('ito_role', data.role);
  localStorage.setItem('ito_name', data.full_name);
}

function clearAuth() {
  localStorage.removeItem('ito_token');
  localStorage.removeItem('ito_user_id');
  localStorage.removeItem('ito_role');
  localStorage.removeItem('ito_name');
}

function isLoggedIn() {
  return !!getToken();
}

function getUserRole() {
  return localStorage.getItem('ito_role') || '';
}

function getUserName() {
  return localStorage.getItem('ito_name') || '';
}

async function api(path, options = {}) {
  const token = getToken();
  const headers = options.headers || {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearAuth();
    window.location.reload();
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

function apiGet(path) {
  return api(path);
}

function apiPost(path, body) {
  return api(path, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

function apiPut(path, body) {
  return api(path, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

function apiDelete(path) {
  return api(path, { method: 'DELETE' });
}

async function apiUpload(path, file) {
  const fd = new FormData();
  fd.append('file', file);
  return api(path, { method: 'POST', body: fd });
}
