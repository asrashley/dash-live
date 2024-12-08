import { html } from 'htm/preact';
import { useCallback } from 'preact/hooks'

export function Alert({text, level, onDismiss, id}) {
  const dismiss = useCallback(() => {
    onDismiss(id);
  }, [id, onDismiss]);
  const className = `alert alert-${level} ${onDismiss ? "alert-dismissible fade ": ""}show`;
  return html`<div class="${className}" id="alert_${id}" role="alert">
  ${ text }
  ${ onDismiss ? html`<button type="button" class="btn-close"
    data-bs-dismiss="alert" aria-label="Close"
    onClick=${dismiss}></button>`: null }
</div>`;
}
