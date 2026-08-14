import { api, getErrorMessage, showToast } from './api.js';

let activeTab = 'knowledge';

// 后端只允许删除终态记录，处理中会返回 409；这里同步该规则以禁用按钮
const DELETABLE_STATUSES = new Set(['COMPLETED', 'FAILED']);

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
    container.appendChild(
      buildFileRow({
        title: doc.title,
        status: doc.status,
        createdAt: doc.createdAt,
        errorMessage: doc.errorMessage,
        confirmMessage:
          `确定删除「${doc.title}」？\n\n` +
          '文档、已生成的向量切片和原始文件都会被永久删除，之后 AI 无法再引用其中内容。',
        doDelete: () => api(`/knowledge/documents/${doc.documentId}`, { method: 'DELETE' }),
        deletedToast: '文档已删除',
      }),
    );
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
    const row = buildFileRow({
      title: `${job.fileType} · ${job.jobId.slice(0, 8)}…`,
      status: job.status,
      createdAt: job.createdAt,
      errorMessage: job.errorMessage,
      confirmMessage: '确定删除该分析任务？\n\n上传的原文件与分析结果都会被永久删除。',
      doDelete: () => api(`/analysis/jobs/${job.jobId}`, { method: 'DELETE' }),
      deletedToast: '分析任务已删除',
    });
    if (job.status === 'COMPLETED' && job.resultSummary) {
      const summary = document.createElement('div');
      summary.className = 'file-row-summary';
      summary.textContent = job.resultSummary;
      row.appendChild(summary);
    }
    container.appendChild(row);
  }
}

function buildFileRow({
  title,
  status,
  createdAt,
  errorMessage,
  confirmMessage,
  doDelete,
  deletedToast,
}) {
  const row = document.createElement('div');
  row.className = 'file-row';

  const head = document.createElement('div');
  head.className = 'file-row-head';

  const titleEl = document.createElement('div');
  titleEl.className = 'file-row-title';
  titleEl.textContent = title;
  titleEl.title = title;

  head.appendChild(titleEl);
  head.appendChild(buildDeleteButton({ status, confirmMessage, doDelete, deletedToast }));
  row.appendChild(head);

  const meta = document.createElement('div');
  meta.className = 'file-row-meta';
  const time = createdAt ? new Date(createdAt).toLocaleString('zh-CN') : '';
  meta.textContent = `${status}${time ? ' · ' + time : ''}`;
  row.appendChild(meta);

  if (status === 'FAILED' && errorMessage) {
    const err = document.createElement('div');
    err.className = 'file-row-summary message-error';
    err.textContent = errorMessage;
    row.appendChild(err);
  }

  return row;
}

function buildDeleteButton({ status, confirmMessage, doDelete, deletedToast }) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'file-row-delete';
  btn.textContent = '删除';

  if (!DELETABLE_STATUSES.has(status)) {
    btn.disabled = true;
    btn.title = '处理中，完成或失败后才能删除';
    return btn;
  }

  btn.addEventListener('click', async () => {
    if (!confirm(confirmMessage)) return;
    btn.disabled = true;
    try {
      await doDelete();
      showToast(deletedToast);
      // 重新拉列表而不是就地移除：顺带反映其他人/其他标签页的变更
      await loadFilesContent();
    } catch (err) {
      showToast(getErrorMessage(err));
      btn.disabled = false;
    }
  });

  return btn;
}
