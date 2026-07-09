import { useComputed, type ReadonlySignal } from "@preact/signals";
import { Link } from "wouter-preact";

import { SetValueFunc } from "../../form/types/SetValueFunc";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { Card } from "../../components/Card";
import { Alert } from "../../components/Alert";
import { EditUserForm, EditUserFormProps } from "./EditUserForm";
import { EditUserState } from "../types/EditUserState";

function NetworkErrorAlert({ networkError }: { networkError: string | null }) {
  if (!networkError) {
    return null;
  }
  return <Alert id={0} level="warning" text={networkError} />;
}

export interface EditUserCardProps {
  user: ReadonlySignal<EditUserState | undefined>;
  networkError?: ReadonlySignal<string | null>;
  validationErrors: EditUserFormProps["errors"];
  disabledFields: EditUserFormProps["disabledFields"];
  only?: EditUserFormProps["only"];
  header: string | ReadonlySignal<string>;
  backUrl: string;
  saveTitle?: string;
  setValue: SetValueFunc;
  onSave: () => void;
  onDelete?: () => void;
}

export function EditUserCard({
  backUrl,
  disabledFields,
  header,
  networkError,
  only,
  user,
  validationErrors,
  saveTitle="Save Changes",
  onDelete,
  onSave,
  setValue,
}: EditUserCardProps) {
  const disableSave = useComputed<boolean>(() => Object.keys(validationErrors.value).length > 0);

  if (!user.value) {
    return <LoadingSpinner />;
  }
  return (
    <Card id="edit-user" header={header}>
      <NetworkErrorAlert networkError={networkError?.value ?? null} />
      <EditUserForm
        user={user as ReadonlySignal<EditUserState>}
        setValue={setValue}
        disabledFields={disabledFields}
        errors={validationErrors}
        newUser={false}
        only={only}
      />
      <div className="form-actions mt-2">
        <button onClick={onSave} className="btn btn-primary me-3" disabled={disableSave}>
          {saveTitle}
        </button>
        {onDelete ? <button onClick={onDelete} className="btn btn-danger me-3">
          Delete User
        </button> : ""}
        <Link href={backUrl} className="btn btn-warning">
          Cancel
        </Link>
      </div>
    </Card>
  );
}
