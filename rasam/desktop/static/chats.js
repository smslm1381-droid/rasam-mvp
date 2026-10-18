'use strict';
let activeChat = null;
let chatCustomer = null;
let chatBusy = false;
let savedChats = [];

function clearChat() {
  activeChat = null;
  answerId = null;
  $('conversation').replaceChildren();
  $('result').hidden = true;
  if ($('result-dialog').open) $('result-dialog').close();
  $('empty').hidden = false;
  $('chat-scroll').scrollTop = 0;
  $('chat-title').textContent = 'گفتگوی جدید';
  $('question').value = '';
  resizeComposer();
  notice('');
}

function chatControls(busy) {
  chatBusy = busy;
  for (const button of $('chat-tools').querySelectorAll('button')) button.disabled = busy;
  for (const button of $('chat-list').querySelectorAll('button')) button.disabled = busy;
  $('chat-delete').disabled = busy;
  for (const button of $('conversation').querySelectorAll('button')) button.disabled = busy;
  $('chat-pending').hidden = !busy;
  if (!busy) $('pending-question')?.remove();
}

function userBubble(text) {
  const bubble = document.createElement('div');
  bubble.className = 'user-message';
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  bubble.append(paragraph);
  return bubble;
}

function showPendingQuestion(question) {
  const pending = document.createElement('article');
  pending.id = 'pending-question';
  pending.className = 'chat-turn';
  pending.append(userBubble(question));
  $('conversation').append(pending);
  $('empty').hidden = true;
  scrollChat();
}

function messageDetails(turn, index) {
  const actions = document.createElement('div');
  actions.className = 'message-actions';
  const details = document.createElement('button');
  details.type = 'button';
  details.disabled = chatBusy;
  details.textContent = turn.answer.rows.length || turn.answer.chart
    ? `نمایش جدول و خروجی‌ها · ${turn.answer.rows.length.toLocaleString('fa-IR')} ردیف`
    : 'بازخورد به پاسخ';
  details.addEventListener('click', () => {
    answerId = turn.id;
    if (!$('result-dialog').open) $('result-dialog').showModal();
    showAnswer(turn.answer);
    $('feedback-positive').hidden ||= index > 0;
  });
  actions.append(details);
  return actions;
}

function assistantBubble(turn, index) {
  const message = document.createElement('div');
  message.className = 'assistant-message';
  const avatar = document.createElement('img');
  avatar.src = '/static/mark.svg';
  avatar.alt = '';
  avatar.className = 'assistant-avatar';
  const body = document.createElement('div');
  body.className = 'assistant-body';
  const meta = document.createElement('div');
  meta.className = 'message-meta';
  meta.textContent = 'رصام';
  if (turn.created) {
    const time = document.createElement('time');
    time.dateTime = turn.created;
    time.textContent = new Date(turn.created).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
    meta.append(time);
  }
  const reply = document.createElement('p');
  reply.textContent = turn.answer.error || turn.answer.message || turn.answer.summary ||
    (turn.answer.rows.length ? 'این نتیجه را از داده‌های شما پیدا کردم.' : 'داده‌ای برای این سؤال پیدا نشد.');
  if (turn.answer.error) body.classList.add('message-error');
  body.append(meta, reply);
  if (!turn.answer.error) body.append(messageDetails(turn, index));
  message.append(avatar, body);
  return message;
}

function drawTurns(turns) {
  $('conversation').replaceChildren();
  turns.forEach((turn, index) => {
    const card = document.createElement('article');
    card.className = 'chat-turn';
    card.append(userBubble(turn.answer.question), assistantBubble(turn, index));
    $('conversation').append(card);
  });
  $('empty').hidden = !!turns.length;
}

async function loadChat(id, afterAsk = false) {
  if (chatBusy && !afterAsk) return;
  const data = await (await request(`/chats/${id}`)).json();
  activeChat = data.id;
  $('chat-title').textContent = data.title;
  drawTurns(data.turns);
  answerId = data.turns.at(-1)?.id || null;
  $('result').hidden = true;
  notice('');
  await refreshChats();
  closeHistory();
  scrollChat();
}

function drawHistory() {
  const search = $('chat-search').value.trim().toLocaleLowerCase();
  const chats = savedChats.filter((chat) => chat.title.toLocaleLowerCase().includes(search));
  $('chat-list').replaceChildren();
  $('chat-count').textContent = savedChats.length.toLocaleString('fa-IR');
  for (const chat of chats) {
    const button = document.createElement('button');
    button.type = 'button';
    const icon = document.createElement('span');
    icon.className = 'rasam-icon icon-ask';
    icon.setAttribute('aria-hidden', 'true');
    const title = document.createElement('span');
    title.textContent = chat.title;
    button.append(icon, title);
    button.title = chat.title;
    button.setAttribute('aria-pressed', String(chat.id === activeChat));
    button.disabled = chatBusy;
    button.addEventListener('click', () => loadChat(chat.id).catch((error) => notice(error.message, true)));
    $('chat-list').append(button);
  }
  if (!chats.length) {
    const empty = document.createElement('p');
    empty.className = 'history-empty';
    empty.textContent = search ? 'گفتگویی پیدا نشد.' : 'اولین گفتگوی شما از همین‌جا شروع می‌شود.';
    $('chat-list').append(empty);
  }
  $('chat-delete').hidden = !activeChat;
}

async function refreshChats() {
  savedChats = await (await request('/chats')).json();
  drawHistory();
  return savedChats;
}

async function syncChats(customer) {
  if (customer === chatCustomer) return;
  chatCustomer = customer;
  clearChat();
  if (!customer) return;
  const chats = await refreshChats();
  if (chats.length) await loadChat(chats[0].id);
}

async function ensureChat() {
  if (activeChat) return activeChat;
  const created = await (await request('/chats', { method: 'POST' })).json();
  activeChat = created.id;
  return activeChat;
}

$('chat-search').addEventListener('input', drawHistory);
$('chat-new').addEventListener('click', () => {
  if (chatBusy) return;
  clearChat();
  $('chat-search').value = '';
  closeHistory();
  refreshChats().catch((error) => notice(error.message, true));
  $('question').focus();
});
$('chat-delete').addEventListener('click', async () => {
  if (chatBusy || !activeChat || !confirm('این گفتگو و پاسخ‌های ذخیره‌شدهٔ آن حذف شود؟')) return;
  try {
    await request(`/chats/${activeChat}`, { method: 'DELETE' });
    clearChat();
    await refreshChats();
  } catch (error) { notice(error.message, true); }
});
