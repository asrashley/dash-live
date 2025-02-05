import { type ComponentChildren, Fragment } from "preact";
import { useSignalEffect } from "@preact/signals";
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

  useSignalEffect(() => {
    if (!user.value.isAuthenticated) {
      apiRequests.getUserInfo();
    }
  });

  if (!user.value.isAuthenticated) {
    return <LoadingSpinner />;
  }
  return <Fragment>{children}</Fragment>
}

