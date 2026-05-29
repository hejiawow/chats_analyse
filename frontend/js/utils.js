/* ============================================
   Utils — 通用工具函数
   ============================================ */

function formatTime(t) {
  if (!t) return '-';
  try { return new Date(t).toLocaleString('zh-CN'); } catch { return t; }
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function genUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  // Reset animation
  const progressBar = t.style;
  setTimeout(() => t.classList.remove('show'), 3000);
}

function closeModal(e) {
  if (e.target === e.currentTarget) {
    e.currentTarget.classList.remove('show');
  }
}

function showEmptyState(containerId, message = '暂无记录', icon = '') {
  const container = document.getElementById(containerId);
  if (container) {
    container.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">${icon}</div>
      <div class="empty-state-text">${message}</div>
    </div>`;
  }
}
