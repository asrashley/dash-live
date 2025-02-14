import { describe, test } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { ErrorBoundary } from "./ErrorBoundary";

function BadComponent() {
    throw new Error("bad bad bad");
    return <div />;
}

describe('ErrorBoundary component', () => {
    test('renders children when there is no error', () => {
        const { getByText } = renderWithProviders(<ErrorBoundary><h1>This is a well behaved component</h1></ErrorBoundary>);
        getByText("This is a well behaved component");
    });

    test('shows an error card if there is an error', () => {
        const { getByText } = renderWithProviders(<ErrorBoundary><BadComponent /></ErrorBoundary>);
        getByText("Oh no! Something went badly wrong...");
    });
});