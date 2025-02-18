import { Link, useLocation } from "wouter-preact";
import type { NavBarItem } from "../types/NavBarItem";

export function NavItem({ className, href, title }: NavBarItem) {
  const [location] = useLocation();
  const itemClassName = `nav-item ${className}`;
  const active = location === href;
  const linkClass = `nav-link${active ? " active" : ""} ${className}`;

  if (/spa/.test(className)) {
    return <li className={itemClassName}><Link href={href} className={linkClass} role="menuitem">{title}</Link></li>;
  }
  return <li className={itemClassName}><a href={href} className={linkClass} role="menuitem">{title}</a></li>;
}
