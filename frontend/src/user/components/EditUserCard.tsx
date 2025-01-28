import { type ReadonlySignal } from "@preact/signals";
import { Link } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";

import { FlattenedUserState, UseAllUsersHook } from "../../hooks/useAllUsers";
import { SetValueFunc } from "../../types/SetValueFunc";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { Card } from "../../components/Card";
import { Alert } from "../../components/Alert";
import { EditUserForm } from "./EditUserForm";

export interface EditUserCardProps {
  user: ReadonlySignal<FlattenedUserState | undefined>;
  error: ReadonlySignal<string | null>;
  setValue: SetValueFunc;
  validateUser: UseAllUsersHook["validateUser"];
  onSave: () => void;
  onDelete: () => void;
}

export function EditUserCard({
  error,
  user,
  onDelete,
  onSave,
  setValue,
  validateUser,
}: EditUserCardProps) {
  const backUrl = uiRouteMap.listUsers.url();

  if (!user.value) {
    return <LoadingSpinner />;
  }
  return (
    <Card id="edit-user" header={`Editing user ${user.value.username}`}>
      {error.value ? <Alert id={0} level="warning" text={error} /> : ""}
      <EditUserForm
        user={user}
        setValue={setValue}
        validateUser={validateUser}
        newUser={false}
      />
      <div className="form-actions mt-2">
        <button onClick={onSave} className="btn btn-primary me-3">
          Save Changes
        </button>
        <button onClick={onDelete} className="btn btn-danger me-3">
          Delete User
        </button>
        <Link href={backUrl} className="btn btn-warning">
          Cancel
        </Link>
      </div>
    </Card>
  );
}
