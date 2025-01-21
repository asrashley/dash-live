import { useCallback, useContext } from "preact/hooks";
import { useComputed } from "@preact/signals";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";

import { EndpointContext } from "../endpoints";
import { useMessages } from "../hooks/useMessages";
import { WhoAmIContext } from "../hooks/useWhoAmI";

export function LoginLogoutLink() {
  const { user, setUser } = useContext(WhoAmIContext);
  const api = useContext(EndpointContext);
  const { appendMessage } = useMessages();
  const setLocation = useLocation()[1];
  const title = useComputed<string>(() => user.value.isAuthenticated ? "Log Out" : "Log In");
  const href = useComputed<string>(() => user.value.isAuthenticated ? "#": uiRouteMap.login.url());
  const onClick = useCallback(
    async (ev: Event) => {
      ev.preventDefault();
      if (user.value.isAuthenticated) {
        setUser(null);
        try {
            await api.logoutUser();
            appendMessage('success', 'You have successfully logged out');
        } catch (err) {
            appendMessage('danger', `Logout failed: ${err}`);
        }
        setLocation(uiRouteMap.home.url());
      } else {
        setLocation(uiRouteMap.login.url());
      }
    },
    [user, setUser, setLocation, api, appendMessage]
  );

  return (
    <li className="nav-item user-login">
      <a className="nav-link" href={href} onClick={onClick}>
        {title}
      </a>
    </li>
  );
}
