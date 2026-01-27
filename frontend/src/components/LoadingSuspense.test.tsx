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

    getByText("Load widgets failed: server exploded");
    expect(document.getElementById("loading-suspense")).not.toBeNull();
    expect(queryBySelector(".lds-ring")).toBeNull();
    expect(queryBySelector(".title")).toBeNull();
    expect(asFragment()).toMatchSnapshot();
  });

  test("can set a heading string for the error card", () => {
    const loaded = signal(true);
    const error = signal<string | null>("server exploded");

    const { asFragment, getByText, queryBySelector } = renderWithProviders(
      <LoadingSuspense action="Load widgets" heading="my custom heading" loaded={loaded} error={error}>
        <p>Child content</p>
      </LoadingSuspense>
    );

    getByText("Load widgets failed: server exploded");
    getByText("my custom heading");
    expect(document.getElementById("loading-suspense")).not.toBeNull();
    expect(queryBySelector(".lds-ring")).toBeNull();
    expect(queryBySelector(".title")).toBeNull();
    expect(asFragment()).toMatchSnapshot();
  });

  test("can use a signal to a heading for the error card", () => {
    const loaded = signal(true);
    const error = signal<string | null>("server exploded");
    const heading = signal<string>("my custom heading via signal");

    const { asFragment, getByText, queryBySelector } = renderWithProviders(
      <LoadingSuspense action="Load widgets" heading={heading} loaded={loaded} error={error}>
        <p>Child content</p>
      </LoadingSuspense>
    );

    getByText("Load widgets failed: server exploded");
    getByText("my custom heading via signal");
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
