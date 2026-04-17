const TAB_BY_PREFIX = {
  stt: 'voice', llm: 'llm', msg: 'llm', mcp: 'mcp', tts: 'tts',
};
const MAX_PER_TAB = 200;

const state = { paused: false, filter: '', activeTab: 'voice' };
const counts = { voice: 0, llm: 0, mcp: 0, tts: 0 };

const wsDot = document.getElementById('ws-dot');
const wsText = document.getElementById('ws-text');
const filterEl = document.getElementById('filter');
const pauseBtn = document.getElementById('pause');
const clearBtn = document.getElementById('clear');

function tabFor(stage) {
  const prefix = stage.split('.')[0];
  return TAB_BY_PREFIX[prefix] || 'voice';
}

function fmtTs(ts) {
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

function previewOf(payload) {
  if (!payload) return '';
  const keys = ['text', 'content', 'name', 'reason', 'full_text'];
  for (const k of keys) {
    if (typeof payload[k] === 'string' && payload[k]) {
      return payload[k].slice(0, 100);
    }
  }
  if (typeof payload.bytes === 'number') return `${payload.bytes} bytes`;
  if (typeof payload.duration_ms === 'number') return `${payload.duration_ms}ms`;
  return JSON.stringify(payload).slice(0, 100);
}

function render(evt) {
  if (state.paused) return;
  if (state.filter && !evt.stage.includes(state.filter)) return;
  const tab = tabFor(evt.stage);
  const list = document.getElementById('list-' + tab);
  if (!list) return;

  const li = document.createElement('li');
  const stageCls = evt.stage.endsWith('.fail') ? 'stage fail' : 'stage';
  li.innerHTML = `
    <details>
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
  list.insertBefore(li, list.firstChild);

  while (list.children.length > MAX_PER_TAB) {
    list.removeChild(list.lastChild);
  }

  counts[tab] = (counts[tab] || 0) + 1;
  const cnt = document.getElementById('count-' + tab);
  if (cnt) cnt.textContent = counts[tab];
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

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.event-list').forEach(l => l.classList.add('hidden'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    document.getElementById('list-' + tab).classList.remove('hidden');
    state.activeTab = tab;
  });
});

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
    document.getElementById('count-' + k).textContent = 0;
  }
});
