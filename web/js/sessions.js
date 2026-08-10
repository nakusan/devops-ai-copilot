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

export function renderSessionList(sessions, currentId, { onSelect, onDelete }) {
  const container = document.getElementById('session-list');
  container.innerHTML = '';

  if (!sessions.length) {
    container.innerHTML = '<p class="empty-list">暂无对话</p>';
    return;
  }

  const groups = groupSessionsByDate(sessions);

  for (const [label, items] of groups) {
    const groupLabel = document.createElement('div');
    groupLabel.className = 'session-group-label';
    groupLabel.textContent = label;
    container.appendChild(groupLabel);

    for (const session of items) {
      const item = document.createElement('div');
      item.className = 'session-item' + (session.id === currentId ? ' active' : '');
      item.dataset.id = session.id;

      const title = document.createElement('span');
      title.className = 'session-item-title';
      title.textContent = session.title || DEFAULT_TITLE;

      const delBtn = document.createElement('button');
      delBtn.className = 'session-item-delete';
      delBtn.type = 'button';
      delBtn.textContent = '×';
      delBtn.title = '删除';
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        onDelete(session.id);
      });

      item.appendChild(title);
      item.appendChild(delBtn);
      item.addEventListener('click', () => onSelect(session.id));
      container.appendChild(item);
    }
  }
}

export function deriveTitleFromMessage(content) {
  const trimmed = content.trim();
  if (trimmed.length <= 30) return trimmed;
  return trimmed.slice(0, 30) + '…';
}

export { DEFAULT_TITLE };
