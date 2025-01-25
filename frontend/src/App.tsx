import { type ComponentChildren } from "preact";
import { useCallback, useMemo, useRef } from "preact/hooks";
import { useSignalEffect } from "@preact/signals";
import { Route, Switch, useLocation } from "wouter-preact";
import lazy from "preact-lazy";

import { uiRouteMap } from "@dashlive/routemap";

import { LoadingSpinner } from "./components/LoadingSpinner";
import { MessagesPanel } from "./components/MessagesPanel";
import { ModalBackdrop } from "./components/ModalBackdrop";
import { NavHeader } from "./components/NavHeader";
import { PageNotFound } from "./components/PageNotFound";

import { ApiRequests, EndpointContext } from "./endpoints";
import { AppStateContext, AppStateType, createAppState } from "./appState";
import { useLocalStorage } from "./hooks/useLocalStorage";
import { NavBarItem } from "./types/NavBarItem";
import { useWhoAmI, WhoAmIContext } from "./hooks/useWhoAmI";

const AddStreamPage = lazy(
  () => import("./mps/components/AddStreamPage"),
  LoadingSpinner
);
const EditStreamPage = lazy(
  () => import("./mps/components/EditStreamPage"),
  LoadingSpinner
);
const HomePage = lazy(
  () => import("./home/components/HomePage"),
  LoadingSpinner
);
const ListStreamsPage = lazy(
  () => import("./mps/components/ListStreamsPage"),
  LoadingSpinner
);
const LoginPage = lazy(
  () => import("./user/components/LoginPage"),
  LoadingSpinner
);
const CgiOptionsPage = lazy(
  () => import("./cgi/components/CgiOptionsPage"),
  LoadingSpinner
);

function AppRoutes() {
  return (
    <Switch>
      <Route component={ListStreamsPage} path={uiRouteMap.listMps.route} />
      <Route component={AddStreamPage} path={uiRouteMap.addMps.route} />
      <Route component={EditStreamPage} path={uiRouteMap.editMps.route} />
      <Route component={LoginPage} path={uiRouteMap.login.route} />
      <Route component={CgiOptionsPage} path={uiRouteMap.cgiOptions.route} />
      <Route component={HomePage} path={uiRouteMap.home.route} />
      <Route path="*" component={PageNotFound} />
    </Switch>
  );
}

export interface AppProps {
  navbar: NavBarItem[];
  children?: ComponentChildren;
}

export function App({ children, navbar }: AppProps) {
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
          <NavHeader navbar={navbar} />
          <MessagesPanel />
          <div className="content container-fluid">
            <AppRoutes />
            {children}
          </div>
        </EndpointContext.Provider>
      </WhoAmIContext.Provider>
      <ModalBackdrop />
    </AppStateContext.Provider>
  );
}
