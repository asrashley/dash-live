import { afterEach, describe, expect, test, vi } from "vitest";
import { act, renderHook } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";
import { type ComponentChildren } from "preact";

import { ApiRequests, EndpointContext } from "../endpoints";

import cgiOptionsFixture from '../test/fixtures/cgiOptions.json';
import { useCgiOptions, UseCgiOptionsHook } from "./useCgiOptions";
import { CgiOptionDescription } from "../types/CgiOptionDescription";

describe("useCgiOptions hook", () => {
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

  test("fetches CGI options", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getCgiOptions.mockImplementationOnce(async () => {
        resolve();
        return cgiOptionsFixture as CgiOptionDescription[];
      });
    });
    const { result } = renderHook<UseCgiOptionsHook, void>(
      () => useCgiOptions(),
      {
        wrapper,
      }
    );
    await act(async () => {
      await prom;
    });
    const { error, allOptions, loaded } = result.current;
    expect(error.value).toBeNull();
    expect(loaded.value).toEqual(true);
    expect(allOptions.value).toEqual(cgiOptionsFixture);
  });

  test("fails to fetch streams list", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getCgiOptions.mockImplementationOnce(async () => {
        resolve();
        throw new Error("connection failed");
      });
    });
    const { result } = renderHook(() => useCgiOptions(),
      {
        wrapper,
      }
    );
    await act(async () => {
      await prom;
    });
    const { error, allOptions, loaded } = result.current;
    expect(error.value).toEqual(
      expect.stringContaining("Failed to fetch CGI options")
    );
    expect(loaded.value).toEqual(false);
    expect(allOptions.value).toEqual([]);
  });
});
