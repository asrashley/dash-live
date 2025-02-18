import { useCallback, useContext } from "preact/hooks";
import { useSignal } from "@preact/signals";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";

import { EndpointContext } from "../../endpoints";
import { LoginRequest } from "../types/LoginRequest";
import { LoginResponse } from "../types/LoginResponse";
import { WhoAmIContext } from "../hooks/useWhoAmI";
import { useLocalStorage } from "../../hooks/useLocalStorage";

import { LoginCard } from "./LoginCard";

export default function LoginPage() {
  const apiRequests = useContext(EndpointContext);
  const { setUser } = useContext(WhoAmIContext);
  const { setRefreshToken } = useLocalStorage();
  const setLocation = useLocation()[1];
  const error = useSignal<string | undefined>();
  const submitting = useSignal<boolean>(false);
  const onLogin = useCallback((request: LoginRequest) => {
    submitting.value = true;
    apiRequests.loginUser(request).then((resp: LoginResponse) => {
        if (resp.success) {
            error.value = undefined;
            setUser(resp.user);
            setRefreshToken(resp.refreshToken ?? null);
            setLocation(uiRouteMap.home.url());
        } else {
            error.value = resp.error ?? 'Unknown error';
        }
    }).catch(err => {
        error.value = `Login failed - ${err}`;
    }).finally(() =>{
        submitting.value = false;
    });
  }, [apiRequests, error, setLocation, setRefreshToken, setUser, submitting]);

  return <LoginCard submitting={submitting} error={error} onLogin={onLogin} />;
}
