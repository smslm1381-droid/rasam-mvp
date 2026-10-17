function showLicenseSupport(url) {
  $('license-support').hidden = !url;
  if (url) $('license-support').href = url;
}

function displayLicense(data) {
  licenseReady = !data.required || data.valid;
  if (!licenseReady) $('connection-status').textContent = 'در انتظار تأیید لایسنس';
  $('activation').hidden = !data.required || data.valid;
  $('workspace').hidden = !!data.required && !data.valid;
  $('license-banner').hidden = !data.required || !data.valid;
  $('license-message').textContent = data.message || '';
  showLicenseSupport(data.support_url);
  if (!data.required || !data.valid) return;
  const expiry = new Date(data.expires_at * 1000).toLocaleDateString('fa-IR');
  const days = data.days_remaining.toLocaleString('fa-IR');
  $('license-description').textContent = `${data.customer} · اعتبار تا ${expiry} · ${days} روز باقی مانده`;
  $('license-banner').classList.toggle('license-warning', data.days_remaining <= 7);
  if (data.days_remaining <= 7) $('license-description').textContent += ' · برای تمدید با پشتیبانی تماس بگیرید.';
}

async function refreshLicense() {
  for (const button of document.querySelectorAll('[data-license-refresh]')) button.disabled = true;
  try {
    const data = await (await request('/license/status')).json();
    displayLicense(data);
    if (data.valid) await refreshStatus();
  } catch (error) { $('license-message').textContent = error.message; }
  finally { for (const button of document.querySelectorAll('[data-license-refresh]')) button.disabled = false; }
}

async function activateLicense(event) {
  event.preventDefault();
  $('license-activate').disabled = true;
  $('license-message').textContent = 'در حال بررسی کد لایسنس…';
  try {
    const data = await (await request('/license/activate', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: $('license-key').value }) })).json();
    if (!data.ok) {
      $('license-message').textContent = data.message;
      showLicenseSupport(data.support_url);
      return;
    }
    $('license-key').value = '';
    displayLicense(data);
    await refreshStatus();
  } catch (error) { $('license-message').textContent = error.message; }
  finally { $('license-activate').disabled = false; }
}

$('license-form').addEventListener('submit', activateLicense);
for (const button of document.querySelectorAll('[data-license-refresh]')) button.addEventListener('click', refreshLicense);
refreshLicense();
