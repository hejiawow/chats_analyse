/* ============================================
   Cases Page — 优秀话术提取
   ============================================ */

let casesPage = 1;

async function loadCases(reset) {
  if (reset) casesPage = 1;
  const uid = document.getElementById('case-user-id')?.value;
  const scriptType = document.getElementById('case-script-type')?.value;
  const scenario = document.getElementById('case-scenario')?.value;

  let url = `/api/cases?page=${casesPage}&page_size=${PAGE_SIZE.cases}`;
  if (uid) url += `&user_id=${encodeURIComponent(uid)}`;
  if (scriptType) url += `&script_type=${encodeURIComponent(scriptType)}`;
  if (scenario) url += `&scenario_type=${encodeURIComponent(scenario)}`;

  const data = await apiFetch(url);
  const grid = document.getElementById('cases-grid');
  if (data?.data?.length) {
    grid.innerHTML = data.data.map(renderCaseCard).join('');
    document.getElementById('cases-count').textContent = `共 ${data.total} 条`;
    document.getElementById('cases-page').textContent = `第 ${data.page} 页`;
    const prevBtn = document.getElementById('cases-prev-btn');
    const nextBtn = document.getElementById('cases-next-btn');
    if (prevBtn) prevBtn.disabled = data.page <= 1;
    if (nextBtn) nextBtn.disabled = data.page * data.page_size >= data.total;
  } else {
    grid.innerHTML = `<div class="card-grid-empty">暂无记录</div>`;
    document.getElementById('cases-count').textContent = '共 0 条';
    document.getElementById('cases-page').textContent = '第 1 页';
    const prevBtn = document.getElementById('cases-prev-btn');
    const nextBtn = document.getElementById('cases-next-btn');
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;
  }
}

function casesPrev() {
  if (casesPage > 1) { casesPage--; loadCases(false); }
}

function casesNext() {
  casesPage++; loadCases(false);
}

function renderCaseCard(r) {
  if (r.status === 'failed') {
    return `<div class="card-page-card" style="border-left-color:var(--danger)">
      <div class="card-page-card-header">
        <span class="badge danger">提取失败</span>
        <span style="font-size:var(--text-sm);color:var(--text-muted)">${formatTime(r.created_at)}</span>
      </div>
      <p style="font-size:var(--text-sm);color:var(--danger);margin-bottom:var(--space-2)">${escapeHtml(r.error_msg || '未知错误')}</p>
      <div class="card-page-card-footer">
        <span>${r.user_id} · ${r.friend_nick || r.friend_id}</span>
      </div>
    </div>`;
  }
  if (r.status === 'no_cases') {
    return `<div class="card-page-card" style="border-left-color:var(--warning)">
      <div class="card-page-card-header">
        <span class="badge warning">未检测到话术</span>
        <span style="font-size:var(--text-sm);color:var(--text-muted)">${formatTime(r.created_at)}</span>
      </div>
      <p style="font-size:var(--text-sm);color:var(--text-muted);margin-bottom:var(--space-2)">该聊天记录中未发现符合要求的优秀话术</p>
      <div class="card-page-card-footer">
        <span>${r.user_id} · ${r.friend_nick || r.friend_id}</span>
      </div>
    </div>`;
  }

  const scriptType = r.script_type || '销售话术';
  const title = scriptType === '唤醒话术'
    ? (r.trigger_customer_state || '唤醒话术')
    : (r.customer_question || '销售话术');
  const quote = scriptType === '唤醒话术'
    ? (r.wake_script || '')
    : (r.sales_answer || r.sales_quote || '');
  const preview = quote.length > 100 ? quote.substring(0, 100) + '...' : quote;

  const tags = [];
  tags.push(`<span class="card-tag ${scriptType === '唤醒话术' ? 'type-wake' : 'type-sale'}">${escapeHtml(scriptType)}</span>`);
  const sceneTag = r.applicable_scenario || r.scene_tag || '';
  if (sceneTag) tags.push(`<span class="card-tag scene">${escapeHtml(sceneTag.substring(0, 20))}</span>`);
  if (r.business_subject) tags.push(`<span class="card-tag subject">${escapeHtml(r.business_subject)}</span>`);
  if (r.tags) {
    r.tags.split(/[、,]/).filter(t => t.trim()).slice(0, 2).forEach(t =>
      tags.push(`<span class="card-tag" style="background:var(--bg);color:var(--text-secondary)">${escapeHtml(t.trim())}</span>`)
    );
  }

  const profilePreview = r.customer_profile
    ? `<div class="card-profile" title="${escapeHtml(r.customer_profile)}">${escapeHtml(r.customer_profile)}</div>`
    : '';

  return `<div class="card-page-card" style="border-left-color:${scriptType === '唤醒话术' ? 'var(--warning)' : 'var(--success)'}"
    onclick="showCaseDetail(${r.id})">
    <div class="card-page-card-header">
      <div class="card-tags">${tags.join('')}</div>
      <span style="font-size:var(--text-sm);color:var(--text-muted)">${formatTime(r.created_at)}</span>
    </div>
    <div class="card-page-card-title">${escapeHtml(title.substring(0, 60))}</div>
    ${profilePreview}
    <p class="card-preview">${escapeHtml(preview) || '-'}</p>
    <div class="card-page-card-footer">
      <span>${r.user_id} · ${r.friend_nick || r.friend_id}</span>
      <div class="card-actions">
        ${r.compliance_risk && r.compliance_risk !== '无' ? `<span class="card-risk">有风险</span>` : ''}
        <button class="card-action-btn" onclick="event.stopPropagation();addToRag(${r.id})">存入话术库</button>
      </div>
    </div>
  </div>`;
}

async function showCaseDetail(id) {
  const r = await apiFetch(`/api/cases/${id}`);
  if (!r || !r.id) { toast('获取详情失败'); return; }

  if (r.status === 'no_cases') {
    document.getElementById('detail-content').innerHTML = `
      <div class="detail-grid">
        <div class="detail-item"><label>销售ID</label><span>${r.user_id}</span></div>
        <div class="detail-item"><label>好友ID</label><span>${r.friend_id}</span></div>
        <div class="detail-item"><label>好友昵称</label><span>${r.friend_nick || '-'}</span></div>
        <div class="detail-item"><label>状态</label><span>未检测到话术</span></div>
        <div class="detail-item"><label>创建时间</label><span>${formatTime(r.created_at)}</span></div>
      </div>
      <div style="background:var(--warning-bg);border-radius:var(--radius-sm);padding:var(--space-4);margin-top:var(--space-4)">
        <div style="font-size:var(--text-base);color:var(--warning)">该聊天记录中未发现符合要求的优秀话术</div>
      </div>
    `;
    document.getElementById('detail-modal').classList.add('show');
    return;
  }

  const scriptType = r.script_type || '销售话术';
  const isWake = scriptType === '唤醒话术';

  let html = `
    <div class="detail-grid">
      <div class="detail-item"><label>销售ID</label><span>${escapeHtml(r.user_id)}</span></div>
      <div class="detail-item"><label>好友ID</label><span>${r.friend_id}</span></div>
      <div class="detail-item"><label>好友昵称</label><span>${escapeHtml(r.friend_nick || '-')}</span></div>
      <div class="detail-item"><label>话术类型</label><span class="badge ${isWake ? 'warning' : 'info'}">${escapeHtml(scriptType)}</span></div>
      <div class="detail-item"><label>创建时间</label><span>${formatTime(r.created_at)}</span></div>
    </div>
    <div style="margin-top:var(--space-3);display:flex;gap:var(--space-2);justify-content:flex-end">
      <button class="btn btn-primary btn-sm" onclick="addToRag(${r.id})">存入话术库</button>
    </div>
    <div style="margin-top:var(--space-4)">`;

  if (!isWake) {
    html += `<div class="script-detail-section">
      <div class="script-detail-section-title">核心内容</div>
      ${buildScriptField('客户问题', r.customer_question)}
      ${buildScriptField('销冠回答', r.sales_answer, true)}
    </div>`;
  } else {
    html += `<div class="script-detail-section">
      <div class="script-detail-section-title">核心内容</div>
      ${buildScriptField('触发客户状态', r.trigger_customer_state)}
      ${buildScriptField('销冠唤醒话术原文', r.wake_script, true)}
      ${buildScriptField('适用场景', r.applicable_scenario)}
      ${buildScriptField('话术核心目标', r.script_objective)}
    </div>`;
  }

  const metaItems = [];
  if (r.customer_profile) metaItems.push(['客户画像', r.customer_profile]);
  if (r.customer_intent) metaItems.push(['客户意图', r.customer_intent]);
  if (r.applicable_scenario) metaItems.push(['适用场景', r.applicable_scenario]);
  if (r.target_audience) metaItems.push(['适配人群', r.target_audience]);

  if (metaItems.length) {
    html += `<div class="script-detail-section">
      <div class="script-detail-section-title" style="color:#7c3aed;border-color:#7c3aed">客户分析</div>`;
    for (const [label, value] of metaItems) {
      html += buildScriptField(label, value, true);
    }
    html += `</div>`;
  }

  if (r.core_design_logic) {
    html += `<div class="script-detail-section">
      <div class="script-detail-section-title" style="color:var(--success);border-color:var(--success)">话术拆解</div>
      ${buildScriptField('核心设计逻辑', r.core_design_logic, true)}
      ${buildScriptField('话术关键技巧', r.key_techniques)}
    </div>`;
  }

  if (r.pitfall_avoid) {
    html += `<div class="script-detail-section">
      <div class="script-detail-section-title" style="color:var(--warning);border-color:var(--warning)">反例避坑</div>
      <div style="font-size:var(--text-base);line-height:1.6;background:var(--warning-bg);padding:var(--space-4);border-radius:var(--radius-sm);border:1px solid #fef3c7">${escapeHtml(r.pitfall_avoid)}</div>
    </div>`;
  }

  const bottomItems = [];
  if (r.tags) bottomItems.push(`标签：${escapeHtml(r.tags)}`);
  if (r.business_subject) bottomItems.push(`业务科目：${escapeHtml(r.business_subject)}`);
  if (r.compliance_risk && r.compliance_risk !== '无') bottomItems.push(`<span style="color:var(--danger)">合规风险：${escapeHtml(r.compliance_risk)}</span>`);
  if (bottomItems.length) {
    html += `<div style="font-size:var(--text-sm);color:var(--text-muted);line-height:1.8;padding-top:var(--space-3);border-top:1px solid var(--border)">${bottomItems.join('<br>')}</div>`;
  }

  html += `</div>`;

  document.getElementById('detail-content').innerHTML = html;
  document.getElementById('detail-modal').classList.add('show');
}

function buildScriptField(label, value, isWide) {
  if (!value) return '';
  if (isWide) {
    return `<div class="script-detail-field">
      <div class="script-detail-label">${escapeHtml(label)}</div>
      <div class="script-detail-quote">${escapeHtml(value)}</div>
    </div>`;
  }
  return `<div class="script-detail-field">
    <div class="script-detail-label">${escapeHtml(label)}</div>
    <div class="script-detail-value">${escapeHtml(value)}</div>
  </div>`;
}

async function addToRag(caseId) {
  try {
    const res = await fetch(`${API_BASE}/api/cases/${caseId}/add-to-rag`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      toast(`已存入话术库 (ID: ${data.rag_id})`);
    } else if (res.status === 409) {
      toast('该话术已在库中');
    } else {
      toast(data.detail || '存入失败');
    }
  } catch (e) {
    toast('存入失败：' + e.message);
  }
}
