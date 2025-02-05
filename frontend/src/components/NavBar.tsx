import { useCallback, useContext, useState } from "preact/hooks";
import { type ReadonlySignal, useComputed } from "@preact/signals";

import { NavBarItem } from "../types/NavBarItem";
import { LoginLogoutLink } from "./LoginLogoutLink";
import { NavItem } from "./NavItem";
import { WhoAmIContext } from "../hooks/useWhoAmI";
import { UserState } from "../types/UserState";

export function createNavItems(user: ReadonlySignal<UserState>): NavBarItem[] {
  const navbar: NavBarItem[] = [
    {
      className: "spa", href: "/", title: "Home"
    }, {
      className: "", href: "/streams", title: "Streams"
    }, {
      className: "spa", href: "/multi-period-streams", title: "Multi-Period"
    }, {
      className: "", href: "/validate/", title: "Validate"
    }, {
      className: "", href: "/media/inspect", title: "Inspect"
    },
  ];
  if (user.value.permissions.admin) {
    navbar.push({
      className: "spa", href: "/users", title: "Users"
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
        <ul className="navbar-nav mr-auto">
          {items.value.map((item) => (
            <NavItem key={item.title} {...item} />
          ))}
          <LoginLogoutLink />
        </ul>
      </div>
    </nav>
  );
}
