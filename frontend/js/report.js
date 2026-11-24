/* report.js —— 报告页：AI 周报生成、历史、详情、下载（真实接口） */

(function () {
  let preset = 'thisweek';
  let generating = false;
  let currentReport = null;

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function dateStr(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function thisWeekRange() {
    const now = new Date();
    const day = (now.getDay() + 6) % 7; // 周一=0
    const monday = new Date(now);
    monday.setDate(now.getDate() - day);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { start: dateStr(monday), end: dateStr(sunday) };
  }

  // ---------- Markdown 渲染 ----------
  function inline(s) { return s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>'); }

  function renderMarkdown(src) {
    const lines = esc(src).split('\n');
    let html = '', list = null;
    const close = () => { if (list) { html += '</' + list + '>'; list = null; } };
    lines.forEach((line) => {
      const h = line.match(/^(#{1,3})\s+(.*)$/);
      if (h) { close(); const lv = h[1].length; html += '<h' + lv + '>' + inline(h[2]) + '</h' + lv + '>'; return; }
      const ul = line.match(/^\s*[-*]\s+(.*)$/);
      if (ul) { if (list !== 'ul') { close(); html += '<ul>'; list = 'ul'; } html += '<li>' + inline(ul[1]) + '</li>'; return; }
      const ol = line.match(/^\s*\d+\.\s+(.*)$/);
      if (ol) { if (list !== 'ol') { close(); html += '<ol>'; list = 'ol'; } html += '<li>' + inline(ol[1]) + '</li>'; return; }
      const q = line.match(/^>\s?(.*)$/);
      if (q) { close(); html += '<blockquote>' + inline(q[1]) + '</blockquote>'; return; }
      if (line.trim() === '') { close(); return; }
      close();
      html += '<p>' + inline(line) + '</p>';
    });
    close();
    return html;
  }

  function showToast(message, kind) {
    const t = document.getElementById('toast');
    t.textContent = message;
    t.className = 'toast is-show ' + (kind === 'error' ? 'is-error' : 'is-success');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { t.className = 'toast'; }, 2800);
  }

  // ---------- 后端字段 → 视图 ----------
  function toViewModel(r) {
    return {
      id: r.reportId,
      start: r.weekStart,
      end: r.weekEnd,
      content: r.content,
      createdAt: r.createdAt,
    };
  }

  function showReport(report) {
    currentReport = report;
    document.getElementById('report-title').textContent = '学习周报 · ' + report.start + ' 至 ' + report.end;
    document.getElementById('report-content').innerHTML = renderMarkdown(report.content);
    document.getElementById('report-view').hidden = false;
  }

  // ---------- 历史 ----------
  async function renderHistory() {
    const box = document.getElementById('report-history');
    let list = [];
    try {
      const data = await api.request('/reports/weekly');
      list = data.reports || [];
    } catch (_) { /* 空 */ }
    if (!list.length) {
      box.innerHTML = '<div class="history-empty">暂无历史周报</div>';
      return;
    }
    box.innerHTML = list.map((r) =>
      '<div class="history-row history-row--click" data-id="' + r.reportId + '">' +
        '<div>' +
          '<div>' + esc(r.weekStart) + ' 至 ' + esc(r.weekEnd) + '</div>' +
          '<div class="history-row__meta">' + esc(r.createdAt || '') + ' · 点击查看详情</div>' +
        '</div>' +
        '<div class="history-row__score">查看 ›</div>' +
      '</div>'
    ).join('');
  }

  // ---------- 下载（走后端接口，保证内容一致）----------
  function download() {
    if (!currentReport) return;
    const a = document.createElement('a');
    a.href = api.downloadUrl('/reports/weekly/' + currentReport.id + '/download');
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // ---------- 事件 ----------
  function bindEvents() {
    document.querySelectorAll('.range-presets .count-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        preset = btn.dataset.preset;
        document.querySelectorAll('.range-presets .count-btn').forEach((b) => b.classList.toggle('is-active', b === btn));
        document.getElementById('report-custom').hidden = preset !== 'custom';
      });
    });

    document.getElementById('report-generate-btn').addEventListener('click', async () => {
      if (generating) return;
      let start, end;
      if (preset === 'thisweek') {
        const r = thisWeekRange();
        start = r.start; end = r.end;
      } else {
        start = document.getElementById('report-start').value;
        end = document.getElementById('report-end').value;
        if (!start || !end) { showToast('请选择完整的起止日期', 'error'); return; }
        if (start > end) { showToast('开始日期不能晚于结束日期', 'error'); return; }
      }

      generating = true;
      const btn = document.getElementById('report-generate-btn');
      btn.disabled = true; btn.hidden = true;
      document.getElementById('report-generating').hidden = false;
      try {
        const r = await api.request('/reports/weekly', {
          method: 'POST',
          body: JSON.stringify({ weekStart: start, weekEnd: end }),
        });
        showReport(toViewModel(r));
        await renderHistory();
      } catch (e) {
        showToast('生成失败：' + e.message, 'error');
      } finally {
        generating = false;
        btn.disabled = false; btn.hidden = false;
        document.getElementById('report-generating').hidden = true;
      }
    });

    document.getElementById('report-download-btn').addEventListener('click', download);

    document.getElementById('report-history').addEventListener('click', async (e) => {
      const row = e.target.closest('.history-row--click');
      if (!row) return;
      try {
        const r = await api.request('/reports/weekly/' + row.dataset.id);
        showReport(toViewModel(r));
      } catch (err) {
        showToast('加载周报失败：' + err.message, 'error');
      }
    });
  }

  function init() {
    const r = thisWeekRange();
    document.getElementById('report-start').value = r.start;
    document.getElementById('report-end').value = r.end;
    bindEvents();
    renderHistory();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
