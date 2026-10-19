import { $, api, button, faNumber, guard, notify, orgPath, state } from './api.js';
import { renderTurns, text } from './results.js';
import { showView } from './session.js';

export async function listChats() {
  $('chat-list').replaceChildren();
  if (!state.org) return;
  const chats = await api(orgPath('/chats'));
  for (const chat of chats) {
    const item = button(chat.title, async () => { showView('chat'); await openChat(chat.id); }, 'chat-item');
    item.classList.toggle('selected', chat.id === state.chat);
    $('chat-list').append(item);
  }
  await usage();
}

async function usage() {
  const value = await api(orgPath('/usage'));
  $('usage-label').textContent = 'پاسخ موفق امروز: ' + faNumber(value.member.used) + ' از ' + faNumber(value.member_limit);
}

async function openChat(id) {
  const chat = await api(orgPath('/chats/' + id));
  state.chat = id;
  renderTurns($('messages'), chat.turns, id);
  $('question-status').textContent = chat.busy_turn_id ? 'پاسخ قبلی در حال آماده‌شدن است؛ دوباره درخواست تازه ارسال نکنید.' : '';
  await listChats();
}

async function newChat() {
  const chat = await api(orgPath('/chats'), { method: 'POST' });
  state.chat = chat.id;
  state.pending = null;
  $('messages').replaceChildren(text('p', 'گفتگوی تازه آماده است؛ سؤال خود را بنویسید.', 'muted'));
  $('retry-question').hidden = true;
  await listChats();
  $('question').focus();
}

async function sendQuestion(retry = false) {
  if (!retry) {
    if (!state.chat) await newChat();
    state.pending = { chat: state.chat, request_id: crypto.randomUUID(), question: $('question').value.trim() };
  }
  const pending = state.pending;
  if (!pending?.question) return;
  $('send').disabled = true;
  $('org-select').disabled = true;
  $('new-chat').disabled = true;
  $('delete-chat').disabled = true;
  $('retry-question').hidden = true;
  $('question-status').textContent = 'در حال آماده‌سازی پاسخ… میزبان آزمایشی ممکن است برای شروع زمان بیشتری نیاز داشته باشد.';
  try {
    await api(orgPath('/chats/' + pending.chat + '/ask'), { method: 'POST', body: pending });
    state.pending = null;
    $('question').value = '';
    await openChat(pending.chat);
  } catch (error) {
    $('question-status').textContent = error.message;
    $('retry-question').hidden = false;
  } finally {
    $('send').disabled = false;
    $('org-select').disabled = false;
    $('new-chat').disabled = false;
    $('delete-chat').disabled = false;
  }
}

$('question-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  if (state.pending) return notify('ابتدا وضعیت درخواست قبلی را با دکمهٔ بررسی دوباره مشخص کنید.');
  await sendQuestion();
}));
$('retry-question').addEventListener('click', guard(() => sendQuestion(true)));
$('new-chat').addEventListener('click', guard(newChat));
$('refresh-chat').addEventListener('click', guard(async () => { if (state.chat) await openChat(state.chat); else await listChats(); }));
$('delete-chat').addEventListener('click', guard(async () => {
  if (!state.chat || !confirm('این گفتگو و پیام‌هایش حذف شوند؟')) return;
  await api(orgPath('/chats/' + state.chat), { method: 'DELETE' });
  state.chat = null;
  $('messages').replaceChildren(text('p', 'گفتگو حذف شد.', 'muted'));
  await listChats();
}));
document.addEventListener('portal-organization', guard(async () => {
  $('messages').replaceChildren(text('p', 'گفتگوی تازه بسازید یا یکی از گفتگوهای خود را باز کنید.', 'muted'));
  $('retry-question').hidden = true;
  try { await listChats(); } catch (error) { $('messages').replaceChildren(text('p', error.message, 'muted')); }
}));
