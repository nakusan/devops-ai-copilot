const ACCESS_KEY = 'accessToken';
const REFRESH_KEY = 'refreshToken';
const USERNAME_KEY = 'username';

let refreshPromise = null;

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function getUsername() {
  return localStorage.getItem(USERNAME_KEY);
}

export function setTokens(accessToken, refreshToken, username) {
  localStorage.setItem(ACCESS_KEY, accessToken);
  localStorage.setItem(REFRESH_KEY, refreshToken);
  if (username) {
    localStorage.setItem(USERNAME_KEY, username);
  }
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USERNAME_KEY);
}

export function isLoggedIn() {
  return Boolean(getAccessToken());
}

export function getErrorMessage(err) {
  if (!err) return '未知错误';
  if (typeof err === 'string') return err;
  if (err.message) return err.message;
  return '请求失败';
}

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  const res = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refreshToken }),
  });

  if (!res.ok) {
    clearTokens();
    return false;
  }

  const data = await res.json();
  setTokens(data.accessToken, data.refreshToken);
  return true;
}

export async function tryRefreshToken() {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function apiPublic(path, options = {}) {
  const res = await fetch('/api/v1' + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    let err;
    try {
      err = await res.json();
    } catch {
      err = { message: `HTTP ${res.status}` };
    }
    throw err;
  }

  return res.status === 204 ? null : res.json();
}

export async function api(path, options = {}, retried = false) {
  const isForm = options.body instanceof FormData;
  const headers = {
    ...(isForm ? {} : { 'Content-Type': 'application/json' }),
    ...options.headers,
  };

  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch('/api/v1' + path, { ...options, headers });

  if (res.status === 401 && !retried) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return api(path, options, true);
    }
    clearTokens();
    throw { code: 'AUTH_INVALID', message: '登录已过期，请重新登录' };
  }

  if (!res.ok) {
    let err;
    try {
      err = await res.json();
    } catch {
      err = { message: `HTTP ${res.status}` };
    }
    throw err;
  }

  if (res.status === 204) return null;

  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }

  return res.text();
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function showToast(message, durationMs = 3000) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.classList.remove('hidden');
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    el.classList.add('hidden');
  }, durationMs);
}
