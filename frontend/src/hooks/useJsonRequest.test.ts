import { act, renderHook } from "@testing-library/preact";
import { afterEach, describe, expect, test, vi } from "vitest";

import { useJsonRequest } from "./useJsonRequest";

describe("useJsonRequest hook", () => {
  const request = vi.fn();

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("initial state uses initialData and is not loaded", () => {
    request.mockResolvedValueOnce({ ok: true });
    const { result } = renderHook(() =>
      useJsonRequest({
        request,
        initialData: { ok: false },
        name: "example",
      })
    );

    expect(result.current.loaded.value).toBe(false);
    expect(result.current.error.value).toBeNull();
    expect(result.current.data.value).toEqual({ ok: false });
  });

  test("fetches data and sets loaded", async () => {
    const called = Promise.withResolvers<void>();
    const response = { value: 123 };

    request.mockImplementation(async () => {
      called.resolve();
      return response;
    });

    const { result } = renderHook(() =>
      useJsonRequest({
        request,
        initialData: { value: 0 },
        name: "data",
      })
    );

    await act(async () => {
      await called.promise;
    });

    expect(request).toHaveBeenCalledTimes(1);
    expect(result.current.error.value).toBeNull();
    expect(result.current.loaded.value).toBe(true);
    expect(result.current.data.value).toEqual(response);
  });

  test("sets error when request fails", async () => {
    const called = Promise.withResolvers<void>();

    request.mockImplementation(async () => {
      called.resolve();
      throw new Error("connection failed");
    });

    const { result } = renderHook(() =>
      useJsonRequest({
        request,
        initialData: { value: 0 },
        name: "widgets",
      })
    );

    await act(async () => {
      await called.promise;
    });

    expect(result.current.loaded.value).toBe(false);
    expect(result.current.data.value).toEqual({ value: 0 });
    expect(result.current.error.value).toEqual(
      expect.stringContaining("Failed to fetch widgets")
    );
  });

  test("aborts an in-flight request on unmount and does not set error", async () => {
    const aborted = Promise.withResolvers<void>();
    request.mockImplementation((signal: AbortSignal) => {
      return new Promise<void>((_resolve, reject) => {
        signal.addEventListener("abort", () => {
          aborted.resolve();
          reject(new Error("aborted"));
        });
      });
    });

    const { result, unmount } = renderHook(() =>
      useJsonRequest({
        request: request as unknown as (signal: AbortSignal) => Promise<unknown>,
        initialData: { value: 0 },
        name: "things",
      })
    );

    const { error, loaded } = result.current;

    act(() => {
      unmount();
    });

    await act(async () => {
      await aborted.promise;
    });

    expect(loaded.value).toBe(false);
    expect(error.value).toBeNull();
  });

  test("setData clones the value, sets loaded, and clears error", () => {
    request.mockResolvedValueOnce({ ok: true });
    const { result } = renderHook(() =>
      useJsonRequest({
        request,
        initialData: { nested: { value: 0 } },
        name: "example",
      })
    );

    const next = { nested: { value: 1 } };
    act(() => {
      result.current.setData(next);
    });

    next.nested.value = 999;

    expect(result.current.loaded.value).toBe(true);
    expect(result.current.error.value).toBeNull();
    expect(result.current.data.value).toEqual({ nested: { value: 1 } });
  });

  test("does not overwrite data if request returns after setData is called", async () => {
    const blocker = Promise.withResolvers<void>();
    request.mockImplementation(async () => {
      await blocker.promise;
      return { value: 123 };
    });
    const { result } = renderHook(() =>
      useJsonRequest({
        request,
        initialData: { value: 0 },
        name: "example",
      })
    );
    act(() => {
      result.current.setData({ value: 42 });
    });
    await act(async () => {
      blocker.resolve();
    });
    
    expect(result.current.loaded.value).toBe(true);
    expect(result.current.error.value).toBeNull();
    expect(result.current.data.value).toEqual({ value: 42 });
  });
});
