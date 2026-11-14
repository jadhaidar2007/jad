(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const panel = $('panel'), log = $('log'), input = $('input'), form = $('form'), typing = $('typing');
  const RES = typeof GetParentResourceName === 'function' ? GetParentResourceName() : 'jw_ainpc';
  const histories = {};       // npcId -> [{who, text}] kept for the session
  let current = null, waiting = false, timeout = null;

  const post = (name, data) => fetch(`https://${RES}/${name}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {})
  }).catch(() => {});

  function add(who, text, store = true) {
    const el = document.createElement('div');
    el.className = `msg ${who}`;
    el.textContent = text;              // textContent only: never inject HTML from the model
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    if (store && current) (histories[current] = histories[current] || []).push({ who, text });
  }

  function setWaiting(on) {
    waiting = on;
    typing.classList.toggle('hidden', !on);
    $('send').disabled = on;
    clearTimeout(timeout);
    if (on) timeout = setTimeout(() => setWaiting(false), 20000);  // never lock the input forever
  }

  function open(d) {
    current = d.npcId;
    const s = d.strings || {};
    document.documentElement.dir = s.dir || 'ltr';
    $('npc-name').textContent = d.name;
    $('npc-role').textContent = d.role || '';
    $('avatar').textContent = (d.name || '?').trim().charAt(0).toUpperCase();
    input.placeholder = s.placeholder || 'Say something...';
    input.maxLength = d.maxChars || 200;
    $('send').textContent = s.send || 'Send';
    $('hint').textContent = s.close_hint || 'ESC to leave';
    $('typing-label').textContent = `${d.name} ${s.typing || 'is typing'}`;
    log.innerHTML = '';
    (histories[current] || []).forEach((m) => add(m.who, m.text, false));
    setWaiting(false);
    panel.classList.remove('hidden');
    input.value = '';
    setTimeout(() => input.focus(), 30);
  }

  function close() {
    panel.classList.add('hidden');
    current = null;
    setWaiting(false);
  }

  window.addEventListener('message', (e) => {
    const d = e.data || {};
    if (d.action === 'open') open(d);
    else if (d.action === 'close') close();
    else if (d.action === 'reply' && d.npcId === current) { setWaiting(false); add('them', d.text); }
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || waiting || !current) return;
    add('me', text);
    input.value = '';
    setWaiting(true);
    post('send', { message: text });
  });

  $('close').addEventListener('click', () => post('close'));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') post('close'); });
})();
