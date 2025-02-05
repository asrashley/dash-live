import { BreadCrumbs } from "./BreadCrumbs";
import { NavBar } from "./NavBar";

export function NavHeader() {
  return (
    <header>
      <NavBar />
      <BreadCrumbs />
    </header>
  );
}
