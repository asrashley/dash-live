import { afterAll, beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook, act } from "@testing-library/preact";

import { useMessages, resetAllMessages } from "./useMessages.js";

describe("useMessages hook", () => {
  beforeEach(() => {
    resetAllMessages();
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  test("initial state", () => {
    const { result, rerender } = renderHook(() => useMessages());
    const { appendMessage, removeAlert } = result.current;
    expect(result.current.alerts.value).toEqual([]);
    expect(appendMessage).toBeInstanceOf(Function);
    expect(removeAlert).toBeInstanceOf(Function);
    act(() => {
      rerender();
    });
    expect(result.current.appendMessage).toStrictEqual(appendMessage);
    expect(result.current.removeAlert).toStrictEqual(removeAlert);
  });

  test("can add a message", () => {
    const { result } = renderHook(() => useMessages());
    const { appendMessage } = result.current;
    appendMessage("this is a message");
    expect(result.current.alerts.value).toEqual([
      {
        id: 1,
        text: "this is a message",
        level: "warning",
      },
    ]);
    appendMessage("second message", "info");
    expect(result.current.alerts.value).toEqual([
      {
        id: 1,
        text: "this is a message",
        level: "warning",
      },
      {
        id: 2,
        text: "second message",
        level: "info",
      },
    ]);
  });

  test("can remove a message", () => {
    const { result } = renderHook(() => useMessages());
    const { appendMessage, removeAlert } = result.current;
    appendMessage("this is a message");
    expect(result.current.alerts.value).toEqual([
      {
        id: 1,
        text: "this is a message",
        level: "warning",
      },
    ]);
    removeAlert(5);
    expect(result.current.alerts.value.length).toEqual(1);
    removeAlert(1);
    expect(result.current.alerts.value).toEqual([]);
  });
});
