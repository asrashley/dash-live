import { BreadCrumbs } from "./BreadCrumbs";
import { ErrorBoundary } from "../../components/ErrorBoundary";
import { NavBar } from "./NavBar";

export function NavHeader() {
  return (
    <ErrorBoundary>
      <header>
        <NavBar />
        <BreadCrumbs />
      </header>
    </ErrorBoundary>
  );
}
