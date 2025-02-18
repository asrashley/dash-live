import { createContext } from "preact";
import { useCallback } from "preact/hooks";
import { type ReadonlySignal, useComputed, useSignal } from "@preact/signals";

import { UserState } from "../types/UserState";
import { InitialUserState } from "../types/InitialUserState";
import { FlattenedUserState } from "../types/FlattenedUserState";
import { flattenUserState } from "../utils/flattenUserState";

export interface UseWhoAmIHook {
  user: ReadonlySignal<UserState>;
  flattened: ReadonlySignal<FlattenedUserState>;
  setUser: (ius: InitialUserState | null) => void;
}

export const WhoAmIContext = createContext<UseWhoAmIHook>(null);

const blankState: InitialUserState = {
  mustChange: false,
  lastLogin: null,
  groups:[],
};

export function useWhoAmI(): UseWhoAmIHook {
  const userInfo = useSignal<InitialUserState>(structuredClone(blankState));
  const user = useComputed<UserState>(() => ({
    ...userInfo.value,
    isAuthenticated: userInfo.value.pk !== undefined,
    permissions: {
      admin: userInfo.value.groups.includes('ADMIN'),
      media: userInfo.value.groups.includes('MEDIA'),
      user: userInfo.value.groups.includes('USER'),
    },
  }));
  const flattened = useComputed<FlattenedUserState>(() => flattenUserState(user.value));

  const setUser = useCallback((ius: InitialUserState | null) => {
    if (ius) {
      userInfo.value = structuredClone(ius);
    } else {
      userInfo.value = structuredClone(blankState);
    }
  }, [userInfo]);

  return { user, flattened, setUser };
}
