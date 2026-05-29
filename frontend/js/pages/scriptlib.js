/* ============================================
   Script Library Page
   ============================================ */

let slPage = 1;

async function loadScriptLibScenarios() {
  const sel = document.getElementById('sl-scenario');
  if (sel?.dataset.loaded) return;

  const sc = await apiFetch('/api/script-lib/scenarios');
  if (sc?.scenarios) {
    sc.scenarios.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      sel.appendChild(opt);
    });
    sel.dataset.loaded = '1';
  }
}

async function loadScriptLib(reset) {
  if (reset) slPage = 1;
  await loadScriptLibScenarios();

  const scenario = document.getElementById('sl-scenario')?.value;
  const keyword = document.getElementById('sl-keyword')?.value;
  const minscore = document.getElementById('sl-minscore')?.value;

  let url = `/api/script-lib?page=${slPage}&page_size=${PAGE_SIZE.scriptlib}`;
  if (scenario) url += `&scenario_type=${encodeURIComponent(scenario)}`;
  if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
  if (minscore) url += `&min_score=${minscore}`;

  const data = await apiFetch(url);
  const grid = document.getElementById('sl-grid');
  if (data?.data?.length) {
    grid.innerHTML = data.data.map(renderScriptCard).join('');
    document.getElementById('sl-count').textContent = `共 ${data.total} 条`;
    document.getElementById('sl-page').textContent = `第 ${data.page} 页`;
    const prevBtn = document.getElementById('sl-prev-btn');
    const nextBtn = document.getElementById('sl-next-btn');
    if (prevBtn) prevBtn.disabled = data.page <= 1;
    if (nextBtn) nextBtn.disabled = data.page * data.page_size >= data.total;
  } else {
    grid.innerHTML = `<div class="card-grid-empty">暂无话术记录</div>`;
    document.getElementById('sl-count').textContent = '共 0 条';
    document.getElementById('sl-page').textContent = '第 1 页';
    const prevBtn = document.getElementById('sl-prev-btn');
    const nextBtn = document.getElementById('sl-next-btn');
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;
  }
}

function slPrev() {
  if (slPage > 1) { slPage--; loadScriptLib(false); }
}

function slNext() {
  slPage++; loadScriptLib(false);
}

function renderScriptCard(r) {
  const scriptType = r.script_type || '销售话术';
  const isWake = scriptType === '唤醒话术';
  const title = isWake ? (r.trigger_customer_state || '唤醒话术') : (r.customer_question || r.scenario_type || '未分类');
  const quote = isWake ? (r.wake_script || '') : (r.sales_answer || r.sales_quote || '');
  const shortQuote = quote.substring(0, 100);

  return `<div class="script-card" onclick="showScriptDetail(${r.id})">
    <div class="script-card-header">
      <span class="card-tag ${isWake ? 'type-wake' : 'type-sale'}">${escapeHtml(scriptType)}</span>
      ${r.business_subject ? `<span class="card-tag subject">${escapeHtml(r.business_subject)}</span>` : ''}
    </div>
    <div class="script-card-title">${escapeHtml(title.substring(0, 50))}</div>
    <p class="script-card-quote">${escapeHtml(shortQuote) || '无话术内容'}</p>
    <div class="script-card-footer">
      <span>意图: ${isWake ? (r.script_objective || '-') : (r.customer_intent || '-')}</span>
    </div>
  </div>`;
}

async function showScriptDetail(id) {
  const r = await apiFetch(`/api/script-lib/${id}`);
  if (!r || !r.id) { toast('获取详情失败'); return; }

  const scriptType = r.script_type || '销售话术';
  const isWake = scriptType === '唤醒话术';

  let fieldsHtml = '';
  if (isWake) {
    fieldsHtml = buildScriptField('触发客户状态', r.trigger_customer_state)
      + buildScriptField('销冠唤醒话术原文', r.wake_script, true)
      + buildScriptField('适用场景', r.applicable_scenario)
      + buildScriptField('话术核心目标', r.script_objective)
      + buildScriptField('适配人群', r.target_audience);
  } else {
    fieldsHtml = buildScriptField('客户问题', r.customer_question)
      + buildScriptField('销冠回答', r.sales_answer, true)
      + buildScriptField('适用场景', r.applicable_scenario)
      + buildScriptField('客户意图', r.customer_intent);
  }

  const sharedItems = [
    ['核心设计逻辑', r.core_design_logic],
    ['话术关键技巧', r.key_techniques],
    ['反例避坑', r.pitfall_avoid],
  ].filter(([_, v]) => v);

  if (sharedItems.length) {
    fieldsHtml += '<div style="font-size:var(--text-base);font-weight:600;margin:var(--space-4) 0 var(--space-2)">设计分析</div>';
    for (const [label, value] of sharedItems) {
      fieldsHtml += buildScriptField(label, value);
    }
  }

  const metaItems = [];
  if (r.tags) metaItems.push(`标签：${escapeHtml(r.tags)}`);
  if (r.business_subject) metaItems.push(`业务科目：${escapeHtml(r.business_subject)}`);
  if (r.compliance_risk) metaItems.push(`合规风险：${escapeHtml(r.compliance_risk)}`);
  if (metaItems.length) {
    fieldsHtml += `<div style="font-size:var(--text-sm);color:var(--text-muted);line-height:1.8;margin-top:var(--space-3)">${metaItems.join('<br>')}</div>`;
  }

  const html = `
    <div style="margin-bottom:var(--space-3)">
      <span class="badge ${isWake ? 'warning' : 'info'}">${escapeHtml(scriptType)}</span>
      <span style="margin-left:var(--space-2);font-size:var(--text-sm);color:var(--text-muted)">${r.friend_nick || r.friend_id}</span>
    </div>
    <div class="detail-grid">
      <div class="detail-item"><label>销售ID</label><span>${escapeHtml(r.user_id)}</span></div>
      <div class="detail-item"><label>好友ID</label><span>${r.friend_id}</span></div>
      <div class="detail-item"><label>创建时间</label><span>${formatTime(r.created_at)}</span></div>
    </div>
    <div style="margin-top:var(--space-4)">${fieldsHtml}</div>
    <div style="margin-top:var(--space-4);text-align:right">
      <button class="btn btn-outline btn-sm" onclick="showSimilarScripts(${r.id})">找相似话术</button>
    </div>
    <div id="similar-results" style="margin-top:var(--space-3)"></div>
  `;

  document.getElementById('detail-content').innerHTML = html;
  document.getElementById('detail-modal').classList.add('show');
}

async function showSimilarScripts(id) {
  const container = document.getElementById('similar-results');
  container.innerHTML = '<p style="font-size:var(--text-sm);color:var(--text-muted)">正在搜索相似话术...</p>';

  const data = await apiFetch(`/api/script-lib/similar/${id}?top_k=5`);
  if (data?.data?.length) {
    container.innerHTML = `
      <label style="font-size:var(--text-sm);color:var(--text-muted);font-weight:600">相似话术 (TOP ${data.data.length})</label>
      <div style="display:flex;flex-direction:column;gap:var(--space-2);margin-top:var(--space-2)">
        ${data.data.map(s => {
          const st = s.script_type || '销售话术';
          const title = st === '唤醒话术' ? (s.trigger_customer_state || '-') : (s.customer_question || s.scenario_type || '-');
          const quote = st === '唤醒话术' ? (s.wake_script || '') : (s.sales_answer || s.sales_quote || '');
          return `<div class="similar-script-item" onclick="showScriptDetail(${s.id})">
            <div style="flex:1">
              <span class="badge ${st === '唤醒话术' ? 'warning' : 'info'}" style="font-size:var(--text-sm)">${escapeHtml(st)}</span>
              <p style="font-size:var(--text-sm);margin-top:var(--space-1);line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(title.substring(0, 60))}</p>
              <p style="font-size:var(--text-sm);color:var(--text-muted);margin-top:var(--space-1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(quote.substring(0, 60))}</p>
            </div>
            <div class="similar-script-similarity">
              <span style="font-size:var(--text-sm);color:var(--text-muted)">相似度</span>
              <div class="similar-script-percent">${s.similarity || 0}%</div>
            </div>
          </div>`;
        }).join('')}
      </div>
    `;
  } else {
    container.innerHTML = '<p style="font-size:var(--text-sm);color:var(--text-muted)">未找到相似话术</p>';
  }
}
