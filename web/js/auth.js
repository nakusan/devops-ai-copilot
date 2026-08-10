import { apiPublic, setTokens, clearTokens, getErrorMessage, showToast } from './api.js';

let authMode = 'login';

export function initAuth(onSuccess) {
  const overlay = document.getElementById('auth-overlay');
  const form = document.getElementById('auth-form');
  const errorEl = document.getElementById('auth-error');
  const submitBtn = document.getElementById('auth-submit');

  document.querySelectorAll('.auth-modal .tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      authMode = tab.dataset.tab;
      document.querySelectorAll('.auth-modal .tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      submitBtn.textContent = authMode === 'login' ? '登录' : '注册';
      errorEl.classList.add('hidden');
    });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.classList.add('hidden');
    submitBtn.disabled = true;

    const username = document.getElementById('auth-username').value.trim();
    const password = document.getElementById('auth-password').value;

    try {
      const path = authMode === 'login' ? '/auth/login' : '/auth/register';
      const data = await apiPublic(path, {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      setTokens(data.accessToken, data.refreshToken, username);
      overlay.classList.add('hidden');
      onSuccess();
    } catch (err) {
      errorEl.textContent = getErrorMessage(err);
      errorEl.classList.remove('hidden');
    } finally {
      submitBtn.disabled = false;
    }
  });

  document.getElementById('btn-logout').addEventListener('click', () => {
    clearTokens();
    overlay.classList.remove('hidden');
    document.getElementById('app').classList.add('hidden');
    onSuccess(false);
  });
}

export function showAuthOverlay() {
  document.getElementById('auth-overlay').classList.remove('hidden');
}

export function hideAuthOverlay() {
  document.getElementById('auth-overlay').classList.add('hidden');
}

export function updateUsernameLabel(username) {
  document.getElementById('username-label').textContent = username || '';
}

export function handleAuthError(err) {
  if (err?.code === 'AUTH_INVALID') {
    showAuthOverlay();
    document.getElementById('app').classList.add('hidden');
    showToast(getErrorMessage(err));
  }
}
