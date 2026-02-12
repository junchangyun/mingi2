const message = document.getElementById('message');
const runningEl = document.getElementById('running');
const keyMaskEl = document.getElementById('key-mask');
const statusEl = document.getElementById('status');
const recentBody = document.getElementById('recent-body');

function setMessage(text) {
  if (message) message.textContent = text;
}

function renderRows(rows) {
  if (!recentBody) return;

  if (!rows || rows.length === 0) {
    recentBody.innerHTML = '<tr><td colspan="6">데이터 없음</td></tr>';
    return;
  }

  recentBody.innerHTML = rows
    .map((row) => {
      const time = row['거래시간'] || '-';
      const symbol = row['종목'] || '-';
      const side = row['포지션'] || '-';
      const pnl = row['손익금'] || '-';
      const roi = row['손익률'] || '-';
      const result = row['승패여부'] || '-';
      return `<tr><td>${time}</td><td>${symbol}</td><td>${side}</td><td>${pnl}</td><td>${roi}</td><td>${result}</td></tr>`;
    })
    .join('');
}

async function loadStatus() {
  try {
    const resp = await fetch('http://localhost:5000/status', { cache: 'no-store' });
    if (!resp.ok) {
      throw new Error(`status ${resp.status}`);
    }

    const data = await resp.json();

    if (runningEl) runningEl.textContent = data.running ? '실행 중' : '중지';
    if (keyMaskEl) keyMaskEl.textContent = data.key_mask || '-';
    if (statusEl) statusEl.textContent = data.status || '-';

    renderRows(data.recent || []);
    setMessage('백엔드 연결 정상');
  } catch (error) {
    if (runningEl) runningEl.textContent = '-';
    if (keyMaskEl) keyMaskEl.textContent = '-';
    if (statusEl) statusEl.textContent = '-';
    renderRows([]);
    setMessage('백엔드가 실행 중인지 확인하세요: cd bybit_web && python app.py');
  }
}

loadStatus();
setInterval(loadStatus, 5000);
