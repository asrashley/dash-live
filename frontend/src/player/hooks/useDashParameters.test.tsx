import { type ComponentChildren } from "preact";
import { afterEach, describe, expect, test, vi } from "vitest";
import { act, renderHook } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";

import { ApiRequests, EndpointContext } from "../../endpoints";
import { DashParameters } from "../types/DashParameters";
import { useDashParameters } from "./useDashParameters";

import dashParmsFixture from "../../test/fixtures/play/vod/bbb/hand_made.json";

describe("useDashParameters hook", () => {
  const apiRequests = mock<ApiRequests>();
  const mode = "vod";
  const stream = "bbb";
  const manifest = "hand_made";
  const params = new URLSearchParams({ drm: "clearkey", timeline: "1" });

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

  test("fetches DASH parameters", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getDashParameters.mockImplementation(async () => {
        resolve();
        return dashParmsFixture as unknown as DashParameters;
      });
    });
    const { result } = renderHook(
      () => useDashParameters(mode, stream, manifest, params),
      {
        wrapper,
      }
    );
    await act(async () => {
      await prom;
    });
    const { dashParams, keys, error, loaded } = result.current;
    expect(error.value).toBeNull();
    expect(loaded.value).toEqual(true);
    expect(dashParams.value).toEqual(dashParmsFixture);
    const expectedKeys = {
      "1ab45440532c439994dc5c5ad9584bac": {
        alg: "AESCTR",
        b64Key: "1tOc7e6QJMiLZOsb3WF6Rw==",
        computed: true,
        guidKid: "4054b41a-2c53-9943-94dc-5c5ad9584bac",
        key: "d6d39cedee9024c88b64eb1bdd617a47",
        kid: "1ab45440532c439994dc5c5ad9584bac",
      },
    };
    expect(Object.fromEntries(keys.value.entries())).toEqual(expectedKeys);
  });

  test("missing DASH parameters", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getDashParameters.mockImplementation(async () => {
        resolve();
        return {} as unknown as DashParameters;
      });
    });
    const { result } = renderHook(
      () => useDashParameters(mode, stream, manifest, params),
      {
        wrapper,
      }
    );
    await act(async () => {
      await prom;
    });
    const { keys } = result.current;
    expect(keys.value.size).toEqual(0);
  });
});
