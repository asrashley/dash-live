import { useContext } from "preact/hooks";
import { useComputed } from "@preact/signals";

import { ModalDialog } from "../../components/ModalDialog";
import { AppStateContext } from "../../appState";

interface BodyProps {
  deleting: boolean;
  name: string;
}
function Body({ deleting, name }: BodyProps) {
  if (deleting) {
    return <span>Deleting stream {name} ...</span>;
  }
  return <p className="fs-4">
    Are you sure you would like to delete stream "{name}"?
  </p>;
}

interface FooterProps  {
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}
function Footer({ deleting, onConfirm, onCancel }: FooterProps) {
  return <div className="btn-toolbar">
    <button className="btn btn-danger m-2" onClick={onConfirm} disabled={deleting}>
      Yes, I'm sure
    </button>
    <button className="btn btn-primary m-2" onClick={onCancel} disabled={deleting}>
      Cancel
    </button>
  </div>;
}

interface ConfirmDeleteDialogProps {
  onClose: () => void;
}
export function ConfirmDeleteDialog({onClose}: ConfirmDeleteDialogProps) {
  const { dialog } = useContext(AppStateContext);

  const confirmDelete = useComputed(() => dialog.value?.confirmDelete);

  if (!confirmDelete.value) {
    return null;
  }

  const { name } = confirmDelete.value;

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

  const footer = <Footer
    deleting={confirmDelete.value.confirmed}
    onConfirm={onConfirm}
    onCancel={onClose}
  />;
  return <ModalDialog onClose={onClose} title="Confirm deletion of stream" footer={footer}>
    <Body name={name} deleting={confirmDelete.value.confirmed} />
</ModalDialog>;
}
