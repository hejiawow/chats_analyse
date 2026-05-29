/* ============================================
   API — 统一的 API 请求封装（自动携带 JWT Token）
   ============================================ */

let apiAvailable = true;

/** 获取当前用户的 Token */
function getAuthToken() {
  return localStorage.getItem('token');
}

/** 构建请求头（自动附带 Token） */
function authHeaders(extra) {
  const headers = { ...extra };
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = 'Bearer ' + token;
  }
  return headers;
}

/** 检查未登录时跳转到登录页 */
function requireAuth() {
  if (!getAuthToken()) {
    window.location.href = '/login';
    return false;
  }
  return true;
}

/** 处理 401 响应 */
function handleUnauthorized() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/login';
}

async function apiFetch(url) {
  if (!requireAuth()) return null;
  try {
    const res = await fetch(API_BASE + url, {
      headers: authHeaders({}),
    });
    if (res.status === 401) { handleUnauthorized(); return null; }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    apiAvailable = true;
    return await res.json();
  } catch (e) {
    apiAvailable = false;
    console.warn('API 不可用:', e.message);
    return null;
  }
}

async function apiPost(url, body) {
  if (!requireAuth()) throw new Error('未登录');
  try {
    const res = await fetch(API_BASE + url, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    });
    if (res.status === 401) { handleUnauthorized(); throw new Error('登录已过期'); }
    apiAvailable = true;
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: '请求失败' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (e) {
    apiAvailable = false;
    throw e;
  }
}

function downloadFile(url) {
  // 下载也携带 Token（通过 fetch 获取 blob 再下载）
  const token = getAuthToken();
  if (token) {
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(res => res.blob())
      .then(blob => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
      });
  } else {
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
}
