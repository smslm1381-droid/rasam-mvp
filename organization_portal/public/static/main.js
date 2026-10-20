import { guard, notify, state } from './api.js';
import { refreshSession } from './session.js';
import { showInvitation } from './account.js';
import './chat.js';
import './management.js';
import './connection.js';

state.invitation = new URLSearchParams(location.search).get('invite') || '';
if (state.invitation) history.replaceState({}, '', location.pathname);

try {
  await refreshSession();
  if (state.invitation) await showInvitation();
} catch (error) {
  notify(error.message);
}
