'use strict';
const $ = (id) => document.getElementById(id);
const initialToken = new URL(location.href).searchParams.get('token');
if (initialToken) {
  sessionStorage.setItem('rasam-token', initialToken);
  history.replaceState(null, '', '/');
}
const token = sessionStorage.getItem('rasam-token') || '';
let answerId = null;
let capabilities = [];

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'X-Rasam-Token': token, ...options.headers },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'انجام درخواست ممکن نشد؛ دوباره تلاش کنید.');
  }
  return response;
}

function notice(text, error = false) {
  $('notice').textContent = text;
  $('notice').classList.toggle('error', error);
  $('notice').hidden = !text;
}

function cellText(value) {
  if (value == null) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function showTable(rows) {
  const wrap = $('table');
  wrap.replaceChildren();
  wrap.hidden = !rows.length;
  if (!rows.length) return;
  const columns = [...new Set(rows.flatMap(Object.keys))]
    .filter((key) => key !== '_id' || rows.some((row) => row[key] != null));
  const table = document.createElement('table');
  const head = table.createTHead().insertRow();
  for (const key of columns) {
    const cell = document.createElement('th');
    cell.textContent = key;
    head.append(cell);
  }
  const body = table.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    for (const key of columns) {
      const value = row[key];
      tr.insertCell().textContent = cellText(value);
    }
  }
  wrap.append(table);
}

function chartLabel(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function xValues(chart, rows) {
  if (!chart.x) return rows.map((_, index) => index + 1);
  return rows.map((row) => {
    const value = row[chart.x];
    return typeof value === 'string' ? chartLabel(value) : value;
  });
}

function showChart(chart, rows) {
  const target = $('chart');
  target.hidden = !chart;
  if (!chart) {
    if (target.data) Plotly.purge(target);
    return;
  }
  const traces = chart.y.map((key) => ({
    x: xValues(chart, rows),
    y: rows.map((row) => row[key]),
    name: chartLabel(key),
    type: chart.chart_type === 'bar' ? 'bar' : 'scatter',
    mode: chart.chart_type === 'scatter' ? 'markers' : 'lines+markers',
    ...(chart.chart_type === 'area' ? { fill: 'tozeroy' } : {}),
  }));
  Plotly.react(target, traces, {
    title: { text: chartLabel(chart.title) },
    font: { family: 'Vazirmatn' },
    margin: { t: 65, r: 30, l: 60, b: 70 },
    paper_bgcolor: 'white', plot_bgcolor: '#fafcfc',
    colorway: ['#176e70', '#dda35d', '#5d91b4', '#9e759e'],
  }, { responsive: true, displaylogo: false, displayModeBar: false });
}

function showAnswer(answer) {
  $('empty').hidden = true;
  $('result').hidden = !!answer.error;
  notice(answer.error || '', !!answer.error);
  if (answer.error) return;
  $('summary').textContent = answer.summary || '';
  $('message').textContent = answer.message || (!answer.rows.length ? 'هیچ ردیفی برای این سؤال پیدا نشد.' : '');
  showTable(answer.rows);
  showChart(answer.chart, answer.rows);
  $('row-count').textContent = answer.rows.length ? `${answer.rows.length.toLocaleString('fa-IR')} ردیف` : '';
  for (const button of document.querySelectorAll('[data-export]')) {
    const capability = button.dataset.export === 'csv' ? 'export_csv' : 'export_excel';
    button.hidden = !answer.rows.length || !capabilities.includes(capability);
  }
}

$('ask-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('ask-button').disabled = true;
  $('ask-button').textContent = 'در حال بررسی داده‌ها…';
  notice('');
  try {
    const response = await request('/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: $('question').value }) });
    answerId = response.headers.get('X-Answer-ID');
    showAnswer(await response.json());
  } catch (error) {
    notice(error instanceof TypeError ? 'ارتباط با برنامه قطع شد؛ رصام را دوباره باز کنید.' : error.message, true);
  } finally {
    $('ask-button').disabled = false;
    $('ask-button').textContent = 'پرسیدن سؤال ←';
  }
});

for (const button of document.querySelectorAll('[data-export]')) {
  button.addEventListener('click', async () => {
    try {
      const kind = button.dataset.export;
      const response = await request(`/export/${answerId}/${kind}`);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = kind === 'csv' ? 'result.csv' : 'result.xlsx';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { notice(error.message, true); }
  });
}

async function refreshStatus() {
  const data = await (await request('/status')).json();
  capabilities = data.capabilities;
  $('qa').hidden = !data.configured;
  $('connection-status').textContent = data.configured ? `آمادهٔ پرسش · ${data.customer}` : 'اتصال دیتابیس هنوز تنظیم نشده';
  if (!data.configured) notice('ابتدا اتصال دیتابیس را تنظیم کنید.');
}
refreshStatus().catch((error) => notice(error.message, true));
