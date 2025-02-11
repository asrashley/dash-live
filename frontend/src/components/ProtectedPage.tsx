import { type ComponentChildren, Fragment } from "preact";
import { useSignalEffect } from "@preact/signals";
import { useContext, useEffect, useRef } from "preact/hooks";

import { WhoAmIContext } from "../hooks/useWhoAmI";
import { EndpointContext } from "../endpoints";

import { LoadingSpinner } from "./LoadingSpinner";
import { useLocation } from "wouter-preact";
import { uiRouteMap } from "@dashlive/routemap";
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
  const hasChecked = useRef<boolean>(false);

  useSignalEffect(() => {
    if (!user.value.isAuthenticated && !hasChecked.current) {
      hasChecked.current = true;
      apiRequests.getUserInfo();
    }
  });

  if (!user.value.isAuthenticated && !optional && hasChecked.current) {
    return <PermissionDenied />;
  }

  if (user.value.isAuthenticated || (optional && hasChecked.current)) {
    return <Fragment>{children}</Fragment>;
  }
  return <LoadingSpinner />;
}
