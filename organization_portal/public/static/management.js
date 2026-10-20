import { $, api, button, cell, faNumber, guard, lines, notify, orgPath, state } from './api.js';
import { renderTurns, text } from './results.js';

let selectedMember;
let selectedOrganization;

function drawTable(target, headings, rows) {
  const table = document.createElement('table');
  const header = document.createElement('tr');
  for (const title of headings) header.append(text('th', title));
  table.append(header);
  for (const values of rows) {
    const row = document.createElement('tr');
    for (const value of values) cell(row, value);
    table.append(row);
  }
  target.replaceChildren(table);
}

export function showInvite(result) {
  $('invite-url').value = location.origin + '/?invite=' + encodeURIComponent(result.token);
  $('invite-result').showModal();
}

async function members() {
  const result = await api(orgPath('/members'));
  drawTable($('members-table'), ['نام', 'ایمیل', 'نقش', 'وضعیت', 'سقف روزانه', 'مصرف امروز', 'در حال اجرا', 'منابع مجاز', ''], result.map(member => [
    member.name, member.email, member.role === 'admin' ? 'مدیر سازمان' : 'عضو', member.active ? 'فعال' : 'غیرفعال',
    faNumber(member.daily_limit), faNumber(member.used), faNumber(member.reserved),
    JSON.parse(member.allowed_sources).join('، '), button('ویرایش', () => editMember(member))
  ]));
}

function editMember(member) {
  selectedMember = member;
  $('edit-member-name').textContent = member.name + ' · ' + member.email;
  $('edit-member-active').value = member.active ? '1' : '0';
  $('edit-member-limit').value = member.daily_limit;
  $('edit-member-sources').value = JSON.parse(member.allowed_sources).join('\n');
  $('edit-member').showModal();
}

$('edit-member-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  await api(orgPath('/members/' + selectedMember.id), { method: 'PATCH', body: {
    active: $('edit-member-active').value === '1', daily_limit: Number($('edit-member-limit').value),
    sources: lines($('edit-member-sources').value)
  } });
  $('edit-member').close();
  await members();
  notify('دسترسی عضو به‌روز شد.');
}));

$('member-invite-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  const result = await api(orgPath('/invitations'), { method: 'POST', body: {
    email: $('member-email').value, role: $('member-role').value,
    daily_limit: Number($('member-limit').value), sources: lines($('member-sources').value)
  } });
  showInvite(result);
}));

async function organizations() {
  const result = await api('/platform/organizations');
  drawTable($('organizations-table'), ['سازمان', 'وضعیت', 'سقف روزانه', 'مشاهدهٔ گفتگو توسط مدیر', ''], result.map(org => [
    org.name, org.active ? 'فعال' : 'غیرفعال', faNumber(org.daily_limit), org.manager_chat_access ? 'فعال' : 'غیرفعال',
    button('سیاست سازمان', () => editOrganization(org))
  ]));
}

function editOrganization(org) {
  selectedOrganization = org;
  $('edit-organization-name').textContent = org.name;
  $('edit-organization-active').value = org.active ? '1' : '0';
  $('edit-organization-limit').value = org.daily_limit;
  $('edit-organization-hosts').value = JSON.parse(org.allowed_hosts).join('\n');
  $('edit-organization-visibility').checked = Boolean(org.manager_chat_access);
  $('edit-organization').showModal();
}

$('edit-organization-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  await api('/platform/organizations/' + selectedOrganization.id, { method: 'PATCH', body: {
    active: $('edit-organization-active').value === '1', daily_limit: Number($('edit-organization-limit').value),
    hosts: lines($('edit-organization-hosts').value), manager_chat_access: $('edit-organization-visibility').checked
  } });
  $('edit-organization').close();
  await organizations();
  notify('سیاست سازمان به‌روز شد؛ تغییر مجوز از سمت سرور اعمال می‌شود.');
}));

$('organization-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  const result = await api('/platform/organizations', { method: 'POST', body: {
    name: $('organization-name').value, manager_email: $('organization-manager').value,
    daily_limit: Number($('organization-limit').value), hosts: lines($('organization-hosts').value)
  } });
  showInvite(result.invitation);
  await organizations();
}));

async function managed() {
  const result = await api(orgPath('/managed-chats'));
  $('managed-list').replaceChildren();
  $('managed-messages').replaceChildren();
  if (!result.length) $('managed-list').append(text('p', 'گفتگویی در دسترسی فعلی وجود ندارد.'));
  for (const chat of result) {
    $('managed-list').append(button(chat.name + ' · ' + chat.title, async () => {
      const response = await api(orgPath('/managed-chats/' + chat.id));
      renderTurns($('managed-messages'), response.turns, chat.id, true);
    }));
  }
}

$('copy-invite').addEventListener('click', guard(async () => {
  await navigator.clipboard.writeText($('invite-url').value);
  notify('پیوند دعوت کپی شد؛ فقط خصوصی ارسالش کنید.');
}));
$('close-invite').addEventListener('click', () => { $('invite-url').value = ''; $('invite-result').close(); });
$('close-member').addEventListener('click', () => $('edit-member').close());
$('close-organization').addEventListener('click', () => $('edit-organization').close());
$('refresh-members').addEventListener('click', guard(members));
document.addEventListener('portal-view', guard(async event => {
  if (event.detail === 'members') await members();
  if (event.detail === 'platform') await organizations();
  if (event.detail === 'managed') await managed();
}));
