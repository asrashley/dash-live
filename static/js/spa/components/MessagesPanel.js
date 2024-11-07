import { html } from 'htm/preact';
import { useCallback } from 'preact/hooks'

import { Alert } from './Alert.js';
import { useMessages } from '@dashlive/hooks';

export function MessagesPanel() {
  const  { alerts, removeAlert } = useMessages();

  const onDismiss = useCallback((id) => {
    removeAlert(id);
  }, [removeAlert]);

  return html`<div class="messages-panel">${ alerts.value.map(
    item => html`<${Alert} key=${item.id} onDismiss=${onDismiss} ...${item} />`) }</div>`;
}
