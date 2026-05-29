/* ============================================
   Referral Page
   ============================================ */

let referralPage = 1;

async function loadReferral() {
  const uid = document.getElementById('ref-user-id')?.value;
  const fid = document.getElementById('ref-friend-id')?.value;

  let url = `/api/referral?page=${referralPage}&page_size=${PAGE_SIZE.referral}`;
  if (uid) url += `&user_id=${encodeURIComponent(uid)}`;
  if (fid) url += `&friend_id=${parseInt(fid)}`;

  const data = await apiFetch(url);
  const tbody = document.getElementById('referral-table');
  if (data?.data?.length) {
    tbody.innerHTML = data.data.map(renderReferralRow).join('');
    renderPagination('referral', data);
  } else {
    tbody.innerHTML = renderEmptyRow(6);
    renderPagination('referral', { total: 0, page: 1 });
  }
}

function renderReferralRow(r) {
  const result = r.result || {};
  const isSent = result.status === '已发送';
  const badge = r.status === 'failed'
    ? '<span class="badge danger">失败</span>'
    : isSent
      ? '<span class="badge success">已发送</span>'
      : '<span class="badge warning">未发送</span>';

  const evidence = r.status === 'failed'
    ? (r.error_msg || '未知错误')
    : (result.evidence || '-');

  return `<tr>
    <td>${formatTime(r.created_at)}</td>
    <td><code>${r.user_id}</code></td>
    <td>${r.friend_nick || r.friend_id}</td>
    <td>${badge}</td>
    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(evidence)}">${escapeHtml(evidence)}</td>
    <td><button class="btn btn-outline btn-sm" onclick="showReferralDetail(${r.id})">详情</button></td>
  </tr>`;
}

async function showReferralDetail(id) {
  const r = await apiFetch(`/api/referral/${id}`);
  if (!r || !r.id) { toast('获取详情失败'); return; }

  const result = r.result || {};
  const html = `
    <div class="detail-grid">
      <div class="detail-item"><label>销售ID</label><span>${escapeHtml(r.user_id)}</span></div>
      <div class="detail-item"><label>好友ID</label><span>${r.friend_id}</span></div>
      <div class="detail-item"><label>好友昵称</label><span>${escapeHtml(r.friend_nick || '-')}</span></div>
      <div class="detail-item"><label>状态</label><span>${escapeHtml(r.status)}</span></div>
      <div class="detail-item"><label>创建时间</label><span>${formatTime(r.created_at)}</span></div>
    </div>
    <label style="font-size:var(--text-sm);color:var(--text-secondary);display:block;margin-bottom:var(--space-2)">检测结果</label>
    <div style="background:var(--bg);border-radius:var(--radius-sm);padding:var(--space-4)">
      <div style="margin-bottom:var(--space-3)">
        <div style="font-size:var(--text-sm);color:var(--text-muted);margin-bottom:var(--space-1)">发送状态</div>
        <div style="font-size:var(--text-title);font-weight:600;color:${result.status === '已发送' ? 'var(--success)' : 'var(--warning)'}">
          ${result.status === '已发送' ? '已发送' : '未发送'}
        </div>
      </div>
      ${result.evidence ? `<div>
        <div style="font-size:var(--text-sm);color:var(--text-muted);margin-bottom:var(--space-1)">证据原文</div>
        <div style="font-size:var(--text-base);background:var(--white);padding:var(--space-3);border-radius:var(--radius-sm);border:1px solid var(--border);line-height:1.6;white-space:pre-wrap">${escapeHtml(result.evidence)}</div>
      </div>` : ''}
    </div>
  `;

  document.getElementById('detail-content').innerHTML = html;
  document.getElementById('detail-modal').classList.add('show');
}
