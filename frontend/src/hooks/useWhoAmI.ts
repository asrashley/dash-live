import { useCallback, useEffect } from "preact/hooks";
import { type ReadonlySignal, useComputed, useSignal } from "@preact/signals";
import log from "loglevel";

import { ApiRequests } from "../endpoints";
import { JWToken } from "../types/JWToken";
import { LoginResponse } from "../types/LoginResponse";
import { InitialUserState, UserState } from "../types/UserState";
import { useMessages } from "./useMessages";
import { createContext } from "preact";

export interface UseWhoAmIHook {
  error: ReadonlySignal<string | null>;
  checked: ReadonlySignal<boolean>;
  user: ReadonlySignal<UserState>;
  setUser: (ius: InitialUserState) => void;
}

export interface UseWhoAmIProps {
    apiRequests: ApiRequests;
    refreshToken: Readonly<JWToken | null>;
}

export const WhoAmIContext = createContext<UseWhoAmIHook>(null);

export function useWhoAmI({ apiRequests, refreshToken }: UseWhoAmIProps): UseWhoAmIHook {
  const { appendMessage } = useMessages();
  const checked = useSignal<boolean>(false);
  const userInfo = useSignal<InitialUserState>({isAuthenticated: false, groups:[]});
  const error = useSignal<string | null>(null);
  const user = useComputed<UserState>(() => ({
    ...userInfo.value,
    permissions: {
      admin: userInfo.value.groups.includes('ADMIN'),
      media: userInfo.value.groups.includes('MEDIA'),
      user: userInfo.value.groups.includes('USER'),
    },
  }));

  const setUser = useCallback((ius: InitialUserState) => {
    userInfo.value = structuredClone(ius);
  }, [userInfo]);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const checkUserInfoIfRequired = async () => {
      log.trace(`getUserInfo hook checked=${checked.value} error=${error.value} token=${refreshToken}`);
      if (!checked.value) {
        if (refreshToken === null) {
            checked.value = true;
            return;
        }
        try {
          log.trace('Trying to fetch user info..');
          const response = await apiRequests.getUserInfo(signal);
          if (!signal.aborted) {
            if (response["success"] !== undefined) {
                const { user } = response as LoginResponse;
                userInfo.value = user;
            }
            checked.value = true;
            error.value = null;
          }
        } catch (err) {
          if (!signal.aborted) {
            error.value = `${err}`;
            checked.value = true;
            appendMessage("danger", `Failed to fetch user information: ${err}`);
          }
        }
      }
    };

    checkUserInfoIfRequired();

    return () => {
      if (!checked.value) {
        controller.abort();
      }
    };
  }, [apiRequests, error, checked, refreshToken, userInfo, appendMessage]);

  return { checked, error, user, setUser };
}
