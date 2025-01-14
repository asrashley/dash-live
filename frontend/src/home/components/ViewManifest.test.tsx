import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock } from "vitest-mock-extended";
import fetchMock from "@fetch-mock/vitest";
import { signal } from "@preact/signals";
import log from "loglevel";

import { renderWithProviders } from "../../test/renderWithProviders";
import { FakeEndpoint } from "../../test/FakeEndpoint";
import { MockDashServer } from "../../test/MockServer";
import { useMessages, UseMessagesHook } from "../../hooks/useMessages";

import { ViewManifest } from "./ViewManifest";

vi.mock("../../hooks/useMessages", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useMessages: vi.fn(),
  };
});

describe("ViewManifest component", () => {
  const useMessagesMock = vi.mocked(useMessages);
  const messagesMock = mock<UseMessagesHook>();
  const initialUrl = signal<URL>();
  let endpoint: FakeEndpoint;
  //let server: MockDashServer;

  beforeEach(() => {
    useMessagesMock.mockReturnValue(messagesMock);
    endpoint = new FakeEndpoint(document.location.origin);
    new MockDashServer({
      endpoint,
    });
    initialUrl.value = new URL(
      "/dash/vod/bbb/hand_made.mpd",
      document.location.href
    );
  });

  afterEach(() => {
    endpoint.shutdown();
    vi.clearAllMocks();
    fetchMock.mockReset();
  });

  test("matches snapshot", async () => {
    const { asFragment, findByText, getBySelector } = renderWithProviders(
      <ViewManifest url={initialUrl} />
    );
    const inp = getBySelector("#id_mpd_url") as HTMLInputElement;
    expect(inp.value).toEqual(initialUrl.value.href);
    await findByText("urn:mpeg:dash:profile:isoff-live:2011", { exact: false });
    expect(asFragment).toMatchSnapshot();
  });

  test("shows error if manifest fetch fails", async () => {
    endpoint.setServerStatus(500);
    const prom = endpoint.addResponsePromise("get", initialUrl.value.pathname);
    const { findByText } = renderWithProviders(
      <ViewManifest url={initialUrl} />
    );
    await expect(prom).resolves.toEqual(500);
    await findByText("Fetching manifest failed", { exact: false });
    expect(messagesMock.appendMessage).toHaveBeenCalledTimes(1);
  });
});
