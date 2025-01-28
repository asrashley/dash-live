import { useCallback, useContext } from "preact/hooks";
import { useComputed, useSignal } from "@preact/signals";
import { useLocation, useParams } from "wouter-preact";

import { FlattenedUserState, useAllUsers } from "../../hooks/useAllUsers";
import { RouteParamsType } from "../../types/RouteParamsType";
import { EditUserCard } from "./EditUserCard";
import { AppStateContext } from "../../appState";
import { DeleteUserDialog } from "./DeleteUserDialog";
import { EndpointContext } from "../../endpoints";
import { uiRouteMap } from "@dashlive/routemap";
import { useMessages } from "../../hooks/useMessages";

export default function EditUserPage() {
  const [, setLocation] = useLocation();
  const { dialog, closeDialog } = useContext(AppStateContext);
  const apiRequests = useContext(EndpointContext);
  const { appendMessage } = useMessages();
  const { flattenedUsers, error, validateUser, updateUser } = useAllUsers();
  const { username } = useParams<RouteParamsType>();
  const changes = useSignal<Partial<FlattenedUserState>>({});
  const userEntry = useComputed<FlattenedUserState | undefined>(() =>
    flattenedUsers.value.find((user) => user.username === username)
  );
  const user = useComputed(() => {
    const usr: FlattenedUserState = {
      adminGroup: false,
      mediaGroup: false,
      userGroup: false,
      mustChange: true,
      lastLogin: null,
      ...userEntry.value,
      ...changes.value,
    };
    return usr;
  });

  const setValue = useCallback(
    (field: string, value: string | number | boolean) => {
      changes.value = {
        ...changes.value,
        [field]: value,
      };
    },
    [changes]
  );

  const saveChanges = useCallback(async () => {
    try {
      const result = await apiRequests.editUser(user.value);
      if (result.success) {
        appendMessage("success", `User ${username} successfully modified`);
        updateUser(result.user);
        setLocation(uiRouteMap.listUsers.url());
      } else {
        appendMessage("warning", `Failed to modify user ${username}`);
      }
    } catch(err) {
      appendMessage("warning", `Failed to modify user ${username} - ${err}`);
    }
  }, [apiRequests, appendMessage, setLocation, updateUser, user, username]);

  const requestDelete = useCallback(() => {
    dialog.value = {
      backdrop: true,
      confirmDelete: {
        name: username,
        confirmed: false,
      },
    };
  }, [dialog, username]);

  const onConfirmDelete = useCallback(async () => {
    try {
      const result = await apiRequests.deleteUser(user.value.pk);
      if (result.ok) {
        appendMessage("success", `User ${username} successfully deleted`);
        setLocation(uiRouteMap.listUsers.url());
      } else {
        appendMessage("warning", "Failed to delete user");
      }
    } catch (err) {
      appendMessage("warning", `Failed to delete user - ${err}`);
    }
    closeDialog();
  }, [apiRequests, appendMessage, closeDialog, setLocation, user, username]);

  console.log(user.value);

  return (
    <div className="content mb-4" style="max-width: 65rem">
      <EditUserCard
        user={user}
        error={error}
        onDelete={requestDelete}
        onSave={saveChanges}
        setValue={setValue}
        validateUser={validateUser}
      />
      <DeleteUserDialog
        username={username}
        onCancel={closeDialog}
        onConfirm={onConfirmDelete}
      />
    </div>
  );
}
