import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { computed, signal } from "@preact/signals";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/renderWithProviders";
import { AppStateType } from "../../appState";
import { DialogState } from "../../types/DialogState";

import { DeleteUserDialog } from "./DeleteUserDialog";

describe("DeleteUserDialog component", () => {
  const onCancel = vi.fn();
  const onConfirm = vi.fn();
  const closeDialog = vi.fn();
  const dialog = signal<DialogState | null>(null);
  const cinemaMode = signal<boolean>(false);
  const appState: AppStateType = {
    cinemaMode,
    dialog,
    backdrop: computed(() => !!dialog.value?.backdrop),
    closeDialog,
  };
  const username = "new.user";

  beforeEach(() => {
    dialog.value = {
      backdrop: true,
      confirmDelete: {
        name: username,
        confirmed: false,
      },
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("shows dialog", () => {
    const { getBySelector, asFragment } = renderWithProviders(
      <DeleteUserDialog
        username={username}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
      { appState }
    );
    getBySelector(".modal-dialog");
    expect(asFragment()).toMatchSnapshot();
  });

  test("hides dialog", () => {
    dialog.value = {
      backdrop: false,
    };
    const { queryBySelector } = renderWithProviders(
      <DeleteUserDialog
        username={username}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
      { appState }
    );
    expect(queryBySelector(".modal-dialog")).toBeNull();
  });

  test("can confirm dialog", async () => {
    const user = userEvent.setup();
    const { getByTestId } = renderWithProviders(
      <DeleteUserDialog
        username={username}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
      { appState }
    );
    const btn = getByTestId("confirm-delete") as HTMLButtonElement;
    await user.click(btn);
    expect(onCancel).not.toHaveBeenCalled();
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  test("can cancel dialog", async () => {
    const user = userEvent.setup();
    const { getByTestId } = renderWithProviders(
      <DeleteUserDialog
        username={username}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
      { appState }
    );
    const btn = getByTestId("cancel-delete") as HTMLButtonElement;
    await user.click(btn);
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
