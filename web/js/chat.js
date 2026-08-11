import { api, getAccessToken, tryRefreshToken, clearTokens, getErrorMessage } from './api.js';

let streaming = false;
let composerReadOnly = false;

export function isStreaming() {
  return streaming;
}

export function setStreaming(value) {
  streaming = value;
  updateComposerDisabled();
}

/** 归档会话仅可查看历史，禁用输入区。 */
export function setComposerReadOnly(value) {
  composerReadOnly = Boolean(value);
  updateComposerDisabled();
}

export function isComposerReadOnly() {
  return composerReadOnly;
}

function updateComposerDisabled() {
  const sendBtn = document.getElementById('btn-send');
  const input = document.getElementById('message-input');
  const attachBtn = document.getElementById('btn-attach');
  const wrap = document.querySelector('.composer-wrap');
  const notice = document.getElementById('archived-notice');
  const disabled = streaming || composerReadOnly;

  sendBtn.disabled = disabled;
  attachBtn.disabled = disabled;
  input.disabled = disabled;
  wrap?.classList.toggle('composer-readonly', composerReadOnly);
  notice?.classList.toggle('hidden', !composerReadOnly);

  if (composerReadOnly) {
    input.placeholder = '已归档会话不可继续对话';
    input.value = '';
    input.style.height = 'auto';
  } else if (!streaming) {
    input.placeholder = '输入你的问题...';
  }
}

export async function loadMessages(sessionId, page = 1, size = 50) {
  const data = await api(`/sessions/${sessionId}/messages?page=${page}&size=${size}`);
  return data.items || [];
}

export function showEmptyState(show) {
  document.getElementById('empty-state').classList.toggle('hidden', !show);
  document.getElementById('messages').classList.toggle('hidden', show);
}

export function clearMessages() {
  const container = document.getElementById('messages');
  container.innerHTML = '<div class="messages-inner"></div>';
}

export function getMessagesInner() {
  let inner = document.querySelector('#messages .messages-inner');
  if (!inner) {
    clearMessages();
    inner = document.querySelector('#messages .messages-inner');
  }
  return inner;
}

export function renderMessages(messages) {
  clearMessages();
  showEmptyState(false);
  const inner = getMessagesInner();

  for (const msg of messages) {
    appendMessageElement(inner, msg.role, msg.content, msg.metadataJson);
  }

  scrollToBottom();
}

function appendMessageElement(container, role, content, metadata) {
  const el = document.createElement('div');
  el.className = `message message-${role.toLowerCase()}`;

  if (role === 'system') {
    el.className = 'message message-system';
  }

  el.textContent = content;

  if (metadata?.citations?.length) {
    const cite = document.createElement('div');
    cite.className = 'message-citation';
    cite.textContent = '引用：' + metadata.citations.map((c) => c.docTitle || c.chunkId).join('、');
    el.appendChild(cite);
  }

  container.appendChild(el);
  return el;
}

export function appendUserMessage(content) {
  showEmptyState(false);
  const inner = getMessagesInner();
  return appendMessageElement(inner, 'user', content);
}

export function appendAssistantMessage(content = '') {
  showEmptyState(false);
  const inner = getMessagesInner();
  const el = appendMessageElement(inner, 'assistant', content);
  el.classList.add('cursor-blink');
  return el;
}

export function appendSystemMessage(content) {
  showEmptyState(false);
  const inner = getMessagesInner();
  const el = appendMessageElement(inner, 'system', content);
  el.dataset.system = 'true';
  return el;
}

export function updateSystemMessage(el, content) {
  el.textContent = content;
  scrollToBottom();
}

export function scrollToBottom() {
  const area = document.getElementById('chat-area');
  area.scrollTop = area.scrollHeight;
}

function parseSseBlock(block, handlers) {
  let eventName = 'message';
  let data = '';

  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      data += line.slice(5).trim();
    }
  }

  if (!data) return;

  let parsed;
  try {
    parsed = JSON.parse(data);
  } catch {
    return;
  }

  switch (eventName) {
    case 'token':
      handlers.onToken(parsed.text ?? '');
      break;
    case 'citation':
      handlers.onCitation?.(parsed);
      break;
    case 'done':
      handlers.onDone(parsed);
      break;
    case 'error':
      handlers.onError(parsed);
      break;
    default:
      break;
  }
}

export async function streamChat(sessionId, content, handlers) {
  setStreaming(true);

  let res = await fetch(`/api/v1/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getAccessToken()}`,
    },
    body: JSON.stringify({
      content,
      clientMessageId: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    }),
  });

  if (res.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      res = await fetch(`/api/v1/sessions/${sessionId}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({
          content,
          clientMessageId: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        }),
      });
    } else {
      clearTokens();
      setStreaming(false);
      throw { code: 'AUTH_INVALID', message: '登录已过期，请重新登录' };
    }
  }

  if (!res.ok) {
    setStreaming(false);
    let err;
    try {
      err = await res.json();
    } catch {
      err = { message: `HTTP ${res.status}` };
    }
    throw err;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() ?? '';
      for (const block of blocks) {
        if (block.trim()) {
          parseSseBlock(block, handlers);
        }
      }
    }
    if (buffer.trim()) {
      parseSseBlock(buffer, handlers);
    }
  } finally {
    setStreaming(false);
  }
}

export function showChatLoading() {
  showEmptyState(false);
  clearMessages();
  const inner = getMessagesInner();
  const loading = document.createElement('div');
  loading.className = 'loading-text';
  loading.id = 'chat-loading';
  loading.textContent = '加载中...';
  inner.appendChild(loading);
}

export function hideChatLoading() {
  document.getElementById('chat-loading')?.remove();
}

export function showAssistantError(el, message) {
  el.classList.remove('cursor-blink');
  el.classList.add('message-error');
  el.textContent = getErrorMessage(message);
}

export function finishAssistantMessage(el, citationData) {
  el.classList.remove('cursor-blink');
  if (citationData?.chunks?.length) {
    const cite = document.createElement('div');
    cite.className = 'message-citation';
    cite.textContent =
      '引用：' + citationData.chunks.map((c) => c.docTitle || c.chunkId).join('、');
    el.appendChild(cite);
  }
}
