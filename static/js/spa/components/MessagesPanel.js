import { html } from 'htm/preact';
import { useCallback } from 'preact/hooks'

import { Alert } from './Alert.js';

export function MessagesPanel({messages}) {
  const dismissAlert = useCallback((id) => {
    const newAlerts = messages.value.alerts.filter(a => a.id !== id);
    messages.value = {
      ...messages.value,
      alerts: newAlerts,
    };
  }, [messages]);

  const alerts = messages.value.alerts.map(
    item => html`<${Alert} key=${item.id} onDismiss=${dismissAlert} ...${item} />`);

  return html`<div class="messages-panel">${ alerts }</div>`;
}
