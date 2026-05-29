/* ============================================
   Dashboard Page
   ============================================ */

async function loadDashboard() {
  const stats = await apiFetch('/api/stats');
  if (stats) {
    const tasksEl = document.getElementById('stat-tasks');
    const referralEl = document.getElementById('stat-referral');
    const casesEl = document.getElementById('stat-cases');
    const successEl = document.getElementById('stat-success');
    const agentsEl = document.getElementById('stat-agents');
    const changeEl = document.getElementById('stat-tasks-change');

    if (tasksEl) tasksEl.textContent = stats.today_tasks ?? 0;
    if (referralEl) referralEl.textContent = stats.referral_sent ?? 0;
    if (casesEl) casesEl.textContent = stats.cases_found ?? 0;
    if (successEl) successEl.textContent = stats.sj_count ?? 0;
    if (agentsEl) agentsEl.textContent = stats.active_agents ?? 0;
    if (changeEl) changeEl.textContent = `转介绍: ${stats.referral_sent || 0} / 案例: ${stats.cases_found || 0} / 成交: ${stats.sj_count || 0} / 督学: ${stats.fu_compliant || 0}合规 ${stats.fu_non_compliant || 0}不合规`;
  }

  const data = await apiFetch('/api/referral?page=1&page_size=5');
  const tbody = document.getElementById('recent-table');
  if (tbody) {
    if (data?.data?.length) {
      tbody.innerHTML = data.data.map(renderReferralRow).join('');
    } else if (!apiAvailable) {
      tbody.innerHTML = `<tr><td colspan="6" class="table-empty">后端未启动，暂无数据</td></tr>`;
    } else {
      tbody.innerHTML = `<tr><td colspan="6" class="table-empty">暂无分析记录</td></tr>`;
    }
  }
}
