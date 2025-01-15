import { afterEach, describe, expect, test, vi } from "vitest";
import { act, renderHook } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";
import { type ComponentChildren } from "preact";

import { ApiRequests, EndpointContext } from "../endpoints";
import { useContentRoles, UseContentRolesHook } from "./useContentRoles";

import contentRolesFixture from "../test/fixtures/content_roles.json";

describe("useContentRoles hook", () => {
  const apiRequests = mock<ApiRequests>();

  const wrapper = ({ children }: { children: ComponentChildren }) => {
    return (
      <EndpointContext.Provider value={apiRequests}>
        {children}
      </EndpointContext.Provider>
    );
  };

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("fetches streams", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getContentRoles.mockImplementationOnce(async () => {
        resolve();
        return contentRolesFixture;
      });
    });
    const { result } = renderHook<UseContentRolesHook, void>(
      () => useContentRoles(),
      {
        wrapper,
      }
    );
    await act(async () => {
      await prom;
    });
    const { error, contentRoles, loaded } = result.current;
    expect(error.value).toBeNull();
    expect(loaded.value).toEqual(true);
    expect(contentRoles.value).toEqual(contentRolesFixture);
  });

  test("fails to fetch streams list", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getContentRoles.mockImplementationOnce(async () => {
        resolve();
        throw new Error("connection failed");
      });
    });
    const { result } = renderHook<UseContentRolesHook, void>(
      () => useContentRoles(),
      {
        wrapper,
      }
    );
    await act(async () => {
      await prom;
    });
    const { error, contentRoles, loaded } = result.current;
    expect(error.value).toEqual(
      expect.stringContaining("Failed to fetch content roles")
    );
    expect(loaded.value).toEqual(false);
    expect(contentRoles.value).toEqual({});
  });
});
