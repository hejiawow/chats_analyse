/* ============================================
   Navigation — 页面切换和导航高亮
   ============================================ */

/** 退出登录 */
function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/login';
}

/** 获取当前用户名 */
function getCurrentUsername() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    return user.username || '';
  } catch { return ''; }
}

/** 页面加载时检查登录状态 */
(function checkAuthOnLoad() {
  if (window.location.pathname === '/login') return; // 登录页不需要跳转
  if (!localStorage.getItem('token')) {
    window.location.href = '/login';
  }
})();

function switchPage(name) {
  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

  // Show target page
  const target = document.getElementById('page-' + name);
  if (target) target.classList.add('active');

  // Update nav active state
  document.querySelectorAll('.nav-list a').forEach(a => a.classList.remove('active'));
  if (event && event.currentTarget) {
    event.currentTarget.classList.add('active');
  }

  // Update page title
  const title = PAGE_TITLES[name] || name;
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = title;

  // Load page data
  const loaders = {
    dashboard: () => loadDashboard(),
    referral: () => loadReferral(),
    cases: () => loadCases(true),
    success: () => loadSuccess(true),
    followup: () => loadFollowUp(true),
    salesjourney: () => loadSalesJourney(true),
    scriptlib: () => loadScriptLib(true),
  };

  if (loaders[name]) {
    loaders[name]();
  }
}

// Update time in topbar
function updateClock() {
  const timeEl = document.querySelector('.topbar .status-time');
  if (timeEl) {
    timeEl.textContent = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
}

// Start clock on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    updateClock();
    setInterval(updateClock, 30000);
  });
} else {
  updateClock();
  setInterval(updateClock, 30000);
}
