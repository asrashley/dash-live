import { useCallback, useState } from "preact/hooks";
import { NavBarItem } from "../types/NavBarItem";
import { LoginLogoutLink } from "./LoginLogoutLink";
import { NavItem } from "./NavItem";

export interface NavBarProps {
  items: NavBarItem[];
}
export function NavBar({ items }: NavBarProps) {
  const [expanded, setExpanded] = useState<boolean>(false);
  const toggleExpand = useCallback(() => setExpanded(!expanded), [expanded]);
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
          {items.map((item) => (
            <NavItem key={item.title} {...item} />
          ))}
          <LoginLogoutLink />
        </ul>
      </div>
    </nav>
  );
}
