import { useCallback, useContext } from "preact/hooks";
import { useComputed, type ReadonlySignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { useJsonRequest } from "./useJsonRequest";
import { InitialUserState } from "../types/UserState";
import { FlattenedUserState } from "../types/FlattenedUserState";
import { EditUserState } from "../types/EditUserState";
import { flattenUserState } from "../user/utils/flattenUserState";
import { validateUserState } from "../user/utils/validateUserState";

export type UserValidationErrors = {
  username?: string;
  email?: string;
  password?: string;
};

export interface UseAllUsersHook {
  allUsers: ReadonlySignal<InitialUserState[]>;
  flattenedUsers: ReadonlySignal<FlattenedUserState[]>;
  loaded: ReadonlySignal<boolean>;
  error: ReadonlySignal<string | null>;
  addUser: (user: Omit<InitialUserState, 'lastLogin'>) => boolean;
  updateUser: (user: InitialUserState) => boolean;
  validateUser: (user: EditUserState) => UserValidationErrors;
}

export function useAllUsers(): UseAllUsersHook {
  const apiRequests = useContext(EndpointContext);
  const request = useCallback((signal: AbortSignal) => apiRequests.getAllUsers({
    signal,
  }), [apiRequests]);
  const { data: allUsers, error, loaded, setData } = useJsonRequest<InitialUserState[]>({
    request,
    initialData: [],
    name: 'list of users',
  });
  const flattenedUsers = useComputed<FlattenedUserState[]>(() => allUsers.value.map(flattenUserState));
  const validateUser = useCallback((user: EditUserState) => validateUserState(user, allUsers.value), [allUsers]);

  const addUser = useCallback((user: Omit<InitialUserState, 'lastLogin'>) => {
    if (!user.username) {
      return false;
    }
    if (allUsers.value.some(usr => usr.username === user.username)) {
      return false;
    }
    const newUsers = [...allUsers.value];
    newUsers.push({
      lastLogin: null,
      ...user
    });
    setData(newUsers);
    return true;
  }, [allUsers, setData]);

  const updateUser = useCallback((user: InitialUserState) => {
    if (!allUsers.value.some(u => u.pk === user.pk)) {
      return false;
    }
    const newUsers = allUsers.value.map(usr => usr.pk === user.pk ? { ...usr, ...user } : usr);
    setData(newUsers);
    return true;
  }, [allUsers, setData]);

  return { allUsers, flattenedUsers, error, loaded, addUser, validateUser, updateUser };
}
