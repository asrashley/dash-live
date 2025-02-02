import { useCallback, useContext } from "preact/hooks";
import { useComputed, type ReadonlySignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { useJsonRequest } from "./useJsonRequest";
import { InitialUserState } from "../types/UserState";

export type FlattenedUserState = Omit<InitialUserState, 'groups'> & {
  adminGroup: boolean;
  mediaGroup: boolean;
  userGroup: boolean;
}

export type EditUserState = FlattenedUserState & {
  password?: string;
  confirmPassword?: string;
}

export type UserValidationErrors = {
  username?: string;
  email?: string;
  password?: string;
};

export function validateUserState(user: EditUserState, allUsers: ReadonlySignal<InitialUserState[]>): UserValidationErrors {
  const errs: UserValidationErrors = {};
  if (user.pk) {
    if (allUsers.value.some(({ pk, username }) => pk !== user.pk && username === user.username)) {
      errs.username = `${user.username} already exists`;
    }
  } else {
    if (allUsers.value.some(({ username }) => username === user.username)) {
      errs.username = `${user.username} username already exists`;
    }
    if (!user.password) {
      errs.password = 'a password is required';
    } else if (user.password !== user.confirmPassword) {
      errs.password = 'passwords do not match';
    }
    if (allUsers.value.some(({ email }) => email === user.email)) {
      errs.email = `${user.email} email address already exists`;
    }
  }
  if (!user.username) {
    errs.username = 'a username is required';
  }
  if (!user.email) {
    errs.email = 'an email address is required';
  }
  return errs;
}

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
  const flattenedUsers = useComputed<FlattenedUserState[]>(() => allUsers.value.map(({ groups, ...user }) => {
    const flat: FlattenedUserState = {
      ...user,
      adminGroup: groups.includes('ADMIN'),
      mediaGroup: groups.includes('MEDIA'),
      userGroup: groups.includes('USER'),
    };
    return flat;
  }));
  const validateUser = useCallback((user: EditUserState) => validateUserState(user, allUsers), [allUsers]);

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
