'use strict';
let activeChat = null;
let chatCustomer = null;
let chatBusy = false;

function clearChat() {
  activeChat = null;
  answerId = null;
  $('conversation').replaceChildren();
  $('result').hidden = true;
  $('empty').hidden = false;
  $('question').value = '';
}

function chatControls(busy) {
  chatBusy = busy;
  for (const button of $('chat-tools').querySelectorAll('button')) button.disabled = busy;
  for (const button of $('chat-list').querySelectorAll('button')) button.disabled = busy;
}

function drawTurns(turns) {
  $('conversation').replaceChildren();
  for (const turn of turns) {
    const card = document.createElement('article');
    card.className = 'chat-turn';
    const question = document.createElement('p');
    question.className = 'chat-question';
    question.textContent = turn.answer.question;
    const reply = document.createElement('p');
    reply.textContent = turn.answer.error || turn.answer.message || turn.answer.summary ||
      `${turn.answer.rows.length.toLocaleString('fa-IR')} ردیف داده دریافت شد.`;
    card.append(question, reply);
    if (!turn.answer.error) {
      const details = document.createElement('button');
      details.className = 'secondary';
      details.textContent = 'نمایش پاسخ و خروجی‌ها';
      details.addEventListener('click', () => {
        answerId = turn.id;
        showAnswer(turn.answer);
        $('feedback-positive').hidden ||= turns.indexOf(turn) > 0;
        $('result').scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      card.append(details);
    }
    $('conversation').append(card);
  }
}

async function loadChat(id, afterAsk = false) {
  if (chatBusy && !afterAsk) return;
  const data = await (await request(`/chats/${id}`)).json();
  activeChat = data.id;
  drawTurns(data.turns);
  const last = data.turns.at(-1);
  if (last) {
    answerId = last.id;
    showAnswer(last.answer);
    $('feedback-positive').hidden ||= data.turns.length > 1;
  }
  else { $('result').hidden = true; $('empty').hidden = false; }
  await refreshChats();
}

async function refreshChats() {
  const chats = await (await request('/chats')).json();
  $('chat-list').replaceChildren();
  for (const chat of chats) {
    const button = document.createElement('button');
    button.className = 'secondary';
    button.textContent = chat.title;
    button.setAttribute('aria-pressed', String(chat.id === activeChat));
    button.disabled = chatBusy;
    button.addEventListener('click', () => loadChat(chat.id).catch((error) => notice(error.message, true)));
    $('chat-list').append(button);
  }
  $('chat-delete').hidden = !activeChat;
  return chats;
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

$('chat-new').addEventListener('click', () => {
  if (chatBusy) return;
  clearChat();
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
