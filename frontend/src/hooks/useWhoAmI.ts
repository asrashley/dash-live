import { createContext } from "preact";
import { useCallback } from "preact/hooks";
import { type ReadonlySignal, useComputed, useSignal } from "@preact/signals";

import { InitialUserState, UserState } from "../types/UserState";

export interface UseWhoAmIHook {
  user: ReadonlySignal<UserState>;
  setUser: (ius: InitialUserState | null) => void;
}

export const WhoAmIContext = createContext<UseWhoAmIHook>(null);

const blankState: InitialUserState = {
  mustChange: false,
  lastLogin: null,
  groups:[],
};

export function useWhoAmI(): UseWhoAmIHook {
  const userInfo = useSignal<InitialUserState>(blankState);
  const user = useComputed<UserState>(() => ({
    ...userInfo.value,
    isAuthenticated: userInfo.value.pk !== undefined,
    permissions: {
      admin: userInfo.value.groups.includes('ADMIN'),
      media: userInfo.value.groups.includes('MEDIA'),
      user: userInfo.value.groups.includes('USER'),
    },
  }));

  const setUser = useCallback((ius: InitialUserState | null) => {
    if (ius) {
      userInfo.value = structuredClone(ius);
    } else {
      userInfo.value = structuredClone(blankState);
    }
  }, [userInfo]);

  return { user, setUser };
}
