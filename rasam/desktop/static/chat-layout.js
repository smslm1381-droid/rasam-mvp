'use strict';

function resizeComposer() {
  $('question').style.height = 'auto';
  $('question').style.height = `${Math.min($('question').scrollHeight, 145)}px`;
}

function scrollChat() {
  requestAnimationFrame(() => { $('chat-scroll').scrollTop = $('chat-scroll').scrollHeight; });
}

function closeHistory() {
  $('workspace').classList.remove('sidebar-open');
  $('sidebar-toggle').setAttribute('aria-expanded', 'false');
  $('sidebar-backdrop').hidden = true;
  syncSidebarFocus();
}

$('sidebar-toggle').addEventListener('click', () => {
  const open = !$('workspace').classList.contains('sidebar-open');
  $('workspace').classList.toggle('sidebar-open', open);
  $('sidebar-toggle').setAttribute('aria-expanded', String(open));
  $('sidebar-backdrop').hidden = !open;
});
$('sidebar-backdrop').addEventListener('click', closeHistory);
$('result-close').addEventListener('click', () => $('result-dialog').close());
$('question').addEventListener('input', resizeComposer);
$('question').addEventListener('keydown', (event) => {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  if (!chatBusy && $('question').value.trim()) $('ask-form').requestSubmit();
});
for (const button of document.querySelectorAll('[data-draft]')) {
  button.addEventListener('click', () => {
    $('question').value = button.dataset.draft;
    resizeComposer();
    $('question').focus();
  });
}
for (const button of document.querySelectorAll('[data-close-panel]')) {
  button.addEventListener('click', () => { $(button.dataset.closePanel).hidden = true; });
}
for (const id of ['setup-open', 'teaching-open']) {
  $(id).addEventListener('click', () => {
    const other = id === 'setup-open' ? 'teaching' : 'setup';
    $(other).hidden = true;
    closeHistory();
  });
}
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeHistory();
});

// فرم باز، تمرکز صفحه‌کلید را از پیام‌های پشت خودش جدا نگه می‌دارد.
const settingsPanels = [$('setup'), $('teaching')];
const panelObserver = new MutationObserver(() => {
  const visible = settingsPanels.find((panel) => !panel.hidden);
  $('qa').inert = !!visible;
  visible?.querySelector('.panel-close')?.focus();
});
for (const panel of settingsPanels) panelObserver.observe(panel, { attributes: true, attributeFilter: ['hidden'] });
const narrowScreen = window.matchMedia('(max-width: 760px)');
function syncSidebarFocus() {
  $('chat-sidebar').inert = narrowScreen.matches && !$('workspace').classList.contains('sidebar-open');
}
narrowScreen.addEventListener('change', () => { closeHistory(); syncSidebarFocus(); });
$('sidebar-toggle').addEventListener('click', () => {
  syncSidebarFocus();
  if ($('workspace').classList.contains('sidebar-open')) $('chat-search').focus();
});
syncSidebarFocus();

$('activation-quit').addEventListener('click', () => $('quit-button').click());
