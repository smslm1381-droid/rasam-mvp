// حساب فقط روی همین دستگاه است؛ لایسنس و اتصال موجود هنگام ساخت حساب حفظ می‌شوند.
let accountState = { required: true, registered: false, authenticated: false };

function showAccount() {
  $('account').hidden = false;
  $('activation').hidden = true;
  $('workspace').hidden = true;
  $('license-banner').hidden = true;
  $('account-title').textContent = accountState.registered ? 'ورود به رصام' : 'حساب این دستگاه را بسازید';
  $('account-submit').textContent = accountState.registered ? 'ورود' : 'ساخت حساب و ورود';
  $('account-password').autocomplete = accountState.registered ? 'current-password' : 'new-password';
  $('account-confirm-wrap').hidden = accountState.registered;
  $('account-confirm').required = !accountState.registered;
  $('connection-status').textContent = 'در انتظار ورود به حساب';
}

async function refreshAccount() {
  try {
    accountState = await (await request('/auth/status')).json();
    if (accountState.error) throw new Error(accountState.error);
    if (accountState.required && !accountState.authenticated && accountState.registered) showAccount();
    else await refreshLicense();
  } catch (error) {
    $('workspace').hidden = true;
    $('activation').hidden = true;
    $('account').hidden = false;
    $('account-message').textContent = error.message;
  }
}

$('account-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!accountState.registered && $('account-password').value !== $('account-confirm').value) {
    $('account-message').textContent = 'تکرار رمز با رمز عبور یکسان نیست.';
    return;
  }
  $('account-submit').disabled = true;
  try {
    await request(accountState.registered ? '/auth/login' : '/auth/register', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        username: $('account-username').value, password: $('account-password').value }) });
    $('account-password').value = '';
    $('account-confirm').value = '';
    $('account-message').textContent = '';
    $('account').hidden = true;
    await refreshAccount();
    await refreshUpdates();
  } catch (error) { $('account-message').textContent = error.message; }
  finally { $('account-submit').disabled = false; }
});

$('account-logout').addEventListener('click', async () => {
  try {
    await request('/auth/logout', { method: 'POST' });
    location.reload();
  } catch (error) { notice(error.message, true); }
});
