import { type ReadonlySignal, useComputed, useSignal } from "@preact/signals";
import { useCallback, useContext } from "preact/hooks";

import { ModalDialog } from "../../components/ModalDialog";
import { EditUserForm } from "./EditUserForm";

import { AppStateContext } from "../../appState";
import { useMessages } from "../../hooks/useMessages";
import { UseAllUsersHook, UserValidationErrors } from "../hooks/useAllUsers";
import { randomToken } from "../../utils/randomToken";
import { Alert, AlertProps } from "../../components/Alert";
import { EditUserState } from "../types/EditUserState";

interface FooterProps {
  onClose: (ev: Event) => void;
  onSave: (ev: Event) => void;
  errors: ReadonlySignal<UserValidationErrors>;
  submitting: ReadonlySignal<boolean>;
}

function Footer({ onClose, onSave, errors, submitting }: FooterProps) {
  const disableSave = useComputed<boolean>(() => submitting.value || Object.keys(errors.value).length !== 0);
  return (
    <div role="group">
      <button type="button" data-testid="add-new-user-btn" className="btn btn-success me-3" onClick={onSave} disabled={disableSave}>
        Add New User
      </button>
      <button type="button" data-testid="cancel-new-user-btn" className="btn btn-warning" onClick={onClose} disabled={submitting}>
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
  const submitting = useSignal<boolean>(false);
  const disabledFields = useSignal<Record<string, boolean>>({});
  const errors = useComputed<UserValidationErrors>(() => validateUser(user.value));

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
    submitting.value = true;
    const result = await saveChanges(user.value);
    submitting.value = false;
    if (result === "") {
      appendMessage("success", `Added new user "${user.value.username}"`);
      onClose();
    } else {
      error.value = `Failed to save new user ${user.value.username}: ${result}`;
    }
  }, [appendMessage, error, onClose, saveChanges, submitting, user]);

  const dismissError = useCallback(() => {
    error.value = "";
  }, [error]);

  if (!dialog.value?.addUser) {
    return null;
  }
  const footer = <Footer onClose={onClose} onSave={onSave} errors={errors} submitting={submitting} />;

  return (
    <ModalDialog
      onClose={onClose}
      title="Add new user"
      size="lg"
      footer={footer}
    >
      <SaveError error={error} onDismiss={dismissError} />
      <EditUserForm user={user} setValue={setValue} errors={errors} disabledFields={disabledFields} newUser={true} />
    </ModalDialog>
  );
}
