/* ============================================
   Success Cases Page — 成功案例分析
   ============================================ */

let successPage = 1;

async function loadSuccess(reset) {
  if (reset) successPage = 1;
  const uid = document.getElementById('success-user-id')?.value;

  let url = `/api/sales-journeys?page=${successPage}&page_size=${PAGE_SIZE.success}`;
  if (uid) url += `&user_id=${encodeURIComponent(uid)}`;

  const data = await apiFetch(url);
  const grid = document.getElementById('success-grid');
  if (data?.data?.length) {
    grid.innerHTML = data.data.map(renderSuccessCard).join('');
    document.getElementById('success-count').textContent = `共 ${data.total} 条`;
    document.getElementById('success-page-num').textContent = `第 ${data.page} 页`;
    const prevBtn = document.getElementById('success-prev-btn');
    const nextBtn = document.getElementById('success-next-btn');
    if (prevBtn) prevBtn.disabled = data.page <= 1;
    if (nextBtn) nextBtn.disabled = data.page * data.page_size >= data.total;
  } else {
    grid.innerHTML = `<div class="card-grid-empty">暂无记录</div>`;
    document.getElementById('success-count').textContent = '共 0 条';
    document.getElementById('success-page-num').textContent = '第 1 页';
    const prevBtn = document.getElementById('success-prev-btn');
    const nextBtn = document.getElementById('success-next-btn');
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;
  }
}

function successPrev() {
  if (successPage > 1) { successPage--; loadSuccess(false); }
}

function successNext() {
  successPage++; loadSuccess(false);
}

function renderSuccessCard(r) {
  if (r.status === 'no_chat') {
    return `<div class="card-page-card" style="border-left-color:var(--warning)">
      <div class="card-page-card-header">
        <span class="badge warning">无聊天记录</span>
        <span style="font-size:var(--text-sm);color:var(--text-muted)">${formatTime(r.created_at)}</span>
      </div>
      <p style="font-size:var(--text-sm);color:var(--text-muted)">该好友无聊天记录</p>
      <div class="card-page-card-footer">
        <span>${r.user_id} · ${r.friend_nick || r.friend_id}</span>
      </div>
    </div>`;
  }

  const basic = r.analysis_result?.module1_basic || {};
  const m5 = r.analysis_result?.module5_key_factors || {};
  const journey = r.analysis_result?.module2_journey || [];
  const scripts = r.analysis_result?.module3_scripts || [];

  return `<div class="card-page-card success">
    <div class="card-page-card-header">
      <span class="badge success">${basic.deal_time ? '已成交' : '已分析'}</span>
      <span style="font-size:var(--text-sm);color:var(--text-muted)">${formatTime(r.created_at)}</span>
    </div>
    <div class="card-meta">
      <span>成交时间: ${escapeHtml(basic.deal_time || '-')}</span>
      <span>时长: ${escapeHtml(basic.chat_duration || '-')}</span>
      <span>轮次: ${basic.message_count || '-'}</span>
    </div>
    <div style="font-size:var(--text-sm);color:var(--text);margin-bottom:var(--space-2)">
      <strong>销售风格：</strong>${escapeHtml(basic.sales_style || '-')}
    </div>
    <div style="font-size:var(--text-sm);color:var(--text);margin-bottom:var(--space-3)">
      <strong>关键一句话：</strong>${m5.key_sentence ? (m5.key_sentence.length > 80 ? escapeHtml(m5.key_sentence.substring(0, 80)) + '...' : escapeHtml(m5.key_sentence)) : '-'}
    </div>
    <div class="card-page-card-footer">
      <span>${r.user_id} · ${journey.length}阶段 · ${scripts.length}话术</span>
      <div class="card-actions">
        <button class="card-action-btn" onclick="event.stopPropagation();showSuccessDetail(${r.id})">详情</button>
        <button class="card-action-btn primary" onclick="event.stopPropagation();downloadCaseReport(${r.id})">下载</button>
      </div>
    </div>
  </div>`;
}

function downloadCaseReport(id) {
  downloadFile(`${API_BASE}/api/sales-journeys/${id}/download`);
  toast('正在下载报告...');
}

async function showSuccessDetail(id) {
  const r = await apiFetch(`/api/sales-journeys/${id}`);
  if (!r || !r.id) { toast('获取详情失败'); return; }

  const result = r.analysis_result;
  if (!result) {
    toast('该记录无分析结果');
    return;
  }

  const basic = result.module1_basic || {};
  const profile = basic.user_profile || {};
  const journey = result.module2_journey || [];
  const scripts = result.module3_scripts || [];
  const psychology = result.module4_psychology || [];
  const keyFactors = result.module5_key_factors || {};
  const improvements = result.module6_improvements || {};

  let html = '';

  // Basic info
  html += `<div class="detail-grid">
    <div class="detail-item"><label>成交时间</label><span>${escapeHtml(basic.deal_time || '-')}</span></div>
    <div class="detail-item"><label>聊天总时长</label><span>${escapeHtml(basic.chat_duration || '-')}</span></div>
    <div class="detail-item"><label>消息数</label><span>${basic.message_count || '-'}</span></div>
    <div class="detail-item"><label>销售风格</label><span>${escapeHtml(basic.sales_style || '-')}</span></div>
    <div class="detail-item"><label>身份背景</label><span>${escapeHtml(profile.identity || '-')}</span></div>
    <div class="detail-item"><label>核心顾虑</label><span>${escapeHtml(profile.concerns || '-')}</span></div>
    <div class="detail-item"><label>真实需求</label><span>${escapeHtml(profile.needs || '-')}</span></div>
    <div class="detail-item"><label>关键痛点</label><span>${escapeHtml(profile.pain_points || '-')}</span></div>
  </div>`;

  // Journey
  if (journey.length) {
    html += `<div style="margin-top:var(--space-5)"><div style="font-size:var(--text-base);font-weight:600;margin-bottom:var(--space-3)">成交全流程拆解</div>`;
    html += `<div style="position:relative;padding-left:32px">`;
    html += `<div style="position:absolute;left:15px;top:8px;bottom:8px;width:2px;background:var(--border-strong);border-radius:1px"></div>`;
    html += journey.map((s, idx) => {
      const eff = s.effectiveness || 0;
      const cl = eff >= 4 ? 'var(--success)' : eff >= 3 ? 'var(--warning)' : 'var(--danger)';
      const colors = ['var(--primary)', '#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#f43f5e', 'var(--danger)'];
      const dotColor = colors[idx % colors.length];
      return `<div style="position:relative;margin-bottom:var(--space-4)">
        <div style="position:absolute;left:-32px;top:4px;width:12px;height:12px;border-radius:50%;background:${dotColor};border:3px #fff;box-shadow:0 0 0 2px ${dotColor}"></div>
        <div style="background:var(--bg);border-radius:var(--radius-md);padding:var(--space-3);border:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;margin-bottom:var(--space-2)">
            <strong style="color:${dotColor};font-size:var(--text-base)">${escapeHtml(s.stage || '')}</strong>
            <span style="font-size:var(--text-sm);color:var(--text-muted);background:var(--bg);padding:2px 8px;border-radius:var(--radius-sm)">${escapeHtml(s.time_range || '')}</span>
          </div>
          <div style="font-size:var(--text-sm);line-height:1.6">
            <div><strong style="color:var(--text-secondary)">销售动作：</strong><span style="color:var(--text)">${escapeHtml(s.sales_action || '')}</span></div>
            <div><strong style="color:var(--text-secondary)">用户反应：</strong><span style="color:var(--text)">${escapeHtml(s.user_reaction || '')}</span></div>
          </div>
          <div style="margin-top:var(--space-2);display:flex;align-items:center;gap:var(--space-2)">
            <span style="font-size:var(--text-sm);color:var(--text-muted)">效果评分</span>
            <div style="display:flex;gap:2px">
              ${Array.from({ length: 5 }, (_, i) => `<div style="width:16px;height:6px;border-radius:3px;background:${i < eff ? cl : 'var(--border)'}"></div>`).join('')}
            </div>
            <span style="font-size:var(--text-sm);color:${cl};font-weight:600">${eff}/5</span>
          </div>
        </div>
      </div>`;
    }).join('');
    html += `</div></div>`;
  }

  // Scripts
  if (scripts.length) {
    html += `<div style="margin-top:var(--space-5)"><div style="font-size:var(--text-base);font-weight:600;margin-bottom:var(--space-3)">优秀话术萃取</div>`;
    html += scripts.map(s => {
      const customerQuestion = s.customer_question || '';
      const salesAnswer = s.sales_answer || s.quote || '';
      const sceneTag = s.scene_tag || '';
      const customerIntent = s.customer_intent || '';
      const tags = s.tags || '';
      const businessSubject = s.business_subject || '';
      const complianceRisk = s.compliance_risk || '';
      const whyGood = s.why_good || '';
      const customerProfile = s.customer_profile || '';
      const antiPitfall = s.anti_pitfall || s.reusable_tip || '';

      const tagsHtml = tags ? tags.split(',').filter(t => t.trim()).map(t =>
        `<span style="display:inline-block;background:var(--primary-bg);color:var(--primary-hover);font-size:var(--text-sm);padding:1px 6px;border-radius:3px;margin-right:var(--space-1)">${escapeHtml(t.trim())}</span>`
      ).join('') : '';

      return `<div style="background:var(--danger-bg);border:1px solid #fecaca;border-radius:var(--radius-md);padding:var(--space-3);margin-bottom:var(--space-3)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-2)">
          <span class="badge" style="background:var(--danger);color:#fff">${escapeHtml(sceneTag)}</span>
          ${businessSubject ? `<span style="font-size:var(--text-sm);color:var(--text-muted);background:var(--bg);padding:2px 8px;border-radius:var(--radius-sm)">${escapeHtml(businessSubject)}</span>` : ''}
        </div>
        <div style="margin-bottom:var(--space-2)">
          ${customerQuestion ? `<div style="font-size:var(--text-sm);color:var(--text-secondary);padding:var(--space-2) var(--space-3);background:var(--bg);border-radius:var(--radius-sm);margin-bottom:var(--space-1);line-height:1.6"><b>客户：</b>${escapeHtml(customerQuestion)}</div>` : ''}
          <div style="font-size:var(--text-base);color:var(--danger);font-weight:700;padding:var(--space-3);background:var(--white);border-radius:var(--radius-sm);border-left:3px solid var(--danger);line-height:1.6"><b>销冠：</b>${escapeHtml(salesAnswer)}</div>
        </div>
        <div style="margin-bottom:var(--space-2);padding:var(--space-3);background:rgba(255,255,255,0.7);border-radius:var(--radius-sm);font-size:var(--text-sm);line-height:1.6">
          ${customerIntent ? `<div style="margin:var(--space-1) 0"><b>客户意图：</b>${escapeHtml(customerIntent)}</div>` : ''}
          ${customerProfile ? `<div style="margin:var(--space-1) 0"><b>客户画像：</b>${escapeHtml(customerProfile)}</div>` : ''}
          ${tagsHtml ? `<div style="margin:var(--space-1) 0"><b>标签：</b>${tagsHtml}</div>` : ''}
          ${complianceRisk ? `<div style="margin:var(--space-1) 0"><b>合规风险：</b><span style="color:var(--danger);font-weight:600">${escapeHtml(complianceRisk)}</span></div>` : ''}
        </div>
        <div style="font-size:var(--text-sm);line-height:1.6">
          ${whyGood ? `<div style="margin:var(--space-1) 0"><b>话术拆解分析：</b>${escapeHtml(whyGood)}</div>` : ''}
          ${antiPitfall ? `<div style="margin:var(--space-1) 0"><b>反例避坑：</b><span style="color:var(--warning);font-weight:600">${escapeHtml(antiPitfall)}</span></div>` : ''}
        </div>
      </div>`;
    }).join('');
    html += `</div>`;
  }

  // Psychology
  if (psychology.length) {
    html += `<div style="margin-top:var(--space-5)"><div style="font-size:var(--text-base);font-weight:600;margin-bottom:var(--space-3)">用户心理变化</div>`;
    html += psychology.map(p => `<div style="display:inline-flex;align-items:center;gap:var(--space-2);padding:var(--space-2) var(--space-3);background:var(--bg);border-radius:var(--radius-full);margin:var(--space-1);font-size:var(--text-sm)">
      <strong>${escapeHtml(p.mental_state || '')}</strong>
      <span style="color:var(--text-muted)">→</span>
      <span style="font-size:var(--text-sm);color:var(--text-secondary)">${escapeHtml(p.trigger || '')}</span>
    </div>`).join('');
    html += `</div>`;
  }

  // Key factors
  html += `<div style="margin-top:var(--space-5)"><div style="font-size:var(--text-base);font-weight:600;margin-bottom:var(--space-3)">成交关键原因</div>`;
  html += `<div style="background:var(--success-bg);border:1px solid #bbf7d0;border-radius:var(--radius-sm);padding:var(--space-3);margin-bottom:var(--space-2)">
    <div style="font-size:var(--text-sm);color:var(--success)">关键一句话</div>
    <div style="font-size:var(--text-base);font-weight:600;margin-top:var(--space-1)">${escapeHtml(keyFactors.key_sentence || '-')}</div>
  </div>`;
  html += `<div style="font-size:var(--text-sm)">成交节点: ${escapeHtml(keyFactors.deal_node || '-')}</div>`;
  if (keyFactors.top3_strengths) {
    html += `<ol style="margin-top:var(--space-2);padding-left:var(--space-5)">${keyFactors.top3_strengths.map(t => `<li style="margin:var(--space-1) 0">${escapeHtml(t)}</li>`).join('')}</ol>`;
  }
  html += `</div>`;

  // Improvements
  if (improvements.flaws || improvements.optimization_suggestions) {
    html += `<div style="margin-top:var(--space-5)"><div style="font-size:var(--text-base);font-weight:600;margin-bottom:var(--space-3)">改进建议</div>`;
    if (improvements.flaws) {
      html += `<div style="color:var(--danger);font-size:var(--text-sm)">瑕疵: ${(improvements.flaws || []).map(escapeHtml).join('；')}</div>`;
    }
    if (improvements.optimization_suggestions) {
      improvements.optimization_suggestions.forEach(s => {
        html += `<div style="font-size:var(--text-sm);margin-top:var(--space-1)"><b>原句：</b>${escapeHtml(s.original || '')}<br><b style="color:var(--success)">更优：</b>${escapeHtml(s.better || '')}</div>`;
      });
    }
    html += `</div>`;
  }

  const modal = createModal({
    title: `成交案例复盘 — ${r.friend_nick || r.friend_id}`,
    width: '900px',
    content: html,
    footer: `<button class="btn btn-primary" onclick="downloadCaseReport(${r.id})">下载报告</button>`,
  });
}
