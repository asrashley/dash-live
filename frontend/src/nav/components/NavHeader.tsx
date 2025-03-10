import { useComputed, useSignal, useSignalEffect } from "@preact/signals";
import { useCallback, useContext, useEffect, useRef } from "preact/hooks";

import { BreadCrumbs } from "./BreadCrumbs";
import { ErrorBoundary } from "../../components/ErrorBoundary";
import { NavBar } from "./NavBar";
import { AppStateContext } from "../../appState";

export function NavHeader() {
  const menuVisible = useSignal<boolean>(true);
  const hideMenuTimer = useRef<number | undefined>(undefined);
  const { cinemaMode } = useContext(AppStateContext);
  const className = useComputed<string>(() =>
    menuVisible.value ? "" : "rollup"
  );

  const hideMenu = useCallback(() => {
    hideMenuTimer.current = null;
    menuVisible.value = !cinemaMode.value;
  }, [cinemaMode.value, menuVisible]);

  const showMenu = useCallback(() => {
    menuVisible.value = true;
    window.clearTimeout(hideMenuTimer.current);
    hideMenuTimer.current = undefined;
  }, [menuVisible]);

  const startHideMenu = useCallback(() => {
    if (!hideMenuTimer.current && cinemaMode.value) {
      hideMenuTimer.current = window.setTimeout(hideMenu, 1000);
    }
  }, [cinemaMode, hideMenu]);

  useSignalEffect(() => {
    if (cinemaMode.value) {
      startHideMenu();
    } else {
      showMenu();
    }
  });

  useEffect(() => {
    return () => {
      window.clearTimeout(hideMenuTimer.current);
    };
  }, []);

  return (
    <ErrorBoundary>
      <header className={className} onMouseEnter={showMenu} onMouseLeave={startHideMenu}>
        <NavBar />
        <BreadCrumbs />
      </header>
    </ErrorBoundary>
  );
}
