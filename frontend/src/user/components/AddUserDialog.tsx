import { type ReadonlySignal, useSignal } from "@preact/signals";
import { useCallback, useContext } from "preact/hooks";

import { ModalDialog } from "../../components/ModalDialog";
import { EditUserForm } from "./EditUserForm";

import { AppStateContext } from "../../appState";
import { useMessages } from "../../hooks/useMessages";
import { EditUserState, UseAllUsersHook } from "../../hooks/useAllUsers";
import { randomToken } from "../../utils/randomToken";
import { Alert, AlertProps } from "../../components/Alert";

interface FooterProps {
  onClose: (ev: Event) => void;
  onSave: (ev: Event) => void;
}

function Footer({ onClose, onSave }: FooterProps) {
  return (
    <div role="group">
      <button type="button" data-testid="add-new-user-btn" className="btn btn-success me-3" onClick={onSave}>
        Add New User
      </button>
      <button type="button" data-testid="cancel-new-user-btn" className="btn btn-warning" onClick={onClose}>
        Cancel
      </button>
    </div>
  );
}

function generateNewUser(): EditUserState {
  const password = randomToken(12);
  const user: EditUserState = {
    adminGroup: false,
    mediaGroup: false,
    userGroup: true,
    mustChange: true,
    lastLogin: null,
    password,
    confirmPassword: password,
  };
  return user;
}

interface SaveErrorProps {
  error: ReadonlySignal<string>;
  onDismiss: AlertProps["onDismiss"];
}

function SaveError({error, onDismiss}: SaveErrorProps) {
  if (!error.value) {
    return null;
  }
  return <Alert level="warning" id={0} text={error} onDismiss={onDismiss} />;
}

export interface AddUserDialogProps {
  onClose: () => void;
  saveChanges: (user: EditUserState) => Promise<string>;
  validateUser: UseAllUsersHook["validateUser"];
}

export function AddUserDialog({ onClose, saveChanges, validateUser }: AddUserDialogProps) {
  const { dialog } = useContext(AppStateContext);
  const { appendMessage } = useMessages();
  const user = useSignal<EditUserState>(generateNewUser());
  const error = useSignal<string>("");
  const setValue = useCallback(
    (field: string, value: string | number | boolean) => {
      user.value = {
        ...user.value,
        [field]: value,
      };
    },
    [user]
  );
  const onSave = useCallback(async () => {
    if (!dialog.value?.addUser.active) {
      return;
    }
    const result = await saveChanges(user.value);
    if (!dialog.value?.addUser) {
      return;
    }
    if (result === "") {
      appendMessage("success", `Added new user "${user.value.username}"`);
      onClose();
    } else {
      error.value = `Failed to save new user ${user.value.username}: ${result}`;
    }
  }, [appendMessage, dialog, error, onClose, saveChanges, user]);
  const dismissError = useCallback(() => {
    error.value = "";
  }, [error]);

  if (!dialog.value?.addUser) {
    return null;
  }
  const footer = <Footer onClose={onClose} onSave={onSave} />;

  return (
    <ModalDialog
      onClose={onClose}
      title="Add new user"
      size="lg"
      footer={footer}
    >
      <SaveError error={error} onDismiss={dismissError} />
      <EditUserForm user={user} setValue={setValue} validateUser={validateUser} newUser={true} />
    </ModalDialog>
  );
}
