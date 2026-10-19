export const $ = id => document.getElementById(id);
export const state = { user: null, csrf: '', organizations: [], org: null, chat: null, pending: null, view: 'chat', invitation: '' };

export async function api(path, options = {}) {
  const headers = { ...options.headers };
  if (state.csrf) headers['X-CSRF-Token'] = state.csrf;
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch('/api' + path, {
    ...options, headers, credentials: 'same-origin',
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });
  let body;
  try { body = await response.json(); }
  catch { throw new Error('پاسخ سرور آماده نیست؛ کمی بعد دوباره تلاش کنید.'); }
  if (!response.ok) throw new Error(body.detail || body.error || 'عملیات کامل نشد.');
  return body;
}

let noticeTimer;
export function notify(message) {
  $('notice').textContent = message;
  $('notice').hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { $('notice').hidden = true; }, 7000);
}

export function guard(action) {
  return async event => {
    try { await action(event); }
    catch (error) { notify(error instanceof TypeError ? 'ارتباط با سرور قطع شد؛ دوباره تلاش کنید.' : error.message); }
  };
}

export function orgPath(suffix) {
  if (!state.org) throw new Error('ابتدا یک سازمان انتخاب کنید.');
  return '/organizations/' + encodeURIComponent(state.org.id) + suffix;
}

export const lines = value => value.split('\n').map(item => item.trim()).filter(Boolean);
export const faNumber = value => new Intl.NumberFormat('fa-IR').format(value);

export function button(text, action, className = 'secondary compact') {
  const element = document.createElement('button');
  element.type = 'button';
  element.textContent = text;
  element.className = className;
  element.addEventListener('click', guard(action));
  return element;
}

export function cell(row, value) {
  const element = document.createElement('td');
  if (value instanceof Node) element.append(value);
  else element.textContent = String(value ?? '');
  row.append(element);
}
