import { api, sleep, getErrorMessage, showToast } from './api.js';
import { appendSystemMessage, updateSystemMessage } from './chat.js';

const KNOWLEDGE_EXTS = new Set(['pdf', 'md', 'txt']);
const ANALYSIS_EXTS = new Set(['log', 'txt', 'hprof']);
const KNOWLEDGE_MAX = 20 * 1024 * 1024;
const ANALYSIS_MAX = 100 * 1024 * 1024;

let pendingTxtFile = null;
let txtChoiceResolve = null;

export function getFileExtension(filename) {
  const idx = filename.lastIndexOf('.');
  if (idx < 0) return '';
  return filename.slice(idx + 1).toLowerCase();
}

export function routeUploadType(filename) {
  const ext = getFileExtension(filename);
  if (['pdf', 'md'].includes(ext)) return 'knowledge';
  if (['hprof', 'log'].includes(ext)) return 'analysis';
  if (ext === 'txt') return 'choice';
  return null;
}

export function validateFileSize(file, type) {
  const max = type === 'knowledge' ? KNOWLEDGE_MAX : ANALYSIS_MAX;
  if (file.size > max) {
    const mb = type === 'knowledge' ? 20 : 100;
    throw { message: `文件不能超过 ${mb}MB` };
  }
}

export function initTxtChoiceDialog() {
  document.getElementById('txt-knowledge').addEventListener('click', () => {
    resolveTxtChoice('knowledge');
  });
  document.getElementById('txt-analysis').addEventListener('click', () => {
    resolveTxtChoice('analysis');
  });
  document.getElementById('txt-cancel').addEventListener('click', () => {
    resolveTxtChoice(null);
  });
}

function resolveTxtChoice(type) {
  document.getElementById('txt-choice-overlay').classList.add('hidden');
  if (txtChoiceResolve) {
    txtChoiceResolve(type);
    txtChoiceResolve = null;
  }
  pendingTxtFile = null;
}

export function askTxtChoice(file) {
  pendingTxtFile = file;
  document.getElementById('txt-choice-filename').textContent = file.name;
  document.getElementById('txt-choice-overlay').classList.remove('hidden');
  return new Promise((resolve) => {
    txtChoiceResolve = resolve;
  });
}

async function uploadKnowledge(file) {
  const form = new FormData();
  form.append('file', file);
  form.append('title', file.name);
  return api('/knowledge/documents', { method: 'POST', body: form });
}

async function uploadAnalysis(file) {
  const form = new FormData();
  form.append('file', file);
  return api('/analysis/jobs', { method: 'POST', body: form });
}

async function pollKnowledge(documentId, systemEl, filename) {
  const intervals = { PENDING: 2000, PROCESSING: 3000 };
  for (let i = 0; i < 60; i++) {
    const doc = await api(`/knowledge/documents/${documentId}`);
    if (doc.status === 'COMPLETED') {
      updateSystemMessage(systemEl, `✅ ${filename} 入库完成，可在对话中提问`);
      return;
    }
    if (doc.status === 'FAILED') {
      updateSystemMessage(
        systemEl,
        `❌ ${filename} 入库失败：${doc.errorMessage || '未知错误'}`,
      );
      return;
    }
    await sleep(intervals[doc.status] ?? 3000);
  }
  updateSystemMessage(
    systemEl,
    `⏳ ${filename} 处理时间较长，请在「文件 → 知识库」中查看`,
  );
}

async function pollAnalysis(jobId, systemEl, filename) {
  const intervals = { PENDING: 2000, PROCESSING: 3000 };
  for (let i = 0; i < 60; i++) {
    const job = await api(`/analysis/jobs/${jobId}`);
    if (job.status === 'COMPLETED') {
      let msg = `✅ ${filename} 分析完成，可在对话中提问`;
      if (job.resultSummary) {
        msg += `\n摘要：${job.resultSummary}`;
      }
      updateSystemMessage(systemEl, msg);
      return;
    }
    if (job.status === 'FAILED') {
      updateSystemMessage(
        systemEl,
        `❌ ${filename} 分析失败：${job.errorMessage || '未知错误'}`,
      );
      return;
    }
    await sleep(intervals[job.status] ?? 3000);
  }
  updateSystemMessage(
    systemEl,
    `⏳ ${filename} 处理时间较长，请在「文件 → 分析任务」中查看`,
  );
}

export async function handleFileUpload(file, uploadType) {
  if (!uploadType) {
    showToast('不支持的文件类型');
    return;
  }

  try {
    validateFileSize(file, uploadType);
  } catch (err) {
    showToast(getErrorMessage(err));
    return;
  }

  const label = uploadType === 'knowledge' ? '入库' : '分析';
  const systemEl = appendSystemMessage(`📄 ${file.name} 已提交${label}，处理中...`);

  try {
    if (uploadType === 'knowledge') {
      const res = await uploadKnowledge(file);
      pollKnowledge(res.documentId, systemEl, file.name).catch((err) => {
        updateSystemMessage(systemEl, `❌ ${file.name}：${getErrorMessage(err)}`);
      });
    } else {
      const res = await uploadAnalysis(file);
      pollAnalysis(res.jobId, systemEl, file.name).catch((err) => {
        updateSystemMessage(systemEl, `❌ ${file.name}：${getErrorMessage(err)}`);
      });
    }
  } catch (err) {
    updateSystemMessage(systemEl, `❌ ${file.name}：${getErrorMessage(err)}`);
    showToast(getErrorMessage(err));
  }
}

export async function processSelectedFile(file) {
  const route = routeUploadType(file.name);
  if (!route) {
    showToast('不支持的文件类型（支持：pdf, md, txt, log, hprof）');
    return;
  }

  let uploadType = route;
  if (route === 'choice') {
    uploadType = await askTxtChoice(file);
    if (!uploadType) return;
  }

  await handleFileUpload(file, uploadType);
}

export { KNOWLEDGE_EXTS, ANALYSIS_EXTS };
