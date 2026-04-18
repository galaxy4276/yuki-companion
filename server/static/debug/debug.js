const TAB_BY_PREFIX = {
  stt: 'voice', llm: 'llm', msg: 'llm',
  mcp: 'mcp', mem: 'mcp', wiki: 'mcp', episode: 'mcp',
  tts: 'tts',
};
const MAX_PER_TAB = 200;

const state = { paused: false, filter: '', activeTab: 'voice' };
const counts = { voice: 0, llm: 0, mcp: 0, tts: 0, errors: 0 };
let unseenErrors = 0;

const LATENCY_RING = { first_chunk: [], first_audio: [], tool_loop: [] };

function _avg(arr) {
  if (!arr.length) return null;
  return Math.round(arr.reduce((a, b) => a + b, 0) / arr.length);
}

function renderLatencyCard() {
  let card = document.getElementById('latency-breakdown');
  if (!card) {
    card = document.createElement('div');
    card.id = 'latency-breakdown';
    card.style.cssText = 'padding:8px 12px;margin:6px 8px;background:#1e293b;border-left:3px solid #38bdf8;border-radius:4px;font-family:ui-monospace,monospace;font-size:12px;color:#e2e8f0;';
    const llmList = document.getElementById('list-llm');
    if (llmList && llmList.parentNode) {
      llmList.parentNode.insertBefore(card, llmList);
    } else {
      document.body.insertBefore(card, document.body.firstChild);
    }
  }
  const fc = _avg(LATENCY_RING.first_chunk);
  const fa = _avg(LATENCY_RING.first_audio);
  const tl = _avg(LATENCY_RING.tool_loop);
  const fmt = (v) => (v === null ? '–' : `${v}ms`);
  card.textContent = `첫 chunk: ${fmt(fc)} | 첫 audio: ${fmt(fa)} | tool loop: ${fmt(tl)} (최근 ${Math.max(LATENCY_RING.first_chunk.length, LATENCY_RING.first_audio.length, LATENCY_RING.tool_loop.length)}회 평균)`;
}

function updateLatencyRing(evt) {
  if (evt.stage !== 'msg.done') return;
  const p = evt.payload || {};
  for (const k of ['first_chunk_ms', 'first_audio_ms', 'tool_loop_ms']) {
    if (typeof p[k] === 'number') {
      const key = k.replace('_ms', '');
      LATENCY_RING[key].push(p[k]);
      if (LATENCY_RING[key].length > 10) LATENCY_RING[key].shift();
    }
  }
  renderLatencyCard();
}

const wsDot = document.getElementById('ws-dot');
const wsText = document.getElementById('ws-text');
const filterEl = document.getElementById('filter');
const pauseBtn = document.getElementById('pause');
const clearBtn = document.getElementById('clear');
const errorBadge = document.getElementById('error-badge');
const errorCountEl = document.getElementById('error-count');

function tabFor(stage) {
  const prefix = stage.split('.')[0];
  return TAB_BY_PREFIX[prefix] || 'voice';
}

function isFail(stage) {
  return stage.endsWith('.fail') || stage.endsWith('.error');
}

function fmtTs(ts) {
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

function previewOf(payload) {
  if (!payload) return '';
  const keys = ['reason', 'text', 'content', 'name', 'full_text'];
  for (const k of keys) {
    if (typeof payload[k] === 'string' && payload[k]) {
      return payload[k].slice(0, 120);
    }
  }
  if (typeof payload.bytes === 'number') return `${payload.bytes} bytes`;
  if (typeof payload.duration_ms === 'number') return `${payload.duration_ms}ms`;
  return JSON.stringify(payload).slice(0, 100);
}

function buildCard(evt, fail) {
  const li = document.createElement('li');
  const stageCls = fail ? 'stage fail' : 'stage';
  li.innerHTML = `
    <details${fail ? ' open' : ''}>
      <summary>
        <span class="ts">${fmtTs(evt.ts)}</span>
        <span class="${stageCls}">${evt.stage}</span>
        <span class="preview"></span>
      </summary>
      <pre></pre>
    </details>
  `;
  li.querySelector('.preview').textContent = previewOf(evt.payload);
  li.querySelector('pre').textContent = JSON.stringify(evt.payload, null, 2);
  if (fail) {
    li.classList.add('fail-card', 'fresh-fail');
    setTimeout(() => li.classList.remove('fresh-fail'), 1500);
  }
  return li;
}

function appendTo(listId, li) {
  const list = document.getElementById(listId);
  if (!list) return;
  list.insertBefore(li, list.firstChild);
  while (list.children.length > MAX_PER_TAB) list.removeChild(list.lastChild);
}

function bumpCount(tab) {
  counts[tab] = (counts[tab] || 0) + 1;
  const cnt = document.getElementById('count-' + tab);
  if (cnt) cnt.textContent = counts[tab];
}

function showErrorBadge() {
  unseenErrors += 1;
  errorCountEl.textContent = unseenErrors;
  errorBadge.classList.remove('hidden');
}

function clearErrorBadge() {
  unseenErrors = 0;
  errorBadge.classList.add('hidden');
}

function render(evt) {
  if (state.paused) return;
  if (state.filter && !evt.stage.includes(state.filter)) return;

  const fail = isFail(evt.stage);
  const tab = tabFor(evt.stage);

  appendTo('list-' + tab, buildCard(evt, fail));
  bumpCount(tab);

  updateLatencyRing(evt);

  if (fail) {
    appendTo('list-errors', buildCard(evt, true));
    bumpCount('errors');
    if (state.activeTab !== 'errors') showErrorBadge();
    flashTabErrors();
  }
}

function flashTabErrors() {
  const t = document.querySelector('.tab-errors');
  if (!t) return;
  t.style.animation = 'none';
  t.offsetHeight;
  t.style.animation = 'badge-pulse 1.4s';
  setTimeout(() => { t.style.animation = ''; }, 1500);
}

function connectWS() {
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
  const ws = new WebSocket(wsUrl);
  ws.onopen = () => { wsDot.classList.add('ok'); wsText.textContent = 'connected'; };
  ws.onclose = () => {
    wsDot.classList.remove('ok'); wsText.textContent = 'reconnecting...';
    setTimeout(connectWS, 3000);
  };
  ws.onerror = () => { wsDot.classList.remove('ok'); wsText.textContent = 'error'; };
  ws.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.type === 'debug_event') render(d);
    } catch {}
  };
}
connectWS();

function activateTab(tab) {
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.event-list').forEach(l => l.classList.add('hidden'));
  const btn = document.querySelector(`.tab[data-tab="${tab}"]`);
  if (btn) btn.classList.add('active');
  document.getElementById('list-' + tab).classList.remove('hidden');
  state.activeTab = tab;
  if (tab === 'errors') clearErrorBadge();
}

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});

errorBadge.addEventListener('click', () => activateTab('errors'));

filterEl.addEventListener('input', () => { state.filter = filterEl.value.trim(); });

pauseBtn.addEventListener('click', () => {
  state.paused = !state.paused;
  pauseBtn.textContent = state.paused ? '▶ Resume' : '⏸ Pause';
  pauseBtn.classList.toggle('active', state.paused);
});

clearBtn.addEventListener('click', () => {
  document.querySelectorAll('.event-list').forEach(l => { l.innerHTML = ''; });
  for (const k of Object.keys(counts)) {
    counts[k] = 0;
    const cnt = document.getElementById('count-' + k);
    if (cnt) cnt.textContent = 0;
  }
  clearErrorBadge();
});
