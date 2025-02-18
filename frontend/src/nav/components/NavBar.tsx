import { useCallback, useContext, useState } from "preact/hooks";
import { type ReadonlySignal, useComputed } from "@preact/signals";

import { uiRouteMap } from "@dashlive/routemap";

import { NavBarItem } from "../types/NavBarItem";
import { LoginLogoutLink } from "../../user/components/LoginLogoutLink";
import { NavItem } from "./NavItem";
import { WhoAmIContext } from "../../user/hooks/useWhoAmI";
import { UserState } from "../../user/types/UserState";

export function createNavItems(user: ReadonlySignal<UserState>): NavBarItem[] {
  const navbar: NavBarItem[] = [
    {
      className: "spa", href: uiRouteMap.home.url(), title: "Home"
    }, {
      className: "", href: "/streams", title: "Streams"
    }, {
      className: "spa", href: uiRouteMap.listMps.url(), title: "Multi-Period"
    }, {
      className: "spa", href: uiRouteMap.validator.url(), title: "Validate"
    }, {
      className: "", href: "/media/inspect", title: "Inspect"
    },
  ];
  if (user.value.permissions.admin) {
    navbar.push({
      className: "spa", href: uiRouteMap.listUsers.url(), title: "Users"
    });
  }
  return navbar;
}

export function NavBar() {
  const { user } = useContext(WhoAmIContext);
  const [expanded, setExpanded] = useState<boolean>(false);
  const toggleExpand = useCallback(() => setExpanded(!expanded), [expanded]);
  const items = useComputed(() => createNavItems(user));

  const togglerClassName = `navbar-toggler${expanded ? '' : ' collapsed'}`;
  const navbarClassName = `collapse navbar-collapse${ expanded ? ' show' : ''}`;

  return (
    <nav className="navbar navbar-expand-lg navbar-light bg-body-tertiary">
      <span className="navbar-brand">DASH server</span>
      <button
        onClick={toggleExpand}
        className={togglerClassName}
        type="button"
        aria-controls="navbarSupportedContent"
        aria-expanded={expanded}
        aria-label="Toggle navigation"
      >
        <span className="navbar-toggler-icon" />
      </button>

      <div className={navbarClassName} id="navbarSupportedContent">
        <ul className="navbar-nav flex-fill">
        {items.value.map((item) => (
            <NavItem key={item.title} {...item} />
          ))}
          <LoginLogoutLink />
          </ul>
      </div>
    </nav>
  );
}
