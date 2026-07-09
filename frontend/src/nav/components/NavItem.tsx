import { Link, useLocation } from "wouter-preact";
import type { NavBarItem } from "../types/NavBarItem";


interface LinkOrAnchorProps {
  title: string;
  href: string;
  external: boolean;
  className: string;
}
function LinkOrAnchor({ href, external, title, className }: LinkOrAnchorProps) {
  if (external) {
    return <a href={href} role="menuitem" className={className}>{title}</a>;
  }
  return <Link href={href} role="menuitem" className={className}>{title}</Link>;
}

export type NavItemProps = NavBarItem & {
  external: boolean;
};

export function NavItem({ className = '', href, title, external }: NavItemProps) {
  const [location] = useLocation();
  const itemClassName = `nav-item ${className}`;
  const active = location === href;
  const linkClass = `nav-link${active ? " active" : ""} ${className}`;

    return <li className={itemClassName}>
      <LinkOrAnchor href={href} external={external} title={title} className={linkClass} />
    </li>;
}
