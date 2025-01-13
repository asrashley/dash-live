import { NavBarItem } from "../types/NavBarItem";
import { LoginLogoutLink } from "./LoginLogoutLink";
import { NavItem } from "./NavItem";

export interface NavBarProps {
  items: NavBarItem[];
}
export function NavBar({ items }: NavBarProps) {
  return (
    <nav className="navbar navbar-expand-lg navbar-light bg-body-tertiary">
      <span className="navbar-brand">DASH server</span>
      <button
        className="navbar-toggler"
        type="button"
        aria-controls="navbarSupportedContent"
        aria-expanded="false"
        aria-label="Toggle navigation"
      >
        <span className="navbar-toggler-icon" />
      </button>

      <div className="collapse navbar-collapse" id="navbarSupportedContent">
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
