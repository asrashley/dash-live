import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { act, fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ConfirmDeleteDialog } from "./ConfirmDeleteDialog";
import { AppStateType, createAppState } from "../../appState";

describe("ConfirmDeleteDialog component", () => {
  const onClose = vi.fn();
  const onConfirm = vi.fn();
  const appState: AppStateType = createAppState();

  beforeEach(() => {
    appState.dialog.value = {
      backdrop: true,
      confirmDelete: {
        name: "testname",
        confirmed: false,
      },
    };
  });

  afterEach(() => vi.clearAllMocks());

  test("should display dialog box", async () => {
    const { getByText } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} onConfirm={onConfirm} />,
      { appState }
    );
    getByText("Confirm deletion of stream");
  });

  test("can confirm", async () => {
    const { getByText } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} onConfirm={onConfirm} />,
      { appState }
    );
    const btn = getByText("Yes, I'm sure") as HTMLButtonElement;
    act(() => {
      fireEvent.click(btn);
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(onConfirm).toHaveBeenCalled();
  });

  test("can cancel", async () => {
    const { getByText } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} onConfirm={onConfirm} />,
      { appState }
    );
    const btn = getByText("Cancel") as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  test("hide when not active", async () => {
    const { container } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} onConfirm={onConfirm} />,
    );
    expect(container.innerHTML).toEqual("");
  });
});
