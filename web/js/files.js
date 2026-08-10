import { api, getErrorMessage, showToast } from './api.js';

let activeTab = 'knowledge';

export function initFilesPanel() {
  document.getElementById('btn-files').addEventListener('click', () => {
    showFilesPanel();
  });

  document.getElementById('btn-files-close').addEventListener('click', () => {
    hideFilesPanel();
  });

  document.getElementById('files-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'files-overlay') hideFilesPanel();
  });

  document.querySelectorAll('[data-files-tab]').forEach((tab) => {
    tab.addEventListener('click', () => {
      activeTab = tab.dataset.filesTab;
      document.querySelectorAll('[data-files-tab]').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      loadFilesContent();
    });
  });
}

export function showFilesPanel() {
  document.getElementById('files-overlay').classList.remove('hidden');
  loadFilesContent();
}

export function hideFilesPanel() {
  document.getElementById('files-overlay').classList.add('hidden');
}

async function loadFilesContent() {
  const container = document.getElementById('files-content');
  container.innerHTML = '<div class="loading-text">加载中...</div>';

  try {
    if (activeTab === 'knowledge') {
      await renderKnowledgeList(container);
    } else {
      await renderAnalysisList(container);
    }
  } catch (err) {
    container.innerHTML = `<p class="error-text">${getErrorMessage(err)}</p>`;
    showToast(getErrorMessage(err));
  }
}

async function renderKnowledgeList(container) {
  const data = await api('/knowledge/documents?page=1&size=20');
  const items = data.items || [];

  if (!items.length) {
    container.innerHTML = '<p class="empty-list">暂无知识库文档</p>';
    return;
  }

  container.innerHTML = '';
  for (const doc of items) {
    container.appendChild(buildFileRow(doc.title, doc.status, doc.createdAt, doc.errorMessage));
  }
}

async function renderAnalysisList(container) {
  const data = await api('/analysis/jobs?page=1&size=20');
  const items = data.items || [];

  if (!items.length) {
    container.innerHTML = '<p class="empty-list">暂无分析任务</p>';
    return;
  }

  container.innerHTML = '';
  for (const job of items) {
    const row = buildFileRow(
      `${job.fileType} · ${job.jobId.slice(0, 8)}…`,
      job.status,
      job.createdAt,
      job.errorMessage,
    );
    if (job.status === 'COMPLETED' && job.resultSummary) {
      const summary = document.createElement('div');
      summary.className = 'file-row-summary';
      summary.textContent = job.resultSummary;
      row.appendChild(summary);
    }
    container.appendChild(row);
  }
}

function buildFileRow(title, status, createdAt, errorMessage) {
  const row = document.createElement('div');
  row.className = 'file-row';

  const titleEl = document.createElement('div');
  titleEl.className = 'file-row-title';
  titleEl.textContent = title;

  const meta = document.createElement('div');
  meta.className = 'file-row-meta';
  const time = createdAt ? new Date(createdAt).toLocaleString('zh-CN') : '';
  meta.textContent = `${status}${time ? ' · ' + time : ''}`;

  row.appendChild(titleEl);
  row.appendChild(meta);

  if (status === 'FAILED' && errorMessage) {
    const err = document.createElement('div');
    err.className = 'file-row-summary message-error';
    err.textContent = errorMessage;
    row.appendChild(err);
  }

  return row;
}
