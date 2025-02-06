import { useCallback, useContext } from "preact/hooks";
import { useComputed, useSignal } from "@preact/signals";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";

import { UserValidationErrors } from "../../hooks/useAllUsers";
import { EditUserCard } from "./EditUserCard";
import { EndpointContext } from "../../endpoints";
import { useMessages } from "../../hooks/useMessages";
import { WhoAmIContext } from "../../hooks/useWhoAmI";
import { validateUserState } from "../utils/validateUserState";
import { FlattenedUserState } from "../../types/FlattenedUserState";
import { ProtectedPage } from "../../components/ProtectedPage";

const only = ['email', 'password', 'confirmPassword'];

const backUrl = uiRouteMap.home.url();

export function ChangePassword() {
  const [, setLocation] = useLocation();
  const apiRequests = useContext(EndpointContext);
  const { flattened, setUser } = useContext(WhoAmIContext);
  const { appendMessage } = useMessages();
  const changes = useSignal<Partial<FlattenedUserState>>({});
  const disabledFields = useSignal<Record<string, boolean>>({
    username: true,
    mustChange: true,
    groups: true,
  });
  const user = useComputed(() => {
    const usr: FlattenedUserState = {
      adminGroup: false,
      mediaGroup: false,
      userGroup: false,
      mustChange: true,
      lastLogin: null,
      ...flattened.value,
      ...changes.value,
    };
    return usr;
  });
  const errors = useComputed<UserValidationErrors>(() => validateUserState(user.value));

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
        appendMessage("success", "Password successfully modified");
        setUser(result.user);
        setLocation(uiRouteMap.listUsers.url());
      } else {
        appendMessage("warning", "Failed to change password");
      }
    } catch(err) {
      appendMessage("warning", `Failed to change password - ${err}`);
    }
  }, [apiRequests, appendMessage, setLocation, setUser, user.value]);

  return (
    <div className="content mb-4" style="max-width: 65rem">
      <EditUserCard
        backUrl={backUrl}
        header="Change my password"
        saveTitle="Change Password"
        user={user}
        validationErrors={errors}
        disabledFields={disabledFields}
        onSave={saveChanges}
        setValue={setValue}
        only={only}
      />
    </div>
  );
}

export default function ChangePasswordPage() {
  return <ProtectedPage><ChangePassword /></ProtectedPage>;
}
