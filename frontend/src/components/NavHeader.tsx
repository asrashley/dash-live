import { NavBarItem } from "../types/NavBarItem";
import { BreadCrumbs } from "./BreadCrumbs";
import { NavBar } from "./NavBar";

export interface NavHeaderProps {
  navbar: NavBarItem[];
}
export function NavHeader({ navbar }: NavHeaderProps) {
  return (
    <header>
      <NavBar items={navbar} />
      <BreadCrumbs />
    </header>
  );
}
