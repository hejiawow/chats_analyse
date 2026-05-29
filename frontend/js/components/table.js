/* ============================================
   Table Renderer — 表格渲染器
   ============================================ */

function renderEmptyRow(colspan, message = '暂无记录') {
  return `<tr><td colspan="${colspan}" class="table-empty">${message}</td></tr>`;
}

function renderPagination(containerPrefix, data) {
  const countEl = document.getElementById(`${containerPrefix}-count`);
  const pageEl = document.getElementById(`${containerPrefix}-page`);

  if (countEl) countEl.textContent = `共 ${data.total || 0} 条`;
  if (pageEl) pageEl.textContent = `第 ${data.page || 1} 页`;
}

function renderPaginationButtons(prefix, data) {
  const prevBtn = document.getElementById(`${prefix}-prev-btn`);
  const nextBtn = document.getElementById(`${prefix}-next-btn`);

  if (prevBtn) prevBtn.disabled = data.page <= 1;
  if (nextBtn) nextBtn.disabled = data.page * data.page_size >= data.total;
}
