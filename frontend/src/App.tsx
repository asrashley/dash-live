import { type ComponentChildren } from "preact";
import { useCallback, useMemo, useRef } from "preact/hooks";
import { useSignalEffect } from "@preact/signals";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";

import { MessagesPanel } from "./components/MessagesPanel";
import { ModalBackdrop } from "./components/ModalBackdrop";
import { NavHeader } from "./nav/components/NavHeader";

import { ApiRequests, EndpointContext } from "./endpoints";
import { AppStateContext, AppStateType, createAppState } from "./appState";
import { useLocalStorage } from "./hooks/useLocalStorage";
import { useWhoAmI, WhoAmIContext } from "./user/hooks/useWhoAmI";
import { Footer } from "./components/Footer";
import { AppRoutes } from "./AppRoutes";

export interface AppProps {
  children?: ComponentChildren;
}

export function App({ children }: AppProps) {
  const setLocation = useLocation()[1];
  const { refreshToken } = useLocalStorage();
  const whoAmI = useWhoAmI();
  const needsRefreshToken = useCallback(() => {
    setLocation(uiRouteMap.login.url());
  }, [setLocation]);
  const apiRequests = useRef(new ApiRequests({ hasUserInfo: whoAmI.setUser, needsRefreshToken }));
  const state: AppStateType = useMemo(() => createAppState(), []);
  const { backdrop } = state;

  useSignalEffect(() => {
    if (backdrop.value) {
      document.body.classList.add("modal-open");
    } else {
      document.body.classList.remove("modal-open");
    }
  });

  useSignalEffect(() => {
    apiRequests.current.setRefreshToken(refreshToken.value);
  });

  return (
    <AppStateContext.Provider value={state}>
      <WhoAmIContext.Provider value={whoAmI}>
        <EndpointContext.Provider value={apiRequests.current}>
          <NavHeader />
          <MessagesPanel />
          <div className="content container-fluid">
            <AppRoutes />
            {children}
          </div>
          <Footer />
        </EndpointContext.Provider>
      </WhoAmIContext.Provider>
      <ModalBackdrop />
    </AppStateContext.Provider>
  );
}
