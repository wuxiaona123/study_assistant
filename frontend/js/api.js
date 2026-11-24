/* api.js —— 后台请求封装（统一指向 Flask 后端） */

// 后端独立运行在 5000 端口，不能用相对路径（静态服务在别的端口会 404）
const API_BASE = 'http://127.0.0.1:5000/api';

/**
 * 通用请求
 * @param {string} path   接口路径，如 '/documents'
 * @param {object} options fetch 选项；body 为 FormData 时不设 Content-Type
 * @returns {Promise<any>} 解析后的 JSON
 */
async function request(path, options = {}) {
  const isForm = options.body instanceof FormData;
  const headers = Object.assign(
    {},
    isForm ? {} : { 'Content-Type': 'application/json' },
    options.headers || {}
  );
  const res = await fetch(API_BASE + path, { ...options, headers });
  if (!res.ok) {
    let msg = 'HTTP ' + res.status;
    try { const e = await res.json(); if (e.error) msg = e.error; } catch (_) { /* 忽略 */ }
    throw new Error(msg);
  }
  return res.json();
}

/** 连通探测：请求 /api/health，成功即视为后台在线 */
async function checkHealth() {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(API_BASE + '/health', { signal: controller.signal });
    clearTimeout(timer);
    return res.ok;
  } catch (e) {
    return false;
  }
}

/** 下载接口地址（不用 fetch，直接给 <a href> 触发浏览器下载） */
function downloadUrl(path) {
  return API_BASE + path;
}

const api = { request, checkHealth, downloadUrl };
