import { useComputed, type ReadonlySignal } from "@preact/signals";
import { Link } from "wouter-preact";

import { SetValueFunc } from "../../types/SetValueFunc";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { Card } from "../../components/Card";
import { Alert } from "../../components/Alert";
import { EditUserForm, EditUserFormProps } from "./EditUserForm";

export interface EditUserCardProps {
  user: EditUserFormProps["user"];
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
      {networkError?.value ? <Alert id={0} level="warning" text={networkError} /> : ""}
      <EditUserForm
        user={user}
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
