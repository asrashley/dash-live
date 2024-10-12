import { html } from 'htm/preact';

export function ModalDialog({id = 'dialog-box', title, children, footer, size, onClose}) {
  const classNames = ["modal-dialog"];
  if (size !== undefined) {
    classNames.push(`modal-${size}`);
  }
  if (footer === undefined) {
    footer = html`<button type="button" class="btn btn-secondary btn-secondary" data-bs-dismiss="modal" onClick=${onClose}>Close</button>`;
  }

  return html`
<div class="modal fade show" tabIndex="-1" role="dialog" aria-modal="true"
  id="${id}" style="display: block">
  <div class="${classNames.join(' ')}" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">${ title }</h5>
        <button type="button" class="close btn-close"
              data-bs-dismiss="modal" aria-label="Close" onClick=${onClose}>
        </button>
      </div>
      <div class="modal-body m-2">
       ${ children }
      </div>
      <div class="modal-footer">
        ${ footer }
      </div>
    </div>
  </div>
</div>
`;
}
