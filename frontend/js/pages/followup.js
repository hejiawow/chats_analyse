/* ============================================
   Follow-Up Compliance Page
   ============================================ */

let followUpPage = 1;

async function loadFollowUp(reset) {
  if (reset) followUpPage = 1;
  const uid = document.getElementById('fu-user-id')?.value;
  const fid = document.getElementById('fu-friend-id')?.value;
  const compliant = document.getElementById('fu-compliant')?.value;

  let url = `/api/follow-up?page=${followUpPage}&page_size=${PAGE_SIZE.followup}`;
  if (uid) url += `&user_id=${encodeURIComponent(uid)}`;
  if (fid) url += `&friend_id=${parseInt(fid)}`;
  if (compliant) url += `&is_compliant=${compliant}`;

  const data = await apiFetch(url);
  const tbody = document.getElementById('followup-table');
  if (data?.data?.length) {
    tbody.innerHTML = data.data.map(renderFollowUpRow).join('');
    renderPagination('followup', data);
  } else {
    tbody.innerHTML = renderEmptyRow(9);
    renderPagination('followup', { total: 0, page: 1 });
  }
}

function renderFollowUpRow(r) {
  const isCompliant = r.is_compliant === 'compliant';
  const badge = isCompliant
    ? '<span class="badge success">合规</span>'
    : '<span class="badge danger">不合规</span>';

  const violationWindows = r.violation_windows || [];
  const createdTime = r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : '-';

  return `<tr>
    <td>${badge}</td>
    <td>${r.user_id || '-'}</td>
    <td>${r.friend_nick || '-'}</td>
    <td>${r.total_follow_up_days || 0}</td>
    <td>${r.chat_date_range || '-'}</td>
    <td>${r.min_window_count || 0}/11</td>
    <td>${violationWindows.length}</td>
    <td>${createdTime}</td>
    <td><button class="btn btn-outline btn-sm" onclick="showFollowUpDetail(${r.id})">详情</button></td>
  </tr>`;
}

async function showFollowUpDetail(id) {
  const r = await apiFetch(`/api/follow-up/${id}`);
  if (r.error) { toast(r.error); return; }

  const isCompliant = r.is_compliant === 'compliant';
  const violationWindows = r.violation_windows || [];

  let windowsHtml = '';
  if (violationWindows.length > 0) {
    windowsHtml = `
      <div style="margin-top:var(--space-4)">
        <h4 style="color:var(--danger);font-size:var(--text-base)">违规窗口详情</h4>
        <div style="margin-top:var(--space-2)">
          ${violationWindows.map(w => `
            <div style="background:var(--danger-bg);border:1px solid #fecaca;border-radius:var(--radius-sm);padding:var(--space-3);margin-bottom:var(--space-2)">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:600">${w.start} ~ ${w.end}</span>
                <span style="color:var(--danger);font-weight:600">跟进 ${w.count} 天 (要求≥11天)</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  const html = `
    <div style="padding:var(--space-2)">
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:var(--space-3);margin-bottom:var(--space-4)">
        <div><strong>合规状态:</strong> ${isCompliant ? '<span class="badge success">合规</span>' : '<span class="badge danger">不合规</span>'}</div>
        <div><strong>销售ID:</strong> ${r.user_id || '-'}</div>
        <div><strong>好友昵称:</strong> ${r.friend_nick || '-'}</div>
        <div><strong>总跟进天数:</strong> ${r.total_follow_up_days || 0} 天</div>
        <div><strong>日期范围:</strong> ${r.chat_date_range || '-'}</div>
        <div><strong>最低窗口次数:</strong> ${r.min_window_count || 0}/11</div>
      </div>
      ${windowsHtml}
    </div>
  `;

  document.getElementById('detail-content').innerHTML = html;
  document.getElementById('detail-modal').classList.add('show');
}
