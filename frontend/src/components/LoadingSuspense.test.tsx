import { describe, expect, test } from "vitest";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../test/renderWithProviders";
import { LoadingSuspense } from "./LoadingSuspense";

describe("LoadingSuspense", () => {
  test("shows ErrorCard when error is set (even if loaded)", () => {
    const loaded = signal(true);
    const error = signal<string | null>("server exploded");

    const { asFragment, getByText, queryBySelector } = renderWithProviders(
      <LoadingSuspense action="Load widgets" loaded={loaded} error={error}>
        <p>Child content</p>
      </LoadingSuspense>
    );

    getByText("Failed to Load widgets: server exploded");
    expect(document.getElementById("loading-suspense")).not.toBeNull();
    expect(queryBySelector(".lds-ring")).toBeNull();
    expect(queryBySelector(".title")).toBeNull();
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows title and spinner while not loaded", () => {
    const loaded = signal(false);
    const error = signal<string | null>(null);

    const { asFragment, getByText, getBySelector } =
      renderWithProviders(
      <LoadingSuspense action="Fetching data" loaded={loaded} error={error}>
        <p>Child content</p>
      </LoadingSuspense>
    );

    getByText("Fetching data...");
    getBySelector("#loading-suspense");
    getBySelector(".lds-ring");
    expect(asFragment()).toMatchSnapshot();
  });

  test("renders children when loaded and no error", () => {
    const loaded = signal(true);
    const error = signal<string | null>(null);

    const { getByText, queryBySelector } = renderWithProviders(
      <LoadingSuspense action="Fetching data" loaded={loaded} error={error}>
        <p>Child content</p>
      </LoadingSuspense>
    );

    getByText("Child content");
    expect(queryBySelector("#loading-suspense")).toBeNull();
    expect(queryBySelector(".lds-ring")).toBeNull();
  });
});
