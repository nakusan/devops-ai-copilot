import { isLoggedIn, getUsername, getErrorMessage, showToast } from './api.js';
import { initAuth, showAuthOverlay, hideAuthOverlay, updateUsernameLabel, handleAuthError } from './auth.js';
import {
  fetchSessions,
  createSession,
  updateSession,
  deleteSession,
  renderSessionList,
  deriveTitleFromMessage,
  isSessionArchived,
  DEFAULT_TITLE,
} from './sessions.js';
import {
  loadMessages,
  renderMessages,
  appendUserMessage,
  appendAssistantMessage,
  showEmptyState,
  clearMessages,
  streamChat,
  showChatLoading,
  hideChatLoading,
  showAssistantError,
  finishAssistantMessage,
  isStreaming,
  isComposerReadOnly,
  setComposerReadOnly,
  scrollToBottom,
} from './chat.js';
import { initTxtChoiceDialog, processSelectedFile } from './upload.js';
import { initFilesPanel } from './files.js';

let sessions = [];
let currentSessionId = null;
let currentSessionTitle = DEFAULT_TITLE;

async function bootstrap(loggedIn) {
  if (!loggedIn) {
    showAuthOverlay();
    return;
  }

  hideAuthOverlay();
  document.getElementById('app').classList.remove('hidden');
  updateUsernameLabel(getUsername());
  await refreshSessions();
  showWelcomeState();
}

async function refreshSessions() {
  sessions = await fetchSessions();
  renderSessionList(sessions, currentSessionId, {
    onSelect: selectSession,
    onDelete: removeSession,
  });
}

function showWelcomeState() {
  currentSessionId = null;
  currentSessionTitle = DEFAULT_TITLE;
  setComposerReadOnly(false);
  clearMessages();
  showEmptyState(true);
  renderSessionList(sessions, null, {
    onSelect: selectSession,
    onDelete: removeSession,
  });
}

async function startNewChat() {
  if (isStreaming()) return;
  currentSessionId = null;
  currentSessionTitle = DEFAULT_TITLE;
  setComposerReadOnly(false);
  clearMessages();
  showEmptyState(true);
  renderSessionList(sessions, null, {
    onSelect: selectSession,
    onDelete: removeSession,
  });
  document.getElementById('message-input').focus();
}

async function ensureSession() {
  if (currentSessionId) {
    const current = sessions.find((s) => s.id === currentSessionId);
    if (isSessionArchived(current)) {
      throw { code: 'FORBIDDEN', message: '会话已归档，无法继续对话' };
    }
    return currentSessionId;
  }

  const session = await createSession(DEFAULT_TITLE);
  currentSessionId = session.id;
  currentSessionTitle = session.title || DEFAULT_TITLE;
  setComposerReadOnly(false);
  sessions.unshift(session);
  renderSessionList(sessions, currentSessionId, {
    onSelect: selectSession,
    onDelete: removeSession,
  });
  return currentSessionId;
}

async function selectSession(sessionId) {
  if (isStreaming() || sessionId === currentSessionId) return;

  currentSessionId = sessionId;
  const session = sessions.find((s) => s.id === sessionId);
  currentSessionTitle = session?.title || DEFAULT_TITLE;
  setComposerReadOnly(isSessionArchived(session));

  renderSessionList(sessions, currentSessionId, {
    onSelect: selectSession,
    onDelete: removeSession,
  });

  showChatLoading();
  try {
    const messages = await loadMessages(sessionId);
    hideChatLoading();
    if (messages.length) {
      renderMessages(messages);
    } else {
      clearMessages();
      showEmptyState(true);
    }
  } catch (err) {
    hideChatLoading();
    showToast(getErrorMessage(err));
    handleAuthError(err);
  }
}

async function removeSession(sessionId) {
  if (isStreaming()) return;
  if (!confirm('确定归档此对话？归档后仅可查看，不能继续发送消息。')) return;

  try {
    await deleteSession(sessionId);
    const session = sessions.find((s) => s.id === sessionId);
    if (session) {
      session.status = 'ARCHIVED';
      session.updatedAt = new Date().toISOString();
    }
    if (currentSessionId === sessionId) {
      setComposerReadOnly(true);
    }
    renderSessionList(sessions, currentSessionId, {
      onSelect: selectSession,
      onDelete: removeSession,
    });
  } catch (err) {
    showToast(getErrorMessage(err));
    handleAuthError(err);
  }
}

async function maybeUpdateSessionTitle(content) {
  if (currentSessionTitle !== DEFAULT_TITLE) return;

  const title = deriveTitleFromMessage(content);
  try {
    await updateSession(currentSessionId, { title });
    currentSessionTitle = title;
    const session = sessions.find((s) => s.id === currentSessionId);
    if (session) session.title = title;
    renderSessionList(sessions, currentSessionId, {
      onSelect: selectSession,
      onDelete: removeSession,
    });
  } catch {
    // 标题更新失败不影响对话
  }
}

async function sendMessage() {
  if (isStreaming() || isComposerReadOnly()) return;

  const input = document.getElementById('message-input');
  const content = input.value.trim();
  if (!content) return;

  input.value = '';
  input.style.height = 'auto';

  try {
    const sessionId = await ensureSession();
    appendUserMessage(content);
    scrollToBottom();

    const assistantEl = appendAssistantMessage('');
    let citationData = null;

    await streamChat(sessionId, content, {
      onToken(text) {
        assistantEl.textContent += text;
        scrollToBottom();
      },
      onCitation(data) {
        citationData = data;
      },
      onDone() {
        finishAssistantMessage(assistantEl, citationData);
        scrollToBottom();
      },
      onError(err) {
        showAssistantError(assistantEl, err);
        scrollToBottom();
      },
    });

    await maybeUpdateSessionTitle(content);
    await refreshSessions();
  } catch (err) {
    showToast(getErrorMessage(err));
    handleAuthError(err);
  }
}

function setupComposer() {
  const input = document.getElementById('message-input');
  const sendBtn = document.getElementById('btn-send');
  const attachBtn = document.getElementById('btn-attach');
  const fileInput = document.getElementById('file-input');

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 200) + 'px';
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener('click', sendMessage);

  attachBtn.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0];
    fileInput.value = '';
    if (!file) return;

    if (!isLoggedIn()) {
      showAuthOverlay();
      return;
    }

    if (isComposerReadOnly()) {
      showToast('已归档会话不可上传文件');
      return;
    }

    try {
      await ensureSession();
      await processSelectedFile(file);
    } catch (err) {
      showToast(getErrorMessage(err));
      handleAuthError(err);
    }
  });
}

function init() {
  initAuth((loggedIn) => bootstrap(loggedIn !== false && isLoggedIn()));
  initTxtChoiceDialog();
  initFilesPanel();
  setupComposer();

  document.getElementById('btn-new-chat').addEventListener('click', startNewChat);

  if (isLoggedIn()) {
    bootstrap(true);
  } else {
    showAuthOverlay();
  }
}

init();
