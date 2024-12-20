import { beforeEach, describe, expect, test, vi } from "vitest";
import { act, fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ConfirmDeleteDialog } from "./ConfirmDeleteDialog";
import { AppStateType, createAppState } from "../../appState";

describe("ConfirmDeleteDialog component", () => {
  const onClose = vi.fn();
  const userInfo = {
    isAuthenticated: true,
    groups: ["MEDIA"],
  };
  const state: AppStateType = createAppState(userInfo);

  beforeEach(() => {
    state.dialog.value = {
      backdrop: true,
      confirmDelete: {
        name: "testname",
        confirmed: false,
      },
    };
  });

  test("should display dialog box", async () => {
    const { getByText } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} />,
      { state }
    );
    getByText("Confirm deletion of stream");
  });

  test("can confirm", async () => {
    const { confirmDelete } = state.dialog.value;
    const { getByText } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} />,
      { state }
    );
    const btn = getByText("Yes, I'm sure") as HTMLButtonElement;
    act(() => {
      fireEvent.click(btn);
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(state.dialog.value).toEqual({
      backdrop: true,
      confirmDelete: {
        ...confirmDelete,
        confirmed: true,
      },
    });
  });

  test("can cancel", async () => {
    const { getByText } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} />,
      { state }
    );
    const btn = getByText("Cancel") as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalled();
  });

  test("hide when not active", async () => {
    const { container } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} />
    );
    expect(container.innerHTML).toEqual("");
  });
});
