import { $, api, guard, state } from './api.js';

const titles = { chat: 'گفتگو با داده‌ها', members: 'اعضای سازمان', connection: 'اتصال و آموزش داده', managed: 'گفتگوهای اعضا', platform: 'مدیریت کل رصام', account: 'تنظیمات حساب' };

export function showView(view) {
  if (!titles[view]) return;
  if (['members', 'connection', 'managed'].includes(view) && state.org?.role !== 'admin') return;
  if (view === 'managed' && !state.org?.manager_chat_access) return;
  if (view === 'platform' && !state.user?.platform_admin) return;
  state.view = view;
  document.querySelectorAll('.view').forEach(element => { element.hidden = element.id !== 'view-' + view; });
  document.querySelectorAll('[data-view]').forEach(element => element.classList.toggle('active', element.dataset.view === view));
  $('view-title').textContent = titles[view];
  document.dispatchEvent(new CustomEvent('portal-view', { detail: view }));
}

export function selectOrganization(id) {
  state.org = state.organizations.find(org => org.id === id) || null;
  state.chat = null;
  state.pending = null;
  $('org-title').textContent = state.org?.name || 'هنوز عضو سازمانی نیستید';
  document.querySelectorAll('.manager-only').forEach(item => { item.hidden = state.org?.role !== 'admin'; });
  document.querySelectorAll('.visibility-only').forEach(item => { item.hidden = state.org?.role !== 'admin' || !state.org.manager_chat_access; });
  $('privacy-note').textContent = state.org?.manager_chat_access
    ? 'دسترسی مشاهدهٔ متن گفتگوها برای مدیر این سازمان فعال است؛ مشاهدهٔ نظارتی ثبت می‌شود.'
    : 'دسترسی مشاهدهٔ متن گفتگوها برای مدیر سازمان فعال نیست.';
  if (state.demo) $('privacy-note').textContent = 'محیط تست با حساب و پاسخ ساختگی؛ دیتابیس و API مدل واقعی استفاده نمی‌شوند.';
  document.dispatchEvent(new Event('portal-organization'));
  showView(state.org ? 'chat' : state.user?.platform_admin ? 'platform' : 'account');
}

export async function refreshSession() {
  const result = await api('/auth/status');
  Object.assign(state, { user: result.user, csrf: result.csrf, organizations: result.organizations, demo: result.demo });
  $('login-view').hidden = Boolean(state.user);
  $('workspace').hidden = !state.user;
  if (!state.user) return;
  $('user-name').textContent = state.user.name;
  document.querySelectorAll('.platform-only').forEach(item => { item.hidden = !state.user.platform_admin; });
  $('org-select').replaceChildren();
  for (const org of state.organizations) {
    const option = document.createElement('option');
    option.value = org.id;
    option.textContent = org.name;
    $('org-select').append(option);
  }
  $('org-select').disabled = !state.organizations.length;
  selectOrganization(state.organizations[0]?.id || '');
  if (result.demo) $('privacy-note').textContent = 'محیط تست با حساب و پاسخ ساختگی؛ دیتابیس و API مدل واقعی استفاده نمی‌شوند.';
}

document.querySelectorAll('[data-view]').forEach(element => {
  element.addEventListener('click', () => showView(element.dataset.view));
});
$('org-select').addEventListener('change', () => selectOrganization($('org-select').value));
$('logout').addEventListener('click', guard(async () => {
  await api('/auth/logout', { method: 'POST' });
  state.csrf = '';
  await refreshSession();
}));
