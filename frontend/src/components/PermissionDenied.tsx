import { uiRouteMap } from "@dashlive/routemap";
import { useEffect } from "preact/hooks";
import { useLocation } from "wouter-preact";
import { ErrorCard } from "./ErrorCard";

export function PermissionDenied() {
  const [, setLocation] = useLocation();

  useEffect(() => {
    const id = window.setTimeout(() => {
      setLocation(uiRouteMap.login.url());
    }, 10000);

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
