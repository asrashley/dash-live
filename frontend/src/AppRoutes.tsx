import { Route, Switch } from "wouter-preact";
import lazy from "preact-lazy";

import { uiRouteMap } from "@dashlive/routemap";

import { LoadingSpinner } from "./components/LoadingSpinner";
import { PageNotFound } from "./components/PageNotFound";

interface PageFallbackProps {
  component: string;
}
function PageFallback({ component }: PageFallbackProps) {
  return <div id="loading-suspense">
    <h2 className="title">Loading {component} component...</h2>
    <LoadingSpinner />
  </div>;
}

function AddStreamPageFallback() {
  return <PageFallback component="add multi-period stream" />;
}
const AddStreamPage = lazy(
  () => import("./mps/components/AddStreamPage"),
  AddStreamPageFallback
);

function EditStreamPageFallback() {
  return <PageFallback component="edit multi-period stream" />;
}
const EditStreamPage = lazy(
  () => import("./mps/components/EditStreamPage"),
  EditStreamPageFallback
);

function HomePageFallback() {
  return <PageFallback component="home page" />;
}
const HomePage = lazy(
  () => import("./home/components/HomePage"),
  HomePageFallback
);

function ListMpsPageFallback() {
  return <PageFallback component="browse multi-period streams" />;
}
const ListStreamsPage = lazy(
  () => import("./mps/components/ListStreamsPage"),
  ListMpsPageFallback
);

function LoginPageFallback() {
  return <PageFallback component="login" />;
}
const LoginPage = lazy(
  () => import("./user/components/LoginPage"),
  LoginPageFallback
);

function CgiOptionsPageFallback() {
  return <PageFallback component="cgi options" />;
}
const CgiOptionsPage = lazy(
  () => import("./cgi/components/CgiOptionsPage"),
  CgiOptionsPageFallback
);

function ListUsersPageFallback() {
  return <PageFallback component="list users" />;
}
const ListUsersPage = lazy(
  () => import("./user/components/ListUsersPage"),
  ListUsersPageFallback
);

function EditUserPageFallback() {
  return <PageFallback component="edit user" />;
}
const EditUserPage = lazy(
  () => import("./user/components/EditUserPage"),
  EditUserPageFallback
);

function ChangePasswordPageFallback() {
  return <PageFallback component="change password" />;
}
const ChangePasswordPage = lazy(
  () => import("./user/components/ChangePasswordPage"),
  ChangePasswordPageFallback
);

function ValidatorPageFallback() {
  return <PageFallback component="stream validator" />;
}
const ValidatorPage = lazy(
  () => import("./validator/components/ValidatorPage"),
  ValidatorPageFallback
);

function VideoPlayerFallback() {
  return <PageFallback component="video player" />;
}
const VideoPlayer = lazy(
  () => import("./player/components/VideoPlayerPage"),
  VideoPlayerFallback
);

export function AppRoutes() {
  return (
    <Switch>
      <Route component={ListStreamsPage} path={uiRouteMap.listMps.route} />
      <Route component={AddStreamPage} path={uiRouteMap.addMps.route} />
      <Route component={EditStreamPage} path={uiRouteMap.editMps.route} />
      <Route component={LoginPage} path={uiRouteMap.login.route} />
      <Route component={CgiOptionsPage} path={uiRouteMap.cgiOptions.route} />
      <Route component={ListUsersPage} path={uiRouteMap.listUsers.route} />
      <Route component={EditUserPage} path={uiRouteMap.editUser.route} />
      <Route component={ChangePasswordPage} path={uiRouteMap.changePassword.route} />
      <Route component={ValidatorPage} path={uiRouteMap.validator.route} />
      <Route component={VideoPlayer} path={uiRouteMap.video.route} />
      <Route component={HomePage} path={uiRouteMap.home.route} />
      <Route path="*" component={PageNotFound} />
    </Switch>
  );
}
