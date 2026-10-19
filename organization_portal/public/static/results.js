import { cell, orgPath } from './api.js';

export function text(tag, value, className = '') {
  const element = document.createElement(tag);
  element.textContent = value;
  element.className = className;
  return element;
}

function table(rows) {
  const wrapper = document.createElement('div');
  wrapper.className = 'table-wrap';
  const element = document.createElement('table');
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
  const header = document.createElement('tr');
  for (const column of columns) header.append(text('th', column));
  element.append(header);
  for (const row of rows.slice(0, 100)) {
    const tr = document.createElement('tr');
    for (const column of columns) cell(tr, typeof row[column] === 'object' ? JSON.stringify(row[column]) : row[column]);
    element.append(tr);
  }
  wrapper.append(element);
  return wrapper;
}

export function renderTurns(target, turns, chatId, readOnly = false) {
  target.replaceChildren();
  for (const turn of turns) {
    const question = text('article', '', 'bubble question');
    question.append(text('div', readOnly ? 'عضو سازمان' : 'شما', 'speaker'), text('p', turn.question));
    const response = text('article', '', 'bubble answer-body');
    response.append(text('div', 'رصام', 'speaker'));
    const answer = turn.answer;
    if (!answer) response.append(text('p', 'این درخواست هنوز در حال آماده‌شدن است.'));
    else {
      response.append(text('p', answer.error || answer.message || answer.summary || 'نتیجهٔ درخواست آماده است.', answer.error ? 'error' : ''));
      if (turn.status === 'failed' && !answer.error) {
        response.append(text('p', 'پاسخ در همهٔ بخش‌های لازم کامل نشد؛ سهمیه کم نشده است.', 'error'));
      }
      if (answer.rows?.length) response.append(table(answer.rows));
      if (answer.chart) chart(response, answer.chart, answer.rows || []);
      if (answer.rows?.length && !answer.error && !readOnly) response.append(downloads(chatId, turn.id));
    }
    target.append(question, response);
  }
}

function downloads(chatId, turnId) {
  const actions = text('div', '', 'result-actions');
  for (const [kind, label] of [['csv', 'دریافت CSV'], ['excel', 'دریافت Excel']]) {
    const link = text('a', label);
    link.href = '/api' + orgPath('/chats/' + chatId + '/turns/' + turnId + '/export/' + kind);
    actions.append(link);
  }
  return actions;
}

function chart(target, spec, rows) {
  if (!globalThis.Plotly || !rows.length || !['line', 'bar', 'scatter', 'area'].includes(spec.chart_type)) return;
  const container = text('div', '', 'chart');
  target.append(container);
  const yColumns = Array.isArray(spec.y) ? spec.y : [spec.y];
  const traces = yColumns.map(column => ({
    x: rows.map((row, index) => spec.x ? row[spec.x] : index + 1), y: rows.map(row => row[column]),
    name: String(column).replace(/[<>]/g, ''),
    type: spec.chart_type === 'bar' ? 'bar' : 'scatter', mode: spec.chart_type === 'scatter' ? 'markers' : 'lines',
    fill: spec.chart_type === 'area' ? 'tozeroy' : undefined
  }));
  globalThis.Plotly.newPlot(container, traces, {
    title: { text: String(spec.title || '').replace(/[<>]/g, '') },
    font: { family: 'Vazirmatn' }, margin: { t: 50, l: 55, r: 20, b: 45 }, paper_bgcolor: 'transparent'
  }, { responsive: true, displaylogo: false, displayModeBar: false });
}
