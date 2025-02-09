import { type ComponentChildren } from "preact";
import { useErrorBoundary } from "preact/hooks";
import { ErrorCard } from "./ErrorCard";

export interface ErrorBoundaryProps {
    children: ComponentChildren;
}

export function ErrorBoundary({children}: ErrorBoundaryProps) {
  const [error, resetError] = useErrorBoundary();

  if (error) {
    return (
      <ErrorCard id="error-boundary" header="Something went wrong">
        <p>Oh no! Something went badly wrong and useErrorBoundary was used</p>
        <pre>{error.message}</pre>

        <button onClick={resetError}>Try again</button>
      </ErrorCard>
    );
  }

  return children;
}