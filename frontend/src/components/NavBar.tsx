import { type JSX } from "preact";
import { useLocation } from "wouter-preact";
import { NavBarItem } from "../types/NavBarItem";
import { useCallback } from "preact/hooks";

function NavItem({ active, className, href, title }: NavBarItem) {
  const setLocation = useLocation()[1];
  const itemClassName = `nav-item ${className}`;
  const linkClass = `nav-link${active ? " active" : ""} ${className}`;
  const spaNavigate  = useCallback((ev: Event) => {
    ev.preventDefault();
    const href = (ev.target as HTMLAnchorElement).getAttribute('href');
    setLocation(href);
    }, [setLocation]);

  const anchorProps: JSX.AnchorHTMLAttributes = {
    className: linkClass,
    href,
  };
  if (active) {
    anchorProps["aria-current"] = "page";
  }
  if (/spa/.test(className)) {
    anchorProps.onClick = spaNavigate;
  }
  return <li className={itemClassName}><a {...anchorProps}>{title}</a></li>;
}

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
        </ul>
      </div>
    </nav>
  );
}
