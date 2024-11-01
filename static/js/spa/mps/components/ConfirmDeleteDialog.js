import { html } from "htm/preact";
import { useContext } from "preact/hooks";
import { useComputed } from "@preact/signals";

import { ModalDialog } from "@dashlive/ui";
import { AppStateContext } from "../../appState.js";

function Body({ deleting, name }) {
  if (deleting) {
    return html`Deleting stream ${name} ...`;
  }
  return html`<p class="fs-4">
    Are you sure you would like to delete stream "${name}"?
  </p>`;
}

function Footer({ deleting, onConfirm, onCancel }) {
  return html`<div class="btn-toolbar">
    <button class="btn btn-danger m-2" onClick=${onConfirm} disabled=${deleting}>
      Yes, I'm sure
    </button>
    <button class="btn btn-primary m-2" onClick=${onCancel} disabled=${deleting}>
      Cancel
    </button>
  </div>`;
}

export function ConfirmDeleteDialog() {
  const { dialog } = useContext(AppStateContext);

  const confirmDelete = useComputed(() => dialog.value?.confirmDelete);

  if (!confirmDelete.value) {
    return null;
  }

  const { name } = confirmDelete.value;

  const onClose = () => {
    dialog.value = null;
  };

  const onConfirm = () => {
    if (!confirmDelete.value) {
      return;
    }
    dialog.value = {
      ...dialog.value,
      confirmDelete: {
        ...confirmDelete.value,
        confirmed: true,
      },
    };
  };

  const footer = html`<${Footer}
    deleting=${confirmDelete.value.confirmed}
    onConfirm=${onConfirm}
    onCancel=${onClose}
  />`;
  return html`
<${ModalDialog} onClose=${onClose} title="Confirm deletion of stream" footer=${footer}>
    <${Body} name=${name} deleting=${confirmDelete.value.confirmed} />
</${ModalDialog}>`;
}
