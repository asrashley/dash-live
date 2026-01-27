import { Fragment, type ComponentChildren } from "preact";
import { useComputed, type ReadonlySignal } from "@preact/signals";

import { LoadingSpinner } from "./LoadingSpinner";
import { ErrorCard } from "./ErrorCard";

export interface LoadingSuspenseProps {
  loaded: ReadonlySignal<boolean>;
  error: ReadonlySignal<string | null | undefined>;
  heading?: ReadonlySignal<string> | string;
  action: string;
  children?: ComponentChildren;
}

export function LoadingSuspense({ action, heading, loaded, error, children }: LoadingSuspenseProps) {
  const header = useComputed<string>(() => heading ? typeof heading === "string" ? heading : heading.value : action);
  if (error.value) {
    return (
      <ErrorCard id="loading-suspense" header={header}>
        <p>{action} failed: {error.value}</p>
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
