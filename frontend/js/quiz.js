/* quiz.js —— 测评页：AI 出题、作答、AI 阅卷、结果、历史（真实接口） */

(function () {
  const RING_CIRCUMFERENCE = 2 * Math.PI * 52;
  const TIME_KEY = 'study_assistant_quiz_time_v1'; // 仅本地记用时，后端不存时长

  const TYPE_LABEL = { choice: '选择题', judge: '判断题', short: '简答题' };
  const DIFF_CLASS = {
    '简单': 'tag--diff-easy', '中等': 'tag--diff-medium', '较难': 'tag--diff-hard',
    easy: 'tag--diff-easy', medium: 'tag--diff-medium', hard: 'tag--diff-hard',
  };

  let docs = [];
  let count = 5;
  let quizId = null;
  let questions = [];   // 统一结构：{ id, type, question, options:{A,B..}, difficulty }
  let answers = {};     // qid -> 提交值（choice: 'A'；judge: '正确'/'错误'；short: 文本）
  let startTime = 0;
  let timerId = null;
  let generating = false;
  let grading = false;
  let lastResult = null;

  // ---------- 工具 ----------
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmtTime(sec) {
    const m = String(Math.floor(sec / 60)).padStart(2, '0');
    const s = String(sec % 60).padStart(2, '0');
    return m + ':' + s;
  }

  function elapsedSec() { return Math.floor((Date.now() - startTime) / 1000); }

  function showView(name) {
    const map = { setup: 'quiz-setup', answering: 'quiz-answering', result: 'quiz-result' };
    Object.values(map).forEach((id) => { document.getElementById(id).hidden = true; });
    document.getElementById(map[name]).hidden = false;
  }

  function readTimes() {
    try { return JSON.parse(localStorage.getItem(TIME_KEY) || '{}'); } catch (_) { return {}; }
  }
  function saveTime(qid, sec) {
    const all = readTimes();
    all[qid] = sec;
    localStorage.setItem(TIME_KEY, JSON.stringify(all));
  }

  // ---------- 选项规范化（关键）----------
  // 后台 options 可能是：数组、JSON 字符串、换行字符串、对象、null
  // 统一输出对象 { A: '文字', B: '文字' ... }；判断题固定 A=正确 / B=错误
  function parseLineOptions(text) {
    const obj = {};
    let i = 0;
    String(text).split(/\n+/).map((x) => x.trim()).filter(Boolean).forEach((line) => {
      const m = line.match(/^([A-Da-d])[\.、:：\)）]\s*(.*)$/);
      if (m) obj[m[1].toUpperCase()] = m[2];
      else obj[String.fromCharCode(65 + i++)] = line;
    });
    return obj;
  }

  function stripPrefix(text, idx) {
    const m = String(text).match(/^\s*([A-Da-d])[\.、:：\)）]\s*(.*)$/);
    if (m) return m[2];
    return String(text);
  }

  function normalizeOptions(q) {
    if (q.type === 'judge') return { A: '正确', B: '错误' }; // 判断题固定
    if (q.type !== 'choice') return {};

    let opts = q.options;
    if (opts == null || opts === '') return {};
    if (typeof opts === 'string') {
      const s = opts.trim();
      if (s.startsWith('[') || s.startsWith('{')) {
        try { opts = JSON.parse(s); } catch (_) { opts = parseLineOptions(s); }
      } else {
        opts = parseLineOptions(s);
      }
    }
    const obj = {};
    if (Array.isArray(opts)) {
      opts.forEach((o, i) => { obj[String.fromCharCode(65 + i)] = stripPrefix(o, i); });
    } else if (typeof opts === 'object') {
      Object.keys(opts).forEach((k) => { obj[String(k).toUpperCase()] = String(opts[k]); });
    }
    return obj;
  }

  function toQuestion(raw, idx) {
    return {
      id: raw.questionId != null ? raw.questionId : 'q' + idx,
      type: raw.type,
      question: raw.question,
      options: normalizeOptions(raw),
      difficulty: raw.difficulty || '中等',
      answer: raw.answer,
      keyPoints: raw.keyPoints,
      source: raw.source,
    };
  }

  function diffText(d) {
    const map = { easy: '简单', medium: '中等', hard: '困难' };
    return map[d] || d || '中等';
  }

  function showToast(message, kind) {
    const t = document.getElementById('toast');
    t.textContent = message;
    t.className = 'toast is-show ' + (kind === 'error' ? 'is-error' : 'is-success');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { t.className = 'toast'; }, 2800);
  }

  // ---------- 数据 ----------
  async function loadDocs() {
    try {
      const data = await api.request('/documents');
      docs = (data.documents || []).filter((d) => d.parseStatus === 'success');
    } catch (_) { docs = []; }
    const sel = document.getElementById('quiz-doc-select');
    sel.innerHTML = '<option value="">全部资料</option>';
    docs.forEach((d) => {
      const opt = document.createElement('option');
      opt.value = d.docId;
      opt.textContent = d.fileName;
      sel.appendChild(opt);
    });
  }

  async function generate() {
    if (generating) return;
    generating = true;
    const btn = document.getElementById('quiz-start-btn');
    btn.disabled = true; btn.hidden = true;
    document.getElementById('quiz-generating').hidden = false;

    const docVal = document.getElementById('quiz-doc-select').value;
    const payload = { total: count, docIds: docVal ? [Number(docVal)] : [] };
    try {
      const data = await api.request('/quiz/generate', {
        method: 'POST', body: JSON.stringify(payload),
      });
      quizId = data.quizId;
      questions = (data.questions || []).map(toQuestion);
      if (!questions.length) throw new Error('AI 未生成题目，请检查资料是否已解析完成');
      answers = {};
      renderQuestions();
      updateProgress();
      startTimer();
      showView('answering');
    } catch (e) {
      showToast('生成失败：' + e.message, 'error');
      showView('setup');
    } finally {
      generating = false;
      btn.disabled = false; btn.hidden = false;
      document.getElementById('quiz-generating').hidden = true;
    }
  }

  // ---------- 答题渲染 ----------
  function renderQuestions() {
    const box = document.getElementById('quiz-questions');
    box.innerHTML = questions.map((q, i) => {
      let body = '';
      if (q.type === 'choice' || q.type === 'judge') {
        const keys = Object.keys(q.options).sort();
        body = '<div class="options">' + keys.map((k) => {
          const val = q.type === 'judge' ? q.options[k] : k; // judge 存 '正确'/'错误'
          return '<div class="option" data-qid="' + q.id + '" data-val="' + esc(val) + '">' +
            '<span class="option__key">' + k + '</span>' +
            '<span>' + esc(q.options[k]) + '</span></div>';
        }).join('') + '</div>';
      } else {
        body = '<textarea class="answer-text" data-qid="' + q.id + '" placeholder="请输入你的答案"></textarea>';
      }
      const dt = diffText(q.difficulty);
      return (
        '<div class="card question-card">' +
          '<div class="question-card__head">' +
            '<span class="tag tag--type">' + (TYPE_LABEL[q.type] || q.type) + '</span>' +
            '<span class="tag ' + (DIFF_CLASS[dt] || '') + '">' + esc(dt) + '</span>' +
          '</div>' +
          '<div class="question-card__stem"><span class="q-index">' + (i + 1) + '.</span>' + esc(q.question) + '</div>' +
          body +
        '</div>'
      );
    }).join('');
  }

  function updateProgress() {
    const answered = questions.filter((q) => answers[q.id] !== undefined && answers[q.id] !== '').length;
    document.getElementById('quiz-progress-text').textContent =
      '已作答 ' + answered + ' / ' + questions.length + ' 题';
  }

  function startTimer() {
    clearInterval(timerId);
    startTime = Date.now();
    document.getElementById('quiz-timer').textContent = '00:00';
    timerId = setInterval(() => {
      document.getElementById('quiz-timer').textContent = fmtTime(elapsedSec());
    }, 1000);
  }

  // ---------- 提交阅卷 ----------
  async function submitQuiz() {
    if (grading) return;
    grading = true;
    clearInterval(timerId);
    const sec = elapsedSec();
    const btn = document.getElementById('quiz-submit-btn');
    btn.disabled = true; btn.hidden = true;
    document.getElementById('quiz-abandon-btn').disabled = true;
    document.getElementById('quiz-grading').hidden = false;

    const payload = {
      answers: questions.map((q) => ({
        questionId: q.id,
        answer: answers[q.id] != null ? answers[q.id] : '',
      })),
    };

    try {
      const graded = await api.request('/quiz/' + quizId + '/submit', {
        method: 'POST', body: JSON.stringify(payload),
      });
      saveTime(quizId, sec);
      // 拿详情：含正确答案 / 你的答案 / AI 点评
      const detail = await api.request('/quiz/' + quizId);
      renderResult(graded, detail, sec);
      await renderHistory();
      lastResult = { graded, detail };
      showView('result');
    } catch (e) {
      showToast('阅卷失败：' + e.message, 'error');
      btn.disabled = false; btn.hidden = false;
      document.getElementById('quiz-abandon-btn').disabled = false;
      document.getElementById('quiz-grading').hidden = true;
    } finally {
      grading = false;
      btn.disabled = false; btn.hidden = false;
      document.getElementById('quiz-abandon-btn').disabled = false;
      document.getElementById('quiz-grading').hidden = true;
    }
  }

  // ---------- 结果渲染 ----------
  function answerText(qtype, val, options) {
    if (val == null || val === '') return '未作答';
    if (qtype === 'choice') {
      const k = String(val).toUpperCase();
      return options[k] ? (k + '. ' + options[k]) : String(val);
    }
    return String(val);
  }

  function renderResult(graded, detail, sec) {
    const total = Number(graded.total) || (detail.questions || []).length;
    const score = Number(graded.score) || 0;
    const qs = detail.questions || [];
    const correct = qs.filter((q) => q.correct === true).length;
    const wrong = qs.length - correct;

    document.getElementById('ring-score').textContent = score;
    document.getElementById('ring-total').textContent = '/ ' + total;
    document.getElementById('stat-correct').textContent = correct;
    document.getElementById('stat-wrong').textContent = wrong;
    document.getElementById('stat-time').textContent = fmtTime(sec);

    const fill = document.getElementById('ring-fill');
    fill.style.strokeDashoffset = RING_CIRCUMFERENCE;
    const ratio = total > 0 ? score / total : 0;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fill.style.strokeDashoffset = RING_CIRCUMFERENCE * (1 - ratio);
    }));

    document.getElementById('quiz-result-list').innerHTML = qs.map((q, i) => {
      const options = normalizeOptions(q);
      const isRight = q.correct === true;
      const part = Number(q.score) === 0.5;
      const mark = isRight ? '正确' : (part ? '部分正确' : '错误');
      const answer = q.type === 'short'
        ? (q.answer || (q.keyPoints || []).join('、') || '见参考答案')
        : answerText(q.type, q.answer, options);
      return (
        '<details class="result-item">' +
          '<summary class="result-item__summary">' +
            '<span class="result-item__mark ' + (isRight ? 'is-right' : 'is-wrong') + '">' + mark + '</span>' +
            '<span class="result-item__stem">' + (i + 1) + '. ' + esc(q.question) + '</span>' +
            '<span class="result-item__score">' + (q.score != null ? q.score : 0) + ' 分</span>' +
          '</summary>' +
          '<div class="result-item__body">' +
            '<div class="result-line result-line--right"><span class="result-line__label">正确答案：</span><span class="result-line__value">' + esc(answer) + '</span></div>' +
            '<div class="result-line ' + (isRight ? 'result-line--right' : 'result-line--wrong') + '"><span class="result-line__label">你的答案：</span><span class="result-line__value">' + esc(answerText(q.type, q.userAnswer, options)) + '</span></div>' +
            '<div class="result-comment"><span class="result-line__label">AI 点评：</span>' + esc(q.feedback || '无') + '</div>' +
          '</div>' +
        '</details>'
      );
    }).join('');
  }

  async function renderHistory() {
    const box = document.getElementById('quiz-history-list');
    let list = [];
    try {
      const data = await api.request('/quiz/history');
      list = data.quizzes || [];
    } catch (_) { /* 空 */ }
    if (!list.length) {
      box.innerHTML = '<div class="history-empty">暂无测评记录</div>';
      return;
    }
    const times = readTimes();
    box.innerHTML = list.map((h) =>
      '<div class="history-row">' +
        '<div>' +
          '<div>测评 #' + h.quizId + ' · ' + (h.total != null ? h.total : 0) + ' 题</div>' +
          '<div class="history-row__meta">' + esc(h.createdAt || '') +
            ' · 用时 ' + fmtTime(times[h.quizId] || 0) + '</div>' +
        '</div>' +
        '<div class="history-row__score">' + (h.score != null ? h.score : 0) + ' / ' + (h.total != null ? h.total : 0) + '</div>' +
      '</div>'
    ).join('');
  }

  // ---------- 事件 ----------
  function bindEvents() {
    document.getElementById('quiz-count-group').addEventListener('click', (e) => {
      const btn = e.target.closest('.count-btn');
      if (!btn) return;
      count = Number(btn.dataset.count);
      document.querySelectorAll('.count-btn').forEach((b) => b.classList.toggle('is-active', b === btn));
    });

    document.getElementById('quiz-start-btn').addEventListener('click', generate);

    document.getElementById('quiz-questions').addEventListener('click', (e) => {
      const opt = e.target.closest('.option');
      if (!opt) return;
      const qid = opt.dataset.qid;
      answers[qid] = opt.dataset.val;
      const card = opt.closest('.question-card');
      card.querySelectorAll('.option').forEach((o) => o.classList.toggle('is-selected', o === opt));
      updateProgress();
    });

    document.getElementById('quiz-questions').addEventListener('input', (e) => {
      const ta = e.target.closest('.answer-text');
      if (!ta) return;
      answers[ta.dataset.qid] = ta.value;
      updateProgress();
    });

    document.getElementById('quiz-abandon-btn').addEventListener('click', () => {
      clearInterval(timerId);
      showView('setup');
    });

    document.getElementById('quiz-submit-btn').addEventListener('click', submitQuiz);
  }

  function init() {
    bindEvents();
    loadDocs();
    renderHistory();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
