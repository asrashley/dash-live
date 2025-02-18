import { type ComponentChildren, Fragment } from "preact";
import { useSignal, useSignalEffect } from "@preact/signals";
import { useContext, useEffect } from "preact/hooks";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";

import { WhoAmIContext } from "../user/hooks/useWhoAmI";
import { EndpointContext } from "../endpoints";
import { LoadingSpinner } from "./LoadingSpinner";
import { ErrorCard } from "./ErrorCard";

function PermissionDenied() {
  const [, setLocation] = useLocation();

  useEffect(() => {
    const id = window.setTimeout(() => {
      setLocation(uiRouteMap.login.url());
    }, 10_000);

    return () => {
      window.clearTimeout(id);
    };
  });

  return (
    <ErrorCard
      id="permission-denied"
      header="You need to log in to access this page">
      <p className="fs-3">
        This page is only available for users who have logged in.
      </p>
      <p className="fs-4">
        Probably a good idea to{" "}
        <a href={uiRouteMap.login.url()} className="link link-underline-light">
          go to the login page
        </a>
        .
      </p>
    </ErrorCard>
  );
}

export interface ProtectedPageProps {
  children: ComponentChildren;
  optional?: boolean;
}

export function ProtectedPage({
  children,
  optional = false,
}: ProtectedPageProps) {
  const { user } = useContext(WhoAmIContext);
  const apiRequests = useContext(EndpointContext);
  const hasChecked = useSignal<boolean>(false);

  useSignalEffect(() => {
    if (!user.value.isAuthenticated && !hasChecked.value) {
      apiRequests.getUserInfo().finally(() => {
        hasChecked.value = true;
      });
    }
  });

  if (!user.value.isAuthenticated && !optional && hasChecked.value) {
    return <PermissionDenied />;
  }

  if (user.value.isAuthenticated || (optional && hasChecked.value)) {
    return <Fragment>{children}</Fragment>;
  }
  return <LoadingSpinner />;
}
