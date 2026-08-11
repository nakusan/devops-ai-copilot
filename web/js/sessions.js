import { api } from './api.js';

const DEFAULT_AGENT_ID = 1;
const DEFAULT_TITLE = '新对话';

export async function fetchSessions() {
  return api('/sessions');
}

export async function createSession(title = DEFAULT_TITLE) {
  return api('/sessions', {
    method: 'POST',
    body: JSON.stringify({ agentId: DEFAULT_AGENT_ID, title }),
  });
}

export async function updateSession(id, payload) {
  return api(`/sessions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteSession(id) {
  return api(`/sessions/${id}`, { method: 'DELETE' });
}

export async function fetchSession(id) {
  return api(`/sessions/${id}`);
}

export function isSessionArchived(session) {
  return session?.status === 'ARCHIVED';
}

export function groupSessionsByDate(sessions) {
  const groups = new Map();
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);

  const sorted = [...sessions].sort(
    (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt),
  );

  for (const session of sorted) {
    const date = new Date(session.updatedAt);
    let label;
    if (date >= todayStart) {
      label = '今天';
    } else if (date >= yesterdayStart) {
      label = '昨天';
    } else {
      label = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    }
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(session);
  }

  return groups;
}

function appendSessionItem(container, session, currentId, { onSelect, onDelete }) {
  const item = document.createElement('div');
  const archived = isSessionArchived(session);
  item.className =
    'session-item' +
    (session.id === currentId ? ' active' : '') +
    (archived ? ' session-item-archived' : '');
  item.dataset.id = session.id;
  item.dataset.status = session.status || 'ACTIVE';

  const title = document.createElement('span');
  title.className = 'session-item-title';
  title.textContent = session.title || DEFAULT_TITLE;

  item.appendChild(title);

  if (!archived) {
    const delBtn = document.createElement('button');
    delBtn.className = 'session-item-delete';
    delBtn.type = 'button';
    delBtn.textContent = '×';
    delBtn.title = '归档';
    delBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      onDelete(session.id);
    });
    item.appendChild(delBtn);
  }

  item.addEventListener('click', () => onSelect(session.id));
  container.appendChild(item);
}

function appendDateGroups(container, sessions, currentId, handlers) {
  const groups = groupSessionsByDate(sessions);
  for (const [label, items] of groups) {
    const groupLabel = document.createElement('div');
    groupLabel.className = 'session-group-label';
    groupLabel.textContent = label;
    container.appendChild(groupLabel);

    for (const session of items) {
      appendSessionItem(container, session, currentId, handlers);
    }
  }
}

export function renderSessionList(sessions, currentId, { onSelect, onDelete }) {
  const container = document.getElementById('session-list');
  container.innerHTML = '';

  if (!sessions.length) {
    container.innerHTML = '<p class="empty-list">暂无对话</p>';
    return;
  }

  const active = sessions.filter((s) => !isSessionArchived(s));
  const archived = sessions.filter(isSessionArchived);

  const activePane = document.createElement('div');
  activePane.className = 'session-list-active';
  if (active.length) {
    appendDateGroups(activePane, active, currentId, { onSelect, onDelete });
  } else {
    activePane.innerHTML = '<p class="empty-list">暂无对话</p>';
  }
  container.appendChild(activePane);

  if (archived.length) {
    const archivedPane = document.createElement('div');
    archivedPane.className = 'session-list-archived';

    const archivedLabel = document.createElement('div');
    archivedLabel.className = 'session-group-label session-archived-label';
    archivedLabel.textContent = '已归档';
    archivedPane.appendChild(archivedLabel);

    const sortedArchived = [...archived].sort(
      (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt),
    );
    for (const session of sortedArchived) {
      appendSessionItem(archivedPane, session, currentId, { onSelect, onDelete });
    }
    container.appendChild(archivedPane);
  }
}

export function deriveTitleFromMessage(content) {
  const trimmed = content.trim();
  if (trimmed.length <= 30) return trimmed;
  return trimmed.slice(0, 30) + '…';
}

export { DEFAULT_TITLE };
