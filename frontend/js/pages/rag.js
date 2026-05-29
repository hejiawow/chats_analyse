/* ============================================
   RAG Q&A Page
   ============================================ */

async function ragAsk() {
  const input = document.getElementById('rag-input');
  const btn = document.getElementById('rag-btn');
  const chat = document.getElementById('rag-chat');
  const query = input.value.trim();
  if (!query) return;

  // Clear welcome message
  if (chat.querySelector('.rag-welcome')) {
    chat.innerHTML = '';
  }

  // User message
  chat.innerHTML += `
    <div class="rag-message rag-message-user">
      <div class="rag-bubble">${escapeHtml(query)}</div>
    </div>
  `;

  // Loading indicator
  chat.innerHTML += `
    <div id="rag-loading" class="rag-message rag-message-bot">
      <div class="rag-bubble">
        <div class="rag-loading-dots">
          <span></span><span></span><span></span>
        </div>
        <span style="font-size:var(--text-sm);color:var(--text-muted);margin-left:var(--space-2)">思考中</span>
      </div>
    </div>
  `;

  chat.scrollTop = chat.scrollHeight;
  input.value = '';
  btn.disabled = true;

  try {
    const res = await fetch(API_BASE + '/api/rag/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: 5 }),
    });

    document.getElementById('rag-loading')?.remove();

    if (res.ok) {
      const data = await res.json();
      const answerHtml = formatRagAnswer(data.answer);

      let sourcesHtml = '';
      if (data.sources?.length) {
        sourcesHtml = `
          <div class="rag-sources">
            <span class="rag-sources-label">参考来源 (${data.sources.length} 个案例)</span>
            <div class="rag-source-tags">
              ${data.sources.map(s => `
                <span class="rag-source-tag" onclick="showScriptDetail(${s.id})">
                  ${escapeHtml(s.scenario_type || '未分类')}
                </span>
              `).join('')}
            </div>
          </div>
        `;
      }

      chat.innerHTML += `
        <div class="rag-message rag-message-bot">
          <div class="rag-bubble">
            ${answerHtml}${sourcesHtml}
          </div>
        </div>
      `;
    } else {
      const err = await res.json();
      chat.innerHTML += `
        <div class="rag-message">
          <div class="rag-error">
            ${err.detail || '请求失败'}
          </div>
        </div>
      `;
    }
  } catch (e) {
    document.getElementById('rag-loading')?.remove();
    chat.innerHTML += `
      <div class="rag-message">
        <div class="rag-error">
          网络错误: ${e.message}
        </div>
      </div>
    `;
  }

  btn.disabled = false;
  chat.scrollTop = chat.scrollHeight;
}

function formatRagAnswer(text) {
  if (!text) return '';
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}
