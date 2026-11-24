/* app.js —— 路由（# 锚点切换）+ 后台状态点 */

// Tab 的 hash 标识 → 页面 id，顺序与顶部导航一致
const ROUTES = {
  study: 'page-study',       // 学习（聊资料）
  library: 'page-library',   // 资料库（传资料）
  quiz: 'page-quiz',         // 测评（做测评）
  progress: 'page-progress', // 进度（看进度）
  report: 'page-report',     // 报告（出周报）
};
const DEFAULT_ROUTE = 'study';

/** 依据 location.hash 切换页面与高亮 Tab */
function renderRoute() {
  const key = location.hash.replace(/^#\/?/, '') || DEFAULT_ROUTE;
  const activePageId = ROUTES[key] || ROUTES[DEFAULT_ROUTE];
  const activeKey = ROUTES[key] ? key : DEFAULT_ROUTE;

  document.querySelectorAll('.page').forEach((el) => {
    el.classList.toggle('is-active', el.id === activePageId);
  });
  document.querySelectorAll('.tab').forEach((el) => {
    el.classList.toggle('is-active', el.dataset.route === activeKey);
  });
}

/** 刷新右上角状态点：连通亮绿，断开亮红 */
async function refreshStatus() {
  const dot = document.getElementById('status-dot');
  const label = document.getElementById('status-label');
  const online = await api.checkHealth();
  dot.classList.toggle('is-online', online);
  label.textContent = online ? '已连接' : '未连接';
}

function init() {
  window.addEventListener('hashchange', renderRoute);
  renderRoute();
  refreshStatus();
  setInterval(refreshStatus, 5000); // 每 5 秒探测一次
}

document.addEventListener('DOMContentLoaded', init);
