import { type ComponentChildren } from "preact";
import { useEffect, useMemo } from "preact/hooks";
import { Route, Switch, useLocation } from "wouter-preact";
import lazy from "preact-lazy";

import { uiRouteMap } from "@dashlive/routemap";

import { LoadingSpinner } from "./components/LoadingSpinner";
import { MessagesPanel } from "./components/MessagesPanel";
import { ModalBackdrop } from "./components/ModalBackdrop";
import { NavHeader } from "./components/NavHeader";
import { WhoAmIProvider } from "./WhoAmIProvider";

import { ApiRequests, EndpointContext } from "./endpoints";
import { AppStateContext, AppStateType, createAppState } from "./appState";
import { PageNotFound } from "./components/PageNotFound";
import { useLocalStorage } from "./hooks/useLocalStorage";
import { InitialApiTokens } from "./types/InitialApiTokens";
import { NavBarItem } from "./types/NavBarItem";

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
  tokens: InitialApiTokens;
  navbar: NavBarItem[];
  children?: ComponentChildren;
}

export function App({ children, navbar, tokens }: AppProps) {
  const setLocation = useLocation()[1];
  const { refreshToken } = useLocalStorage();
  const apiRequests = useMemo(
    () =>
      new ApiRequests({
        accessToken: refreshToken ? null : tokens.accessToken,
        refreshToken: refreshToken ?? tokens.refreshToken,
        navigate: setLocation,
      }),
    [refreshToken, setLocation, tokens]
  );
  const state: AppStateType = useMemo(() => createAppState(), []);
  const { backdrop } = state;

  useEffect(() => {
    if (backdrop.value) {
      document.body.classList.add("modal-open");
    } else {
      document.body.classList.remove("modal-open");
    }
  }, [backdrop.value]);

  return (
    <AppStateContext.Provider value={state}>
      <EndpointContext.Provider value={apiRequests}>
        <WhoAmIProvider>
          <NavHeader navbar={navbar} />
          <MessagesPanel />
          <div className="content container-fluid">
            <AppRoutes />
            {children}
          </div>
        </WhoAmIProvider>
      </EndpointContext.Provider>
      <ModalBackdrop />
    </AppStateContext.Provider>
  );
}
