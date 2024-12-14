import { beforeEach, describe, expect, test, vi } from "vitest";
import { act, fireEvent } from "@testing-library/preact";
import { html } from "htm/preact";

import { renderWithProviders } from "../../../test/renderWithProviders.js";
import { ConfirmDeleteDialog } from "./ConfirmDeleteDialog.js";
import { createAppState } from "../../appState.js";

describe("ConfirmDeleteDialog component", () => {
  const onClose = vi.fn();
  const userInfo = {
    isAuthenticated: true,
    groups: ["MEDIA"],
  };
  const state = createAppState(userInfo);

  beforeEach(() => {
    state.dialog.value = {
      confirmDelete: {
        name: "testname",
        confirmed: false,
      },
    };
  });

  test("should display dialog box", async () => {
    const { getByText } = renderWithProviders(
      html`<${ConfirmDeleteDialog} onClose=${onClose} />`,
      { state }
    );
    getByText("Confirm deletion of stream");
  });

  test("can confirm", async () => {
    const { confirmDelete } = state.dialog.value;
    const { getByText } = renderWithProviders(
      html`<${ConfirmDeleteDialog} onClose=${onClose} />`,
      { state }
    );
    const btn = getByText("Yes, I'm sure");
    act(() => {
      fireEvent.click(btn);
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(state.dialog.value).toEqual({
      confirmDelete: {
        ...confirmDelete,
        confirmed: true,
      },
    });
  });

  test("can cancel", async () => {
    const { getByText } = renderWithProviders(
      html`<${ConfirmDeleteDialog} onClose=${onClose} />`,
      { state }
    );
    const btn = getByText("Cancel");
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalled();
  });

  test("hide when not active", async () => {
    const { container } = renderWithProviders(
      html`<${ConfirmDeleteDialog} onClose=${onClose} />`
    );
    expect(container.innerHTML).toEqual("");
  });
});
