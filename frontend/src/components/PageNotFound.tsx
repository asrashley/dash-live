import { uiRouteMap } from "@dashlive/routemap";
import { ErrorCard } from "./ErrorCard";

export function PageNotFound() {
  return (
    <ErrorCard
      id="page-not-found"
      header="Sorry I don't know about this page"
    >
          <p className="fs-3">
            This page might have moved, or it might be a bug in this site.
          </p>
          <p className="fs-4">
            Probably a good idea to{" "}
            <a href={uiRouteMap.home.url()} className="link link-underline-light">
              return to the home page
            </a>
            .
          </p>
    </ErrorCard>
  );
}
