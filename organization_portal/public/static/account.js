import { $, api, guard, notify, state } from './api.js';
import { refreshSession } from './session.js';

$('login-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  const submit = event.target.querySelector('button');
  submit.disabled = true;
  $('login-message').textContent = '';
  try {
    await api('/auth/login', { method: 'POST', body: { email: $('login-email').value, password: $('login-password').value } });
    $('login-password').value = '';
    await refreshSession();
    if (state.invitation) await showInvitation();
  } catch (error) { $('login-message').textContent = error.message; }
  finally { submit.disabled = false; }
}));

export async function showInvitation() {
  if (!state.invitation) return;
  try {
    const invitation = await api('/invitations/' + encodeURIComponent(state.invitation));
    $('login-email').value = invitation.email;
    $('invitation-info').textContent = invitation.email + ' · ' + invitation.organization;
    const needsLogin = invitation.existing_account && state.user?.email !== invitation.email;
    for (const name of ['name', 'password', 'confirm']) {
      $('invite-' + name + '-wrap').hidden = invitation.existing_account;
      $('invite-' + name).required = !invitation.existing_account;
    }
    $('invitation-login').hidden = !needsLogin;
    $('invitation-form').hidden = needsLogin;
    $('invitation-view').hidden = false;
    $('login-view').hidden = true;
    $('workspace').hidden = true;
  } catch (error) {
    $('invitation-message').textContent = error.message;
    $('invitation-view').hidden = false;
  }
}

$('invitation-login').addEventListener('click', () => {
  $('invitation-view').hidden = true;
  $('login-view').hidden = false;
});

$('invitation-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  if ($('invite-password').value !== $('invite-confirm').value) throw new Error('تکرار رمز یکسان نیست.');
  await api('/invitations/accept', { method: 'POST', body: {
    token: state.invitation, name: $('invite-name').value, password: $('invite-password').value
  } });
  $('invitation-form').reset();
  state.invitation = '';
  $('invitation-view').hidden = true;
  notify('عضویت فعال شد؛ با حساب مرکزی خود وارد شوید.');
  await refreshSession();
}));

$('password-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  if ($('new-password').value !== $('confirm-password').value) throw new Error('تکرار رمز یکسان نیست.');
  await api('/auth/password', { method: 'POST', body: { old: $('old-password').value, new: $('new-password').value } });
  event.target.reset();
  state.csrf = '';
  await refreshSession();
  notify('رمز تغییر کرد؛ دوباره وارد شوید.');
}));
