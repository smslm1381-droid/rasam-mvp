import { $, api, guard, notify, orgPath } from './api.js';

function values() {
  return { db_type: $('db-type').value, values: {
    host: $('db-host').value, port: $('db-port').value, database: $('db-name').value,
    username: $('db-user').value, password: $('db-password').value
  }, advanced_uri: $('db-uri').value, ca_pem: $('db-ca').value,
  sources: [...$('sources-list').querySelectorAll('input:checked')].map(input => input.value),
  documentation: $('db-documentation').value };
}

async function current() {
  const result = await api(orgPath('/connection'));
  $('connection-current').textContent = result
    ? 'اتصال فعلی: ' + result.db_type + ' · ' + result.database_name + ' — ویرایش اتصال نیازمند ورود دوبارهٔ رمز است.'
    : 'اتصال سازمان هنوز تنظیم نشده است.';
  $('db-documentation').value = result?.documentation || '';
  $('sources-list').replaceChildren();
  $('sources-list').hidden = true;
  $('save-connection').disabled = true;
  $('db-password').value = '';
  $('db-uri').value = '';
}

$('probe-connection').addEventListener('click', guard(async () => {
  $('probe-connection').disabled = true;
  $('save-connection').disabled = true;
  $('connection-status').textContent = 'در حال بررسی مسیر، گواهی و دسترسی فقط‌خواندنی…';
  try {
    const result = await api(orgPath('/connection/test'), { method: 'POST', body: values() });
    $('connection-status').textContent = result.message;
    $('sources-list').replaceChildren();
    $('sources-list').hidden = !result.ok;
    if (!result.ok) return;
    for (const source of result.sources) {
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = source;
      label.className = 'check';
      label.append(input, document.createTextNode(source));
      $('sources-list').append(label);
    }
    $('save-connection').disabled = false;
  } finally { $('probe-connection').disabled = false; }
}));

$('connection-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  $('save-connection').disabled = true;
  try {
    const result = await api(orgPath('/connection'), { method: 'PUT', body: values() });
    if (!result.ok) throw new Error(result.message);
    notify(result.message);
    await current();
  } finally { $('save-connection').disabled = false; }
  if ($('sources-list').hidden) $('save-connection').disabled = true;
}));
$('db-type').addEventListener('change', () => { $('db-port').value = $('db-type').value === 'mysql' ? '3306' : '27017'; });
document.addEventListener('portal-view', guard(async event => { if (event.detail === 'connection') await current(); }));
