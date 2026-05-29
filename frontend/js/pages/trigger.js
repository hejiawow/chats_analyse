/* ============================================
   Trigger Page — 触发分析
   ============================================ */

// 获取选中的智能体（多选）
function getSelectedAgents() {
  const checkboxes = document.querySelectorAll('input[name="agent"]:checked');
  const selected = Array.from(checkboxes).map(cb => cb.value);
  return selected.length > 0 ? selected.join(',') : null;
}

// 全选智能体
function selectAllAgents() {
  document.querySelectorAll('input[name="agent"]').forEach(cb => {
    cb.checked = true;
  });
}

// 清除选择
function clearAllAgents() {
  document.querySelectorAll('input[name="agent"]').forEach(cb => {
    cb.checked = false;
  });
}

async function submitTrigger(e) {
  e.preventDefault();
  const msg = document.getElementById('trigger-result-msg');
  const progress = document.getElementById('trigger-progress');
  const progressTitle = document.getElementById('trigger-progress-title');
  const progressDesc = document.getElementById('trigger-progress-desc');
  const btn = document.getElementById('trigger-btn');
  const logsDiv = document.getElementById('trigger-logs');
  const logsBox = document.getElementById('trigger-logs-box');

  const agent = getSelectedAgents();
  const datasource = document.getElementById('datasource')?.value || 'hujing';

  const payload = {
    user_id: document.getElementById('t-user-id')?.value || null,
    user_name: document.getElementById('t-user-name')?.value || null,
    friend_id: document.getElementById('t-friend-id')?.value ? parseInt(document.getElementById('t-friend-id').value) : null,
    friend_phone: document.getElementById('t-friend-phone')?.value || null,
    friend_wx_id: document.getElementById('t-friend-wx')?.value || null,
    friend_alias: document.getElementById('t-friend-alias')?.value || null,
    user_wx_id: null,
    friend_nick: null,
    agent: agent,
    datasource: datasource,
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
  if (!agent) {
    msg.className = 'trigger-result show error';
    msg.textContent = '请选择一个智能体';
    return;
  }

  const saleInfo = payload.user_id || payload.user_name;
  const friendInfo = payload.friend_id || payload.friend_phone || payload.friend_wx_id || payload.friend_alias || '-';

  progress.style.display = 'block';
  progress.className = 'trigger-result show info';
  progressTitle.textContent = '正在分析中...';
  progressDesc.textContent = `销售: ${saleInfo} → 客户: ${friendInfo}`;
  btn.disabled = true;
  msg.className = 'trigger-result';
  msg.style.display = 'none';
  logsDiv.style.display = 'block';
  logsBox.innerHTML = '<div style="color:var(--text-muted)">等待日志...</div>';

  const taskId = genUUID();
  payload.task_id = taskId;
  let currentTaskId = taskId;
  let lastLogCount = 0;

  const endpoint = agent === 'all' ? '/api/trigger' : '/api/trigger/single';

  const triggerPromise = fetch(API_BASE + endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

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
      if (logData.done) {
        clearInterval(logInterval);
        await sleep(300);
        try {
          const res = await triggerPromise;
          if (res.ok) {
            const data = await res.json();
            progress.style.display = 'none';
            msg.className = 'trigger-result show success';
            msg.textContent = data.message;
            toast('分析完成');

            const hist = document.getElementById('trigger-history');
            const now = new Date().toLocaleString('zh-CN');
            hist.innerHTML = `<tr>
              <td><span class="badge success">已完成</span></td>
              <td><code>${escapeHtml(saleInfo)}</code></td>
              <td>${escapeHtml(friendInfo)}</td>
              <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(data.message)}">${escapeHtml(data.message)}</td>
              <td>${now}</td>
              <td><button class="btn btn-outline btn-sm" onclick="switchPage('referral')">查看</button></td>
            </tr>` + hist.innerHTML;

            e.target.reset();
            btn.disabled = false;
            setTimeout(() => {
              loadDashboard();
              setTimeout(() => { logsDiv.style.display = 'none'; }, 10000);
            }, 1000);
          } else {
            const err = await res.json();
            progress.style.display = 'none';
            btn.disabled = false;
            msg.className = 'trigger-result show error';
            msg.textContent = `分析失败: ${err.detail || '未知错误'}`;
          }
        } catch (err) {
          progress.style.display = 'none';
          btn.disabled = false;
          msg.className = 'trigger-result show error';
          msg.textContent = `获取结果失败: ${err.message}`;
        }
      }
    }
  }, 1000);

  try {
    const res = await triggerPromise;
    if (!res.ok) {
      const err = await res.json();
      clearInterval(logInterval);
      progress.style.display = 'none';
      logsDiv.style.display = 'none';
      btn.disabled = false;

      if (err.detail && err.detail.includes('未找到') && err.detail.includes('好友')) {
        showNoMatchModal(payload, err.detail);
        return;
      }

      msg.className = 'trigger-result show error';
      msg.textContent = `${err.detail || JSON.stringify(err)}`;
    }
  } catch (err) {
    clearInterval(logInterval);
    progress.style.display = 'none';
    logsDiv.style.display = 'none';
    btn.disabled = false;
    msg.className = 'trigger-result show error';
    msg.textContent = `网络错误: ${err.message}（请确认后端服务已启动）`;
  }
}

async function triggerWithIds(payload) {
  const progress = document.getElementById('trigger-progress');
  const progressTitle = document.getElementById('trigger-progress-title');
  const progressDesc = document.getElementById('trigger-progress-desc');
  const msg = document.getElementById('trigger-result-msg');
  const btn = document.getElementById('trigger-btn');
  const logsDiv = document.getElementById('trigger-logs');
  const logsBox = document.getElementById('trigger-logs-box');

  const saleInfo = payload.user_id || payload.user_name;
  const friendInfo = payload.friend_id || payload.friend_phone || payload.friend_wx_id || payload.friend_alias || '-';

  progress.style.display = 'block';
  progress.className = 'trigger-result show info';
  progressTitle.textContent = '正在分析中...';
  progressDesc.textContent = `销售: ${saleInfo} → 客户: ${friendInfo}`;
  btn.disabled = true;
  msg.style.display = 'none';
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
    const res = await fetch(API_BASE + '/api/trigger', {
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
      msg.textContent = `${data.message}`;
      toast('分析完成');
      btn.disabled = false;
      setTimeout(() => { loadDashboard(); setTimeout(() => { logsDiv.style.display = 'none'; }, 10000); }, 1000);
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
