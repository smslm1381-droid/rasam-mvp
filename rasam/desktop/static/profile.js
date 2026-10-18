async function loadSources() {
  const result = await (await request('/setup/sources')).json();
  $('source-step').hidden = !result.ok;
  $('readonly-help').hidden = !result.script;
  $('source-list').replaceChildren();
  $('readiness').replaceChildren();
  if (!result.ok) {
    $('connection-result').textContent = result.message;
    $('readonly-script').textContent = result.script || '';
    return;
  }
  for (const source of result.sources) appendSource(source);
}

function appendSource(source) {
  const row = document.createElement('div');
  row.className = 'source-row';
  const label = document.createElement('label');
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.name = 'sources';
  input.value = source.name;
  label.append(input, document.createTextNode(source.name));
  row.append(label);
  if (source.sensitive) {
    const warning = document.createElement('label');
    const confirm = document.createElement('input');
    confirm.type = 'checkbox';
    confirm.name = 'confirmed_sensitive';
    confirm.value = source.name;
    warning.append(confirm, document.createTextNode('این نام حساس به نظر می‌رسد؛ تأیید می‌کنم که خواندن آن لازم است.'));
    row.append(warning);
  }
  $('source-list').append(row);
}

async function saveProfile(event) {
  event.preventDefault();
  $('profile-save').disabled = true;
  const form = new FormData($('profile-form'));
  try {
    const result = await (await request('/setup/profile', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: $('customer-name').value, sources: form.getAll('sources'),
        confirmed_sensitive: form.getAll('confirmed_sensitive') }) })).json();
    if (!result.ok) { $('connection-result').textContent = result.message; return; }
    $('source-step').hidden = true;
    $('connection-result').textContent = 'پروفایل ساخته شد؛ می‌توانید سؤال بپرسید.';
    $('readiness').replaceChildren();
    for (const check of result.checks) {
      const line = document.createElement('p');
      line.textContent = `${check.status === 'ok' ? '✅' : check.status === 'warning' ? '⚠️' : '❌'} ${check.name} — ${check.detail}`;
      $('readiness').append(line);
    }
    chatCustomer = null;
    await refreshStatus();
  } catch (error) { $('connection-result').textContent = error.message; }
  finally { $('profile-save').disabled = false; }
}

$('profile-form').addEventListener('submit', saveProfile);
$('copy-script').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText($('readonly-script').textContent); }
  catch { $('connection-result').textContent = 'کپی خودکار ممکن نشد؛ متن دستور را انتخاب و کپی کنید.'; }
});
