import { type ComponentChildren, Fragment } from "preact";
import { useSignal, useSignalEffect } from "@preact/signals";
import { useContext } from "preact/hooks";

import { WhoAmIContext } from "../hooks/useWhoAmI";
import { EndpointContext } from "../endpoints";

import { LoadingSpinner } from "./LoadingSpinner";

export interface ProtectedPageProps {
    children: ComponentChildren;
}

export function ProtectedPage({children}: ProtectedPageProps) {
  const { user } = useContext(WhoAmIContext);
  const apiRequests = useContext(EndpointContext);
  const hasChecked = useSignal<boolean>(false);

  useSignalEffect(() => {
    if (!user.value.isAuthenticated && !hasChecked.value) {
      hasChecked.value = true;
      apiRequests.getUserInfo();
    }
  });

  if (!user.value.isAuthenticated) {
    return <LoadingSpinner />;
  }
  return <Fragment>{children}</Fragment>
}

