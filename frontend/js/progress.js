/* progress.js —— 进度页：后端统计/知识点/薄弱点 + 本地笔记 */

(function () {
  const NOTES_KEY = 'study_assistant_notes_v1';
  let points = [];   // 后端知识点：{ knowledgePointId, name, mastery, status, docId }

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function readNotes() {
    try { return JSON.parse(localStorage.getItem(NOTES_KEY) || '{}'); } catch (_) { return {}; }
  }

  // 后台 status：mastered / weak / unlearned → 中文等级
  function levelOf(status) {
    if (status === 'mastered') return '掌握';
    if (status === 'weak') return '薄弱';
    return '未学';
  }
  const LEVEL_STATUS = { 掌握: 'mastered', 薄弱: 'weak', 未学: 'unlearned' };

  // ---------- 顶部统计 ----------
  async function renderOverview() {
    try {
      const [ov, kp] = await Promise.all([
        api.request('/progress/overview'),
        api.request('/progress/knowledge-points'),
      ]);
      points = kp.points || [];
      const mastered = points.filter((p) => p.status === 'mastered').length;
      const weak = points.filter((p) => p.status === 'weak').length;
      document.getElementById('ov-docs').textContent = ov.documentCount || 0;
      document.getElementById('ov-mastered').textContent = mastered;
      document.getElementById('ov-quizzes').textContent = ov.quizCount || 0;
      document.getElementById('ov-avg').textContent = Math.round((ov.avgAccuracy || 0) * 100);
      document.getElementById('ov-weak').textContent = weak;
      renderRadar();
      renderPoints();
      renderWeak();
    } catch (e) {
      console.error('进度统计加载失败', e);
    }
  }

  // ---------- 雷达图 ----------
  function renderRadar() {
    const cx = 170, cy = 155, r = 110;
    const n = points.length;
    const box = document.getElementById('radar');
    if (n === 0) { box.innerHTML = '<div class="doc-empty">答题后生成知识点掌握图</div>'; return; }
    const angle = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const pt = (i, radius) => [cx + radius * Math.cos(angle(i)), cy + radius * Math.sin(angle(i))];
    const polygon = (scale) => Array.from({ length: n }, (_, i) => pt(i, r * scale).map((v) => v.toFixed(1)).join(',')).join(' ');

    let svg = '<svg viewBox="0 0 340 310" xmlns="http://www.w3.org/2000/svg">';
    [0.25, 0.5, 0.75, 1].forEach((s) => { svg += '<polygon class="radar__grid" points="' + polygon(s) + '"/>'; });
    for (let i = 0; i < n; i++) {
      const [x, y] = pt(i, r);
      svg += '<line class="radar__axis" x1="' + cx + '" y1="' + cy + '" x2="' + x.toFixed(1) + '" y2="' + y.toFixed(1) + '"/>';
    }
    const area = points.map((p, i) => pt(i, r * (p.mastery || 0)).map((v) => v.toFixed(1)).join(',')).join(' ');
    svg += '<polygon class="radar__area" points="' + area + '"/>';
    points.forEach((p, i) => {
      const [x, y] = pt(i, r * (p.mastery || 0));
      svg += '<circle class="radar__point" cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="3"/>';
    });
    points.forEach((p, i) => {
      const [x, y] = pt(i, r + 22);
      svg += '<text class="radar__label" x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" text-anchor="middle" dominant-baseline="middle">' + esc(p.name) + '</text>';
    });
    svg += '</svg>';
    box.innerHTML = svg;
  }

  // ---------- 知识点清单 ----------
  function renderPoints() {
    const box = document.getElementById('kp-list');
    if (!points.length) { box.innerHTML = '<div class="doc-empty">暂无知识点，完成一次测评后生成</div>'; return; }
    box.innerHTML = points.map((p) => {
      const pct = Math.round((p.mastery || 0) * 100);
      const level = levelOf(p.status);
      return (
        '<div class="kp-row">' +
          '<div class="kp-row__head">' +
            '<span>' + esc(p.name) + '</span>' +
            '<span class="kp-row__level" data-level="' + LEVEL_STATUS[level] + '">' + level + ' ' + pct + '%</span>' +
          '</div>' +
          '<div class="progress-bar"><div class="progress-bar__fill" data-level="' + LEVEL_STATUS[level] + '" style="width:' + pct + '%"></div></div>' +
        '</div>'
      );
    }).join('');
  }

  // ---------- 资料详情 + 笔记（笔记存本地，文档无笔记接口）----------
  async function renderDocs() {
    const box = document.getElementById('doc-detail-list');
    let docs = [];
    try {
      const data = await api.request('/documents');
      docs = data.documents || [];
    } catch (_) { /* 空 */ }
    const notes = readNotes();

    if (!docs.length) {
      box.innerHTML = '<div class="card"><div class="doc-empty">暂无资料，去资料库上传后显示在这里</div></div>';
      return;
    }

    box.innerHTML = docs.map((d) =>
      '<div class="card doc-detail">' +
        '<div class="doc-detail__head">' +
          '<span class="doc-detail__title">' + esc(d.fileName) + '</span>' +
          '<span class="doc-detail__label">笔记</span>' +
        '</div>' +
        '<div class="note-box">' +
          '<div class="note-box__area">' +
            '<textarea class="note-textarea" data-id="' + d.docId + '" placeholder="写下你的学习笔记，输入后自动保存...">' + esc(notes[d.docId] || '') + '</textarea>' +
            '<div class="note-status" data-status="' + d.docId + '"></div>' +
          '</div>' +
          '<div class="note-slider">' +
            '<input type="range" min="80" max="400" value="220" data-slider="' + d.docId + '" aria-label="笔记缩略">' +
            '<span class="note-slider__hint">缩略</span>' +
          '</div>' +
        '</div>' +
      '</div>'
    ).join('');

    box.querySelectorAll('input[data-slider]').forEach((slider) => {
      const ta = box.querySelector('.note-textarea[data-id="' + slider.dataset.slider + '"]');
      if (ta) ta.style.maxHeight = slider.value + 'px';
      slider.addEventListener('input', () => {
        if (ta) ta.style.maxHeight = slider.value + 'px';
      });
    });

    const timers = {};
    box.querySelectorAll('.note-textarea').forEach((ta) => {
      ta.addEventListener('input', () => {
        const id = ta.dataset.id;
        const status = box.querySelector('.note-status[data-status="' + id + '"]');
        status.textContent = '输入中...';
        status.classList.remove('is-saved');
        clearTimeout(timers[id]);
        timers[id] = setTimeout(() => {
          const all = readNotes();
          all[id] = ta.value;
          localStorage.setItem(NOTES_KEY, JSON.stringify(all));
          status.textContent = '已自动保存';
          status.classList.add('is-saved');
        }, 800);
      });
    });
  }

  // ---------- 薄弱知识点（走后端弱点到接口）----------
  async function renderWeak() {
    const box = document.getElementById('weak-list');
    let weak = [];
    try {
      const data = await api.request('/progress/weak-points');
      weak = data.weakPoints || [];
    } catch (_) { /* 空 */ }
    if (!weak.length) {
      box.innerHTML = '<div class="weak-empty">暂无薄弱知识点，继续保持！</div>';
      return;
    }
    box.innerHTML = weak.map((p) =>
      '<div class="weak-row">' +
        '<span class="weak-row__name">' + esc(p.name) + '</span>' +
        '<span class="weak-row__score">掌握度 ' + Math.round((p.mastery || 0) * 100) + '%</span>' +
      '</div>'
    ).join('');
  }

  function init() {
    renderOverview();
    renderDocs();
    renderWeak();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
