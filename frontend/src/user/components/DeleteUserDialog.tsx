import { useContext } from "preact/hooks";
import { AppStateContext } from "../../appState";
import { ModalDialog } from "../../components/ModalDialog";

export interface DeleteUserDialogProps {
  username: string;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteUserDialog({
  username,
  onCancel,
  onConfirm,
}: DeleteUserDialogProps) {
  const { dialog } = useContext(AppStateContext);

  if (!dialog.value?.confirmDelete) {
    return null;
  }
  const footer = (
    <div className="form-actions">
      <button className="btn btn-danger me-4" onClick={onConfirm}>
        Delete {username}
      </button>
      <button className="btn btn-primary me-2" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );

  return (
    <ModalDialog
      onClose={onCancel}
      title="Are you sure you want to delete this user?"
      footer={footer}
    >
      <h3>Delete user "{username}" ?</h3>
    </ModalDialog>
  );
}
