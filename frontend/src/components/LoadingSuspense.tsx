import { Fragment, type ComponentChildren } from "preact";
import { type ReadonlySignal } from "@preact/signals";

import { LoadingSpinner } from "./LoadingSpinner";
import { ErrorCard } from "./ErrorCard";

export interface LoadingSuspenseProps {
  loaded: ReadonlySignal<boolean>;
  error: ReadonlySignal<string | null | undefined>;
  action: string;
  children?: ComponentChildren;
}

export function LoadingSuspense({ action, loaded, error, children }) {
  if (error.value) {
    return (
      <ErrorCard id="loading-suspense" header={action}>
        <p>Failed to {action}: {error.value}</p>
      </ErrorCard>
    );
  }
  if (!loaded.value) {
    return (
      <div id="loading-suspense">
        <h2 className="title">{action}...</h2>
        <LoadingSpinner />
      </div>
    );
  }
  return <Fragment>{children}</Fragment>;
}
