/* chat.js —— 学习页：真实会话与基于资料的 AI 问答 */

(function () {
  let docs = [];              // 已解析完成的资料，供下拉框选择
  let sessions = [];          // 会话列表
  let activeId = null;        // 当前会话 id
  let messages = [];          // 当前会话消息
  let sending = false;

  // ---------- Markdown 极简渲染 ----------
  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function inlineFormat(text) {
    return text
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  }

  function renderMarkdown(src) {
    const lines = escapeHtml(src).split('\n');
    let html = '', inCode = false, listTag = null;
    const closeList = () => { if (listTag) { html += '</' + listTag + '>'; listTag = null; } };

    for (const line of lines) {
      const fence = line.match(/^\s*```/);
      if (fence) {
        if (inCode) { html += '</code></pre>'; inCode = false; }
        else { closeList(); html += '<pre><code>'; inCode = true; }
        continue;
      }
      if (inCode) { html += line + '\n'; continue; }
      const heading = line.match(/^(#{1,3})\s+(.*)$/);
      if (heading) {
        closeList();
        const lv = heading[1].length;
        html += '<h' + lv + '>' + inlineFormat(heading[2]) + '</h' + lv + '>';
        continue;
      }
      const ul = line.match(/^\s*[-*]\s+(.*)$/);
      if (ul) {
        if (listTag !== 'ul') { closeList(); html += '<ul>'; listTag = 'ul'; }
        html += '<li>' + inlineFormat(ul[1]) + '</li>';
        continue;
      }
      const ol = line.match(/^\s*\d+\.\s+(.*)$/);
      if (ol) {
        if (listTag !== 'ol') { closeList(); html += '<ol>'; listTag = 'ol'; }
        html += '<li>' + inlineFormat(ol[1]) + '</li>';
        continue;
      }
      const quote = line.match(/^>\s?(.*)$/);
      if (quote) { closeList(); html += '<blockquote>' + inlineFormat(quote[1]) + '</blockquote>'; continue; }
      if (line.trim() === '') { closeList(); continue; }
      closeList();
      html += '<p>' + inlineFormat(line) + '</p>';
    }
    if (inCode) html += '</code></pre>';
    closeList();
    return html;
  }

  // ---------- 渲染 ----------
  function renderSessions() {
    const list = document.getElementById('session-list');
    list.innerHTML = '';
    sessions.forEach((s) => {
      const btn = document.createElement('button');
      btn.className = 'session-item' + (s.sessionId === activeId ? ' is-active' : '');
      btn.textContent = s.title || '新对话';
      btn.title = s.title || '新对话';
      btn.addEventListener('click', () => openSession(s.sessionId));
      list.appendChild(btn);
    });
  }

  function buildMessage(msg) {
    const wrap = document.createElement('div');
    wrap.className = 'message message--' + (msg.role === 'user' ? 'user' : 'ai');

    const bubble = document.createElement('div');
    bubble.className = 'message__bubble';
    if (msg.role === 'user') bubble.textContent = msg.content;
    else bubble.innerHTML = renderMarkdown(msg.content);
    wrap.appendChild(bubble);

    if (msg.sources && msg.sources.length) {
      const details = document.createElement('details');
      details.className = 'sources';
      const summary = document.createElement('summary');
      summary.textContent = '查看引用资料（' + msg.sources.length + ' 处）';
      details.appendChild(summary);
      msg.sources.forEach((src) => {
        const item = document.createElement('div');
        item.className = 'sources__item';
        const meta = document.createElement('div');
        meta.className = 'sources__meta';
        // 后台来源字段：{ docId, fileName, section }
        meta.textContent = (src.fileName || '资料' + src.docId) + (src.section ? ' · ' + src.section : '');
        item.appendChild(meta);
        if (src.text) {
          const text = document.createElement('div');
          text.className = 'sources__text';
          text.textContent = src.text;
          item.appendChild(text);
        }
        details.appendChild(item);
      });
      wrap.appendChild(details);
    }
    return wrap;
  }

  function renderMessages() {
    const box = document.getElementById('chat-messages');
    const empty = document.getElementById('chat-empty');
    Array.from(box.children).forEach((child) => { if (child !== empty) box.removeChild(child); });
    empty.style.display = messages.length ? 'none' : '';
    messages.forEach((m) => box.appendChild(buildMessage(m)));
    box.scrollTop = box.scrollHeight;
  }

  function showThinking() {
    const box = document.getElementById('chat-messages');
    const t = document.createElement('div');
    t.className = 'message message--ai';
    t.id = 'thinking-msg';
    t.innerHTML = '<div class="message__bubble"><span class="thinking__dots"><i></i><i></i><i></i></span> 正在思考...</div>';
    box.appendChild(t);
    box.scrollTop = box.scrollHeight;
  }

  function hideThinking() {
    const t = document.getElementById('thinking-msg');
    if (t) t.remove();
  }

  // ---------- 数据 ----------
  async function loadDocs() {
    try {
      const data = await api.request('/documents');
      docs = (data.documents || []).filter((d) => d.parseStatus === 'success');
    } catch (_) { docs = []; }
    const sel = document.getElementById('doc-select');
    sel.innerHTML = '<option value="">普通对话（不引用资料）</option>';
    docs.forEach((d) => {
      const opt = document.createElement('option');
      opt.value = d.docId;
      opt.textContent = d.fileName;
      sel.appendChild(opt);
    });
  }

  async function loadSessions() {
    try {
      const data = await api.request('/chat/sessions');
      sessions = data.sessions || [];
    } catch (_) { sessions = []; }
    if (!sessions.some((s) => s.sessionId === activeId)) {
      activeId = sessions.length ? sessions[0].sessionId : null;
    }
    renderSessions();
    if (activeId) await loadMessages(activeId);
    else { messages = []; renderMessages(); }
  }

  async function loadMessages(sessionId) {
    try {
      const data = await api.request('/chat/sessions/' + sessionId + '/messages');
      messages = data.messages || [];
    } catch (_) { messages = []; }
    renderMessages();
  }

  async function openSession(sessionId) {
    activeId = sessionId;
    renderSessions();
    await loadMessages(sessionId);
  }

  async function newSession() {
    try {
      const s = await api.request('/chat/sessions', {
        method: 'POST', body: JSON.stringify({ title: '新对话' }),
      });
      sessions.unshift({ sessionId: s.sessionId, title: s.title, updatedAt: s.createdAt });
      activeId = s.sessionId;
      messages = [];
      renderSessions();
      renderMessages();
    } catch (e) {
      showToast ? showToast('新建对话失败：' + e.message, 'error') : console.error(e);
    }
  }

  // ---------- 发送 ----------
  async function send() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text || sending) return;

    sending = true;
    input.value = '';
    input.disabled = true;
    document.getElementById('new-chat-btn').disabled = true;
    messages.push({ role: 'user', content: text });
    renderMessages();
    showThinking();

    const docId = document.getElementById('doc-select').value;
    const docIds = docId ? [Number(docId)] : [];
    const payload = { docIds, question: text };
    if (activeId) payload.sessionId = activeId;

    try {
      const r = await api.request('/chat', { method: 'POST', body: JSON.stringify(payload) });
      activeId = r.sessionId;
      messages.push({ role: 'assistant', content: r.answer, sources: r.sources || [] });
      // 新会话首次发消息后，刷新会话列表
      if (!sessions.some((s) => s.sessionId === activeId)) {
        sessions.unshift({ sessionId: activeId, title: text.slice(0, 20), updatedAt: null });
      }
      renderSessions();
    } catch (e) {
      messages.push({ role: 'assistant', content: '（调用失败：' + e.message + '）', sources: [] });
    } finally {
      hideThinking();
      renderMessages();
      sending = false;
      input.disabled = false;
      document.getElementById('new-chat-btn').disabled = false;
      input.focus();
    }
  }

  // ---------- 初始化 ----------
  function init() {
    Promise.all([loadDocs(), loadSessions()]);
    document.getElementById('new-chat-btn').addEventListener('click', newSession);
    const input = document.getElementById('chat-input');
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
