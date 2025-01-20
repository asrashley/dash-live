import { useCallback } from "preact/hooks";
import { type ReadonlySignal, useSignal } from "@preact/signals";

import { defaultCgiOptions } from "@dashlive/options";

import { InputFormData } from "../types/InputFormData";
import { JWToken } from "../types/JWToken";

export enum LocalStorageKeys {
  DASH_OPTIONS = "dashlive.homepage.options",
  REFRESH_TOKEN = "dashlive.refresh.token",
}

function getDefaultDashOptions(): InputFormData {
  const lsKey = localStorage.getItem(LocalStorageKeys.DASH_OPTIONS);
  let previousOptions: Partial<InputFormData> = {};
  try {
    previousOptions = lsKey ? JSON.parse(lsKey) : {};
  } catch (err) {
    console.warn(`Failed to parse ${LocalStorageKeys.DASH_OPTIONS}: ${err}`);
  }
  return {
    ...defaultCgiOptions,
    manifest: "hand_made.mpd",
    mode: "vod",
    stream: undefined,
    ...previousOptions,
  };
}

function getRefreshToken(): JWToken | null {
  try{
  const jwt = localStorage.getItem(LocalStorageKeys.REFRESH_TOKEN);
  return jwt ? JSON.parse(jwt) : null;
  } catch (err) {
    console.warn(`Failed to parse ${LocalStorageKeys.REFRESH_TOKEN}: ${err}`);
    return null;
  }
}

export interface UseLocalStorageHook {
  dashOptions: ReadonlySignal<InputFormData>;
  refreshToken: ReadonlySignal<JWToken | null>;
  setDashOption: (name: string, value: string | number | boolean) => void;
  resetDashOptions: () => void;
  setRefreshToken: (token: JWToken | null) => void;
}

export function useLocalStorage(): UseLocalStorageHook {
  const dashOptions = useSignal<InputFormData>(getDefaultDashOptions());
  const refreshToken = useSignal<JWToken | null>(getRefreshToken());

  const setDashOption = useCallback((name: string, value: string | number | boolean) => {
    if (value === true) {
      value = "1";
    } else if (value === false) {
      value = "0";
    }
    const data: InputFormData = {
      ...dashOptions.value,
      [name]: value,
    };
    dashOptions.value = data;
    const params = Object.fromEntries(
      Object.entries(data).filter(
        ([key, value]) => defaultCgiOptions[key] !== value
      )
    );
    localStorage.setItem(LocalStorageKeys.DASH_OPTIONS, JSON.stringify(params));
  }, [dashOptions]);

  const resetDashOptions = useCallback(() => {
    localStorage.removeItem(LocalStorageKeys.DASH_OPTIONS);
    dashOptions.value = getDefaultDashOptions();
  }, [dashOptions]);

  const setRefreshToken = useCallback((token: JWToken | null) => {
    if (token) {
      localStorage.setItem(LocalStorageKeys.REFRESH_TOKEN, JSON.stringify(token));
    } else {
      localStorage.removeItem(LocalStorageKeys.REFRESH_TOKEN);
    }
    refreshToken.value = token;
  }, [refreshToken]);

  const hook: UseLocalStorageHook = {
    dashOptions,
    refreshToken,
    setDashOption,
    resetDashOptions,
    setRefreshToken,
  };
  return hook;
}