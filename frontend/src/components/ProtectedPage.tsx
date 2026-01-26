import { type ComponentChildren, Fragment } from "preact";
import { useSignal, useSignalEffect } from "@preact/signals";
import { useContext } from "preact/hooks";

import { WhoAmIContext } from "../user/hooks/useWhoAmI";
import { EndpointContext } from "../endpoints";
import { LoadingSpinner } from "./LoadingSpinner";
import { PermissionDenied } from "./PermissionDenied";

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
