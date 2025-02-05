import { Route, Switch } from "wouter-preact";
import lazy from "preact-lazy";

import { uiRouteMap } from "@dashlive/routemap";

import { LoadingSpinner } from "./components/LoadingSpinner";
import { PageNotFound } from "./components/PageNotFound";

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
const ListUsersPage = lazy(
  () => import("./user/components/ListUsersPage"),
  LoadingSpinner
);
const EditUserPage = lazy(
  () => import("./user/components/EditUserPage"),
  LoadingSpinner
);
const ChangePasswordPage = lazy(
  () => import("./user/components/ChangePasswordPage"),
  LoadingSpinner
);

export function AppRoutes() {
  return (
    <Switch>
      <Route component={ListStreamsPage} path={uiRouteMap.listMps.route} />
      <Route component={AddStreamPage} path={uiRouteMap.addMps.route} />
      <Route component={EditStreamPage} path={uiRouteMap.editMps.route} />
      <Route component={LoginPage} path={uiRouteMap.login.route} />
      <Route component={CgiOptionsPage} path={uiRouteMap.cgiOptions.route} />
      <Route component={HomePage} path={uiRouteMap.home.route} />
      <Route component={ListUsersPage} path={uiRouteMap.listUsers.route} />
      <Route component={EditUserPage} path={uiRouteMap.editUser.route} />
      <Route component={ChangePasswordPage} path={uiRouteMap.changePassword.route} />
      <Route path="*" component={PageNotFound} />
    </Switch>
  );
}
