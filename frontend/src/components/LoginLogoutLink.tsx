import { useCallback, useContext, useState } from "preact/hooks";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";

import { EndpointContext } from "../endpoints";
import { useMessages } from "../hooks/useMessages";
import { WhoAmIContext } from "../hooks/useWhoAmI";
import { Icon } from "./Icon";

export function LoginLogoutLink() {
  const { user, setUser } = useContext(WhoAmIContext);
  const api = useContext(EndpointContext);
  const { appendMessage } = useMessages();
  const setLocation = useLocation()[1];
  const [expanded, setExpanded] = useState<boolean>(false);
  const onLogin = useCallback(() => {
    setLocation(uiRouteMap.login.url());
  }, [setLocation]);
  const onChangePassword = useCallback(() => {
    setExpanded(false);
    setLocation(uiRouteMap.changePassword.url());
  }, [setLocation]);
  const onLogOut = useCallback(async () => {
    setExpanded(false);
    setUser(null);
    try {
      await api.logoutUser();
      appendMessage("success", "You have successfully logged out");
    } catch (err) {
      appendMessage("danger", `Logout failed: ${err}`);
    }
    setLocation(uiRouteMap.home.url());
  }, [setUser, setLocation, api, appendMessage]);
  const toggleExpand = useCallback(() => {
    setExpanded(!expanded);
  }, [expanded]);
  const toggleClasses = `btn btn-light dropdown-toggle${
    expanded ? " show" : ""
  }`;
  const listClasses = `dropdown-menu${expanded ? " show" : ""}`;

  if (!user.value.isAuthenticated) {
    return (
      <li className="nav-item dropdown ms-auto me-4">
        <button className="nav-link" role="menuitem" onClick={onLogin}>
          Log In
        </button>
      </li>
    );
  }

  return (
    <li className="nav-item dropdown ms-auto me-4">
      <span className="username me-1">{user.value.username}</span>
      <button
        className={toggleClasses}
        role="menubar"
        data-testid="toggle-user-menu"
        onClick={toggleExpand}
        aria-expanded={expanded}>
        <Icon name="gear-fill" />
      </button>
      <ul className={listClasses}>
        <li>
          <button className="dropdown-item" role="menuitem" onClick={onChangePassword}>
            Change Password
          </button>
        </li>
        <li>
          <button className="dropdown-item" role="menuitem" onClick={onLogOut}>
            Log Out
          </button>
        </li>
      </ul>
    </li>
  );
}
