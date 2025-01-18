import { beforeEach, describe, expect, test, vi } from "vitest";
import { act, fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ConfirmDeleteDialog } from "./ConfirmDeleteDialog";
import { AppStateType, createAppState } from "../../appState";

describe("ConfirmDeleteDialog component", () => {
  const onClose = vi.fn();
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

  test("should display dialog box", async () => {
    const { getByText } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} />,
      { appState }
    );
    getByText("Confirm deletion of stream");
  });

  test("can confirm", async () => {
    const { confirmDelete } = appState.dialog.value;
    const { getByText } = renderWithProviders(
      <ConfirmDeleteDialog onClose={onClose} />,
      { appState }
    );
    const btn = getByText("Yes, I'm sure") as HTMLButtonElement;
    act(() => {
      fireEvent.click(btn);
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(appState.dialog.value).toEqual({
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
      { appState }
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
