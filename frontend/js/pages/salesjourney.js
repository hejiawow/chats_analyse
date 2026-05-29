/* ============================================
   Sales Journey Page (独立页面 — 成交案例提取)
   ============================================ */

let salesJourneyPage = 1;

async function loadSalesJourney(reset) {
  if (reset) salesJourneyPage = 1;
  const uid = document.getElementById('sj-user-id')?.value;

  let url = `/api/sales-journeys?page=${salesJourneyPage}&page_size=${PAGE_SIZE.salesjourney}`;
  if (uid) url += `&user_id=${encodeURIComponent(uid)}`;

  const data = await apiFetch(url);
  const tbody = document.getElementById('salesjourney-table');
  if (data?.data?.length) {
    tbody.innerHTML = data.data.map(r => {
      const statusBadge = r.status === 'no_chat' ? '<span class="badge warning">无聊天记录</span>' :
                         r.status === 'no_cases' ? '<span class="badge info">无优秀案例</span>' :
                         '<span class="badge success">已分析</span>';
      return `<tr>
        <td>${statusBadge}</td>
        <td><code>${r.user_id}</code></td>
        <td>${r.friend_nick || r.friend_id}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(r.status)}">${escapeHtml(r.status)}</td>
        <td>${formatTime(r.created_at)}</td>
        <td><button class="btn btn-outline btn-sm" onclick="showSuccessDetail(${r.id})">查看</button></td>
      </tr>`;
    }).join('');
    renderPagination('salesjourney', data);
  } else {
    tbody.innerHTML = renderEmptyRow(6);
    renderPagination('salesjourney', { total: 0, page: 1 });
  }
}

async function submitSalesJourney(e) {
  e.preventDefault();
  const btn = document.getElementById('sj-trigger-btn');
  const progress = document.getElementById('sj-progress');
  const logsDiv = document.getElementById('sj-logs');
  const logsBox = document.getElementById('sj-logs-box');
  const msg = document.getElementById('sj-result-msg');
  const resultDisplay = document.getElementById('sj-result-display');

  const payload = {
    user_id: document.getElementById('sj-user-id')?.value || null,
    user_name: document.getElementById('sj-user-name')?.value || null,
    friend_id: document.getElementById('sj-friend-id')?.value ? parseInt(document.getElementById('sj-friend-id').value) : null,
    friend_phone: document.getElementById('sj-friend-phone')?.value || null,
    friend_wx_id: document.getElementById('sj-friend-wx')?.value || null,
    friend_alias: document.getElementById('sj-friend-alias')?.value || null,
    user_wx_id: null,
    friend_nick: null,
  };

  if (!payload.user_id && !payload.user_name) {
    msg.className = 'trigger-result show error';
    msg.textContent = '请填写销售 ID 或销售姓名（至少一个）';
    return;
  }
  if (!payload.friend_id && !payload.friend_phone && !payload.friend_wx_id && !payload.friend_alias) {
    msg.className = 'trigger-result show error';
    msg.textContent = '请填写好友 ID / 客户手机号 / 客户微信号 / 客户别名（至少一个）';
    return;
  }

  const saleInfo = payload.user_id || payload.user_name;
  const friendInfo = payload.friend_id || payload.friend_phone || payload.friend_wx_id || payload.friend_alias || '-';

  progress.style.display = 'block';
  progress.className = 'trigger-result show info';
  document.getElementById('sj-progress-title').textContent = '正在分析中...';
  document.getElementById('sj-progress-desc').textContent = `销售: ${saleInfo} → 客户: ${friendInfo}`;
  btn.disabled = true;
  msg.style.display = 'none';
  resultDisplay.style.display = 'none';
  logsDiv.style.display = 'block';
  logsBox.innerHTML = '<div style="color:var(--text-muted)">等待日志...</div>';

  const taskId = genUUID();
  payload.task_id = taskId;
  let currentTaskId = taskId;
  let lastLogCount = 0;

  const logInterval = setInterval(async () => {
    const logsRes = await fetch(API_BASE + '/api/logs/' + currentTaskId);
    if (logsRes.ok) {
      const logData = await logsRes.json();
      if (logData.logs && logData.logs.length > lastLogCount) {
        const newLogs = logData.logs.slice(lastLogCount);
        for (const log of newLogs) {
          const color = log.level === 'error' ? 'var(--danger)' :
                        log.level === 'success' ? 'var(--success)' :
                        log.level === 'warning' ? 'var(--warning)' : 'var(--text-muted)';
          logsBox.innerHTML += `<div><span style="color:var(--text-secondary)">[${log.time}]</span> <span style="color:${color}">${escapeHtml(log.message)}</span></div>`;
        }
        lastLogCount = logData.logs.length;
        logsBox.scrollTop = logsBox.scrollHeight;
      }
    }
  }, 1000);

  try {
    const res = await fetch(API_BASE + '/api/trigger/sales-journey', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      currentTaskId = data.task_id || taskId;
      await sleep(500);
      clearInterval(logInterval);
      progress.style.display = 'none';
      msg.className = 'trigger-result show success';
      msg.textContent = `${data.message || '分析完成'}`;
      toast('分析完成');
      btn.disabled = false;
      if (data.result) {
        renderSalesJourneyResult(data.result);
      }
      setTimeout(() => { logsDiv.style.display = 'none'; }, 10000);
    } else {
      const err = await res.json();
      clearInterval(logInterval);
      progress.style.display = 'none';
      btn.disabled = false;
      msg.className = 'trigger-result show error';
      msg.textContent = `${err.detail || JSON.stringify(err)}`;
    }
  } catch (err) {
    clearInterval(logInterval);
    progress.style.display = 'none';
    logsDiv.style.display = 'none';
    btn.disabled = false;
    msg.className = 'trigger-result show error';
    msg.textContent = `网络错误: ${err.message}`;
  }
}

function renderSalesJourneyResult(result) {
  const display = document.getElementById('sj-result-display');
  display.style.display = 'block';

  const m1 = result.module1_basic || {};
  const profile = m1.user_profile || {};
  const m2 = result.module2_journey || [];
  const m3 = result.module3_scripts || [];
  const m4 = result.module4_psychology || [];
  const m5 = result.module5_key_factors || {};
  const m6 = result.module6_improvements || {};

  // Module 1
  const module1El = document.getElementById('sj-module1');
  if (module1El) {
    module1El.innerHTML = `<div class="detail-grid">
      <div class="detail-item"><label>成交时间</label><span>${escapeHtml(m1.deal_time || '-')}</span></div>
      <div class="detail-item"><label>聊天总时长</label><span>${escapeHtml(m1.chat_duration || '-')}</span></div>
      <div class="detail-item"><label>消息数</label><span>${m1.message_count || '-'}</span></div>
      <div class="detail-item"><label>销售风格</label><span>${escapeHtml(m1.sales_style || '-')}</span></div>
      <div class="detail-item"><label>身份背景</label><span>${escapeHtml(profile.identity || '-')}</span></div>
      <div class="detail-item"><label>核心顾虑</label><span>${escapeHtml(profile.concerns || '-')}</span></div>
      <div class="detail-item"><label>真实需求</label><span>${escapeHtml(profile.needs || '-')}</span></div>
      <div class="detail-item"><label>关键痛点</label><span>${escapeHtml(profile.pain_points || '-')}</span></div>
    </div>`;
  }

  // Module 2 - Journey
  const module2El = document.getElementById('sj-module2');
  if (module2El) {
    if (m2.length) {
      module2El.innerHTML = `<div style="position:relative;padding-left:32px">
        <div style="position:absolute;left:15px;top:8px;bottom:8px;width:2px;background:var(--border-strong);border-radius:1px"></div>
        ${m2.map((s, idx) => {
          const effColor = s.effectiveness >= 4 ? 'var(--success)' : s.effectiveness >= 3 ? 'var(--warning)' : 'var(--danger)';
          const colors = ['var(--primary)', '#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#f43f5e', 'var(--danger)'];
          const dotColor = colors[idx % colors.length];
          return `<div style="position:relative;margin-bottom:var(--space-5)">
            <div style="position:absolute;left:-32px;top:4px;width:12px;height:12px;border-radius:50%;background:${dotColor};border:3px #fff;box-shadow:0 0 0 2px ${dotColor}"></div>
            <div style="background:var(--bg);border-radius:var(--radius-md);padding:var(--space-4);border:1px solid var(--border)">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-2)">
                <span style="font-weight:700;font-size:var(--text-base);color:${dotColor}">${escapeHtml(s.stage || '-')}</span>
                <span style="font-size:var(--text-sm);color:var(--text-muted);background:var(--bg);padding:2px 8px;border-radius:var(--radius-sm)">${escapeHtml(s.time_range || '')}</span>
              </div>
              <div style="font-size:var(--text-sm);line-height:1.6">
                <div style="margin-bottom:var(--space-1)"><strong style="color:var(--text-secondary)">销售动作：</strong><span style="color:var(--text)">${escapeHtml(s.sales_action || '-')}</span></div>
                <div><strong style="color:var(--text-secondary)">用户反应：</strong><span style="color:var(--text)">${escapeHtml(s.user_reaction || '-')}</span></div>
              </div>
              <div style="margin-top:var(--space-3);display:flex;align-items:center;gap:var(--space-2)">
                <span style="font-size:var(--text-sm);color:var(--text-muted)">效果评分</span>
                <div style="display:flex;gap:2px">
                  ${Array.from({ length: 5 }, (_, i) => `<div style="width:16px;height:6px;border-radius:3px;background:${i < (s.effectiveness || 0) ? effColor : 'var(--border)'}"></div>`).join('')}
                </div>
                <span style="font-size:var(--text-sm);color:${effColor};font-weight:600">${s.effectiveness || 0}/5</span>
              </div>
            </div>
          </div>`;
        }).join('')}
      </div>`;
    } else {
      module2El.innerHTML = '<p style="color:var(--text-muted)">无数据</p>';
    }
  }

  // Module 3 - Scripts
  const module3El = document.getElementById('sj-module3');
  if (module3El) {
    if (m3.length) {
      module3El.innerHTML = `<div style="display:flex;flex-direction:column;gap:var(--space-4)">${m3.map(s => {
        const sceneTag = s.scene_tag || '';
        const businessSubject = s.business_subject || '';
        const customerQuestion = s.customer_question || '';
        const salesAnswer = s.sales_answer || s.quote || '';
        const customerIntent = s.customer_intent || '';
        const customerProfile = s.customer_profile || '';
        const tags = s.tags || '';
        const complianceRisk = s.compliance_risk || '';
        const whyGood = s.why_good || '';
        const antiPitfall = s.anti_pitfall || s.reusable_tip || '';

        const tagsHtml = tags ? tags.split(',').filter(t => t.trim()).map(t =>
          `<span style="display:inline-block;background:var(--primary-bg);color:var(--primary-hover);font-size:var(--text-sm);padding:1px 6px;border-radius:3px;margin-right:var(--space-1)">${escapeHtml(t.trim())}</span>`
        ).join('') : '';

        return `<div style="background:var(--danger-bg);border:1px solid #fecaca;border-radius:var(--radius-md);padding:var(--space-4)">
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
      }).join('')}</div>`;
    } else {
      module3El.innerHTML = '<p style="color:var(--text-muted)">无数据</p>';
    }
  }

  // Module 4 - Psychology
  const module4El = document.getElementById('sj-module4');
  if (module4El) {
    if (m4.length) {
      module4El.innerHTML = `<div style="display:flex;flex-direction:column;gap:var(--space-3)">
        ${m4.map(s => `<div style="background:var(--bg);border-radius:var(--radius-sm);padding:var(--space-3);border-left:4px solid #7c3aed">
          <span class="badge" style="background:#f3e8ff;color:#7c3aed">${escapeHtml(s.mental_state || '')}</span>
          <div style="margin-top:var(--space-2);font-size:var(--text-sm);line-height:1.6">
            <div><strong>触发因素：</strong>${escapeHtml(s.trigger || '-')}</div>
            <div style="margin-top:var(--space-1)"><strong>用户原话：</strong>${escapeHtml(s.user_quote || '-')}</div>
          </div>
        </div>`).join('')}
      </div>`;
    } else {
      module4El.innerHTML = '<p style="color:var(--text-muted)">无数据</p>';
    }
  }

  // Module 5 - Key Factors
  const module5El = document.getElementById('sj-module5');
  if (module5El) {
    module5El.innerHTML = `<div style="display:flex;flex-direction:column;gap:var(--space-3)">
      <div style="background:var(--success-bg);border:1px solid #bbf7d0;border-radius:var(--radius-sm);padding:var(--space-4)">
        <div style="font-size:var(--text-sm);color:var(--success);font-weight:600;margin-bottom:var(--space-1)">关键一句话</div>
        <div style="font-size:var(--text-base);line-height:1.6">${escapeHtml(m5.key_sentence || '-')}</div>
      </div>
      <div style="background:var(--bg);border-radius:var(--radius-sm);padding:var(--space-4)">
        <div style="font-size:var(--text-sm);color:var(--text-muted);font-weight:600;margin-bottom:var(--space-1)">成交关键节点</div>
        <div style="font-size:var(--text-base)">${escapeHtml(m5.deal_node || '-')}</div>
      </div>
      <div style="background:var(--bg);border-radius:var(--radius-sm);padding:var(--space-4)">
        <div style="font-size:var(--text-sm);color:var(--text-muted);font-weight:600;margin-bottom:var(--space-2)">销售做得最好的3个点</div>
        <ol style="margin:0;padding-left:var(--space-5);font-size:var(--text-base);line-height:2">
          ${(m5.top3_strengths || []).map(t => `<li>${escapeHtml(t)}</li>`).join('')}
        </ol>
      </div>
    </div>`;
  }

  // Module 6 - Improvements
  const module6El = document.getElementById('sj-module6');
  if (module6El) {
    let html = '<div style="display:flex;flex-direction:column;gap:var(--space-3)">';
    if ((m6.flaws || []).length) {
      html += `<div style="background:var(--danger-bg);border:1px solid #fecaca;border-radius:var(--radius-sm);padding:var(--space-4)">
        <div style="font-size:var(--text-sm);color:var(--danger);font-weight:600;margin-bottom:var(--space-2)">聊天中的瑕疵</div>
        <ul style="margin:0;padding-left:var(--space-5);font-size:var(--text-base);line-height:2">
          ${m6.flaws.map(f => `<li>${escapeHtml(f)}</li>`).join('')}
        </ul>
      </div>`;
    }
    if ((m6.optimization_suggestions || []).length) {
      html += `<div>
        <div style="font-size:var(--text-sm);color:var(--text-muted);font-weight:600;margin-bottom:var(--space-2)">改进建议</div>
        <div style="display:flex;flex-direction:column;gap:var(--space-2)">
          ${m6.optimization_suggestions.map(s => `<div style="background:var(--bg);border-radius:var(--radius-sm);padding:var(--space-3)">
            <div style="font-size:var(--text-sm);color:var(--text-muted);margin-bottom:var(--space-1)">原句：${escapeHtml(s.original || '')}</div>
            <div style="font-size:var(--text-sm);color:var(--success)">更优：${escapeHtml(s.better || '')}</div>
          </div>`).join('')}
        </div>
      </div>`;
    }
    if (m6.time_compression) {
      html += `<div style="background:var(--warning-bg);border:1px solid #fde68a;border-radius:var(--radius-sm);padding:var(--space-4)">
        <div style="font-size:var(--text-sm);color:var(--warning);font-weight:600;margin-bottom:var(--space-1)">压缩成交时长建议</div>
        <div style="font-size:var(--text-base);line-height:1.6">${escapeHtml(m6.time_compression)}</div>
      </div>`;
    }
    html += '</div>';
    module6El.innerHTML = html;
  }

  display.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
