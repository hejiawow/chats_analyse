/* ============================================
   Modal Component — 弹窗系统
   ============================================ */

function createModal(options = {}) {
  const {
    title = '详情',
    content = '',
    width = '520px',
    onClose = null,
    footer = null,
  } = options;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay show';
  overlay.onclick = (e) => {
    if (e.target === overlay) {
      overlay.classList.remove('show');
      setTimeout(() => overlay.remove(), 200);
      if (onClose) onClose();
    }
  };

  const footerHtml = footer ? `<div style="padding:var(--space-4) var(--space-6);border-top:1px solid var(--border);display:flex;justify-content:flex-end;gap:var(--space-2)">${footer}</div>` : '';

  overlay.innerHTML = `
    <div class="modal-content" style="max-width:${width}" onclick="event.stopPropagation()">
      <div class="modal-header">
        <h3>${escapeHtml(title)}</h3>
        <button class="modal-close" onclick="this.closest('.modal-overlay').classList.remove('show'); setTimeout(() => this.closest('.modal-overlay').remove(), 200); ${onClose ? 'void(0)' : ''}">&times;</button>
      </div>
      <div class="modal-body">${content}</div>
      ${footerHtml}
    </div>
  `;

  document.body.appendChild(overlay);

  return {
    close: () => {
      overlay.classList.remove('show');
      setTimeout(() => overlay.remove(), 200);
      if (onClose) onClose();
    },
    updateContent: (html) => {
      const body = overlay.querySelector('.modal-body');
      if (body) body.innerHTML = html;
    },
    element: overlay,
  };
}

// Show no-match modal
function showNoMatchModal(payload, detail) {
  createModal({
    title: '未找到匹配的好友',
    width: '480px',
    content: `
      <p style="font-size:var(--text-base);color:var(--text);margin-bottom:var(--space-4);line-height:1.6">${detail}</p>
      <div style="background:var(--bg);border-radius:var(--radius-sm);padding:var(--space-3) var(--space-4);font-size:var(--text-sm);color:var(--text-secondary)">
        <p style="font-weight:600;margin-bottom:var(--space-2);color:var(--text)">请检查以下信息：</p>
        <ul style="margin:0;padding-left:var(--space-4);line-height:2">
          <li>销售姓名是否拼写正确</li>
          <li>客户手机号是否为绑定手机号或备注手机号</li>
          <li>该客户是否已被该销售删除好友</li>
        </ul>
      </div>
    `,
    footer: `<button class="btn btn-outline" onclick="this.closest('.modal-overlay').classList.remove('show'); setTimeout(() => this.closest('.modal-overlay').remove(), 200)">关闭</button>`,
  });
}

// Show duplicate selection modal
function showDuplicateModal(options, payload) {
  const optionsHtml = options.map((o, i) => `
    <button class="dup-option" onclick="selectDuplicate(${i})">
      <span style="font-weight:500;font-size:var(--text-base);color:var(--text)">${escapeHtml(o.username)}</span>
      <span style="display:flex;gap:var(--space-4);font-size:var(--text-sm);color:var(--text-secondary)">
        <span>销售ID: ${escapeHtml(o.user_id)}</span>
        <span>好友: ${escapeHtml(o.friend_nick)}</span>
      </span>
    </button>
  `).join('');

  createModal({
    title: '选择销售',
    width: '520px',
    content: `
      <p style="font-size:var(--text-base);color:var(--text-secondary);margin-bottom:var(--space-4);line-height:1.6">找到 ${options.length} 个同名销售，请选择对应的销售进行好友分析：</p>
      <div style="display:flex;flex-direction:column;gap:var(--space-3)">${optionsHtml}</div>
    `,
  });

  window._dupOptions = options;
  window._dupPayload = payload;
}

function selectDuplicate(index) {
  const opt = window._dupOptions[index];
  const payload = {
    ...window._dupPayload,
    user_id: opt.user_id,
    friend_id: opt.friend_id,
    friend_nick: opt.friend_nick,
    friend_wx_id: opt.friend_wx_id,
  };

  // Close the modal
  document.querySelectorAll('.modal-overlay.show').forEach(el => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 200);
  });

  triggerWithIds(payload);
}
