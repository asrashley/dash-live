import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { signal } from "@preact/signals";
import { fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../test/renderWithProviders";
import { MessagesPanel } from "./MessagesPanel";
import { useMessages } from "../hooks/useMessages";
import { MessageType } from "../types/MessageType";

vi.mock("../hooks/useMessages");

describe("MessagesPanel", () => {
  const useMessagesMock = vi.mocked(useMessages);
  const appendMessage = vi.fn();
  const removeAlert = vi.fn();
  const alerts = signal<MessageType[]>([]);

  beforeEach(() => {
    useMessagesMock.mockReturnValue({ alerts, appendMessage, removeAlert });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should display messages", () => {
    alerts.value = [
      {
        text: "alert message one",
        id: 12,
        level: "warning",
      },
      {
        text: "message two",
        id: 23,
        level: "info",
      },
    ];
    const { asFragment, getBySelector, getByText } = renderWithProviders(
      <MessagesPanel />
    );
    getBySelector(".messages-panel");
    getByText(alerts.value[0].text);
    getByText(alerts.value[1].text);
    expect(asFragment()).toMatchSnapshot();
  });

  test("can dismiss message", () => {
    alerts.value = [
      {
        text: "alert message one",
        id: 12,
        level: "warning",
      },
    ];
    const { getBySelector } = renderWithProviders(<MessagesPanel />);

    const btn = getBySelector("#alert_12 .btn-close");
    fireEvent.click(btn);
    expect(removeAlert).toHaveBeenCalledTimes(1);
    expect(removeAlert).toHaveBeenCalledWith(12);
  });
});
