import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { MessagesPanel } from "./MessagesPanel.js";
import { useMessages } from "../hooks/useMessages.js";
import { fireEvent } from "@testing-library/preact";

vi.mock("../hooks/useMessages.js");

describe("MessagesPanel", () => {
  const useMessagesMock = vi.mocked(useMessages);
  const removeAlert = vi.fn();
  const alerts = signal([]);

  beforeEach(() => {
    useMessagesMock.mockReturnValue({ alerts, removeAlert });
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
      html`<${MessagesPanel} />`
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
    const { getBySelector } = renderWithProviders(html`<${MessagesPanel} />`);

    const btn = getBySelector("#alert_12 .btn-close");
    fireEvent.click(btn);
    expect(removeAlert).toHaveBeenCalledTimes(1);
    expect(removeAlert).toHaveBeenCalledWith(12);
  });
});
