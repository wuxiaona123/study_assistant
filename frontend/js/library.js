/* library.js —— 资料库：真实上传、状态轮询、重新解析、删除 */

(function () {
  const ALLOWED_EXT = ['pdf', 'ppt', 'pptx', 'doc', 'docx', 'md', 'markdown', 'txt'];
  const STATUS_TEXT = { parsing: '解析中', success: '完成', failed: '失败' };

  let docs = [];
  let toastTimer = null;
  let pollTimer = null;

  // ---------- 工具 ----------
  function extOf(name) {
    const i = name.lastIndexOf('.');
    return i === -1 ? '' : name.slice(i + 1).toLowerCase();
  }

  function formatSize(bytes) {
    bytes = Number(bytes) || 0;
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  function esc(str) {
    return String(str == null ? '' : str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function showToast(message, kind) {
    const t = document.getElementById('toast');
    t.textContent = message;
    t.className = 'toast is-show ' + (kind === 'error' ? 'is-error' : 'is-success');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.className = 'toast'; }, 2800);
  }

  // ---------- 渲染 ----------
  function render() {
    const list = document.getElementById('doc-list');
    document.getElementById('doc-count').textContent = docs.length + ' 份';

    if (!docs.length) {
      list.innerHTML = '<div class="doc-empty">暂无资料，上传后显示在这里</div>';
      return;
    }

    list.innerHTML = docs.map((d) => {
      const actions = [];
      if (d.parseStatus === 'failed') {
        actions.push('<button class="mini-btn mini-btn--retry" data-act="retry" data-id="' + d.docId + '">重试</button>');
      }
      actions.push('<button class="mini-btn mini-btn--delete" data-act="delete" data-id="' + d.docId + '">删除</button>');
      const badge = '<span class="status-badge" data-status="' + d.parseStatus + '"' +
        (d.failReason ? ' title="' + esc(d.failReason) + '"' : '') + '>' +
        (STATUS_TEXT[d.parseStatus] || d.parseStatus) + '</span>';
      return (
        '<div class="doc-row">' +
          '<span class="doc-name" title="' + esc(d.fileName) + '">' + esc(d.fileName) + '</span>' +
          '<span>' + esc((d.fileType || '').toUpperCase()) + '</span>' +
          '<span>' + formatSize(d.fileSize) + '</span>' +
          '<span>' + badge + '</span>' +
          '<span class="doc-actions">' + actions.join('') + '</span>' +
        '</div>'
      );
    }).join('');
  }

  // ---------- 数据 ----------
  async function loadDocs() {
    try {
      const data = await api.request('/documents');
      docs = data.documents || [];
      render();
      schedulePoll();
    } catch (e) {
      showToast('加载资料失败：' + e.message, 'error');
    }
  }

  // 有解析中的文档时轮询状态，直到全部结束
  function schedulePoll() {
    clearTimeout(pollTimer);
    if (!docs.some((d) => d.parseStatus === 'parsing')) return;
    pollTimer = setTimeout(async () => {
      for (const d of docs.filter((x) => x.parseStatus === 'parsing')) {
        try {
          const st = await api.request('/documents/' + d.docId + '/status');
          d.parseStatus = st.parseStatus;
          d.failReason = st.failReason || null;
        } catch (_) { /* 单次失败下一轮再试 */ }
      }
      render();
      schedulePoll();
    }, 1500);
  }

  // ---------- 上传 ----------
  async function handleFiles(files) {
    let ok = 0, fail = 0;
    for (const file of Array.from(files)) {
      if (!ALLOWED_EXT.includes(extOf(file.name))) { fail++; continue; }
      const form = new FormData();
      form.append('file', file);
      try {
        const r = await api.request('/documents/upload', { method: 'POST', body: form });
        docs.unshift({
          docId: r.docId, fileName: r.fileName, fileType: extOf(r.fileName),
          fileSize: file.size, parseStatus: r.parseStatus,
        });
        ok++;
      } catch (e) {
        fail++;
      }
    }
    render();
    if (ok > 0) { showToast('已上传 ' + ok + ' 份，正在后台解析', 'success'); schedulePoll(); }
    if (fail > 0) showToast(fail + ' 份上传失败或格式不支持', 'error');
  }

  // ---------- 初始化 ----------
  function init() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');

    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) handleFiles(fileInput.files);
      fileInput.value = '';
    });

    ['dragenter', 'dragover'].forEach((type) => {
      dropzone.addEventListener(type, (e) => { e.preventDefault(); dropzone.classList.add('is-dragover'); });
    });
    ['dragleave', 'drop'].forEach((type) => {
      dropzone.addEventListener(type, (e) => { e.preventDefault(); dropzone.classList.remove('is-dragover'); });
    });
    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
    });

    document.getElementById('doc-list').addEventListener('click', async (e) => {
      const btn = e.target.closest('button[data-act]');
      if (!btn) return;
      const id = btn.dataset.id;
      try {
        if (btn.dataset.act === 'delete') {
          await api.request('/documents/' + id, { method: 'DELETE' });
          docs = docs.filter((d) => String(d.docId) !== id);
          render();
          showToast('已删除', 'success');
        } else if (btn.dataset.act === 'retry') {
          const r = await api.request('/documents/' + id + '/reparse', { method: 'POST' });
          const doc = docs.find((d) => String(d.docId) === id);
          if (doc) { doc.parseStatus = r.parseStatus; doc.failReason = null; }
          render();
          schedulePoll();
          showToast('已重新解析', 'success');
        }
      } catch (err) {
        showToast('操作失败：' + err.message, 'error');
      }
    });

    loadDocs();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
