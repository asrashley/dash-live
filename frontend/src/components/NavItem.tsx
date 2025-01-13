import type { JSX } from "preact";
import { useCallback } from "preact/hooks";
import { useLocation } from "wouter-preact";
import type { NavBarItem } from "../types/NavBarItem";

export function NavItem({ active, className, href, title }: NavBarItem) {
  const setLocation = useLocation()[1];
  const itemClassName = `nav-item ${className}`;
  const linkClass = `nav-link${active ? " active" : ""} ${className}`;
  const spaNavigate = useCallback((ev: Event) => {
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
