import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { computed, signal } from "@preact/signals";
import userEvent from "@testing-library/user-event";
import { mock } from "vitest-mock-extended";

import { renderWithProviders } from "../../test/renderWithProviders";
import { AddUserDialog } from "./AddUserDialog";
import { AppStateType } from "../../appState";
import { DialogState } from "../../types/DialogState";
import { UserValidationErrors } from "../hooks/useAllUsers";
import { InitialUserState } from "../types/InitialUserState";
import { useMessages, UseMessagesHook } from "../../hooks/useMessages";
import { validateUserState } from "../utils/validateUserState";

vi.mock("../../hooks/useMessages");

describe("AddUserDialog component", () => {
  const onClose = vi.fn();
  const saveChanges = vi.fn();
  const validateUser = vi.fn();
  const closeDialog = vi.fn();
  const dialog = signal<DialogState | null>(null);
  const allUsers = signal<InitialUserState[]>([]);
  const appState: AppStateType = {
    dialog,
    backdrop: computed(() => !!dialog.value?.backdrop),
    closeDialog,
  };
  const useMessagesSpy = vi.mocked(useMessages);
  const useMessagesHook = mock<UseMessagesHook>();

  const username = "new.username";
  const email = "new.username@test.local";

  beforeEach(() => {
    validateUser.mockImplementation((user) =>
      validateUserState(user, allUsers.value)
    );
    saveChanges.mockResolvedValue("");
    useMessagesSpy.mockReturnValue(useMessagesHook);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("shows dialog", () => {
    dialog.value = {
      backdrop: true,
      addUser: {
        active: true,
      },
    };
    const { getBySelector } = renderWithProviders(
      <AddUserDialog
        onClose={onClose}
        saveChanges={saveChanges}
        validateUser={validateUser}
      />,
      { appState }
    );
    getBySelector(".modal-dialog");
  });

  test("hides  dialog", () => {
    dialog.value = {
      backdrop: false,
    };
    const { queryBySelector } = renderWithProviders(
      <AddUserDialog
        onClose={onClose}
        saveChanges={saveChanges}
        validateUser={validateUser}
      />,
      { appState }
    );
    expect(queryBySelector(".modal-dialog")).toBeNull();
  });

  test("can close dialog", async () => {
    const user = userEvent.setup();
    dialog.value = {
      backdrop: true,
      addUser: {
        active: true,
      },
    };
    const { getByTestId } = renderWithProviders(
      <AddUserDialog
        onClose={onClose}
        saveChanges={saveChanges}
        validateUser={validateUser}
      />,
      { appState }
    );
    const btn = getByTestId("cancel-new-user-btn") as HTMLButtonElement;
    await user.click(btn);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(saveChanges).not.toHaveBeenCalled();
  });

  test.each([true, false])("can create a user, success=%s", async (success: boolean) => {
    const user = userEvent.setup();
    saveChanges.mockResolvedValue(success ? "" : "a server error message");
    dialog.value = {
      backdrop: true,
      addUser: {
        active: true,
      },
    };
    const { findByText, findBySelector, getByTestId, queryByText } = renderWithProviders(
      <AddUserDialog
        onClose={onClose}
        saveChanges={saveChanges}
        validateUser={validateUser}
      />,
      { appState }
    );
    expect(saveChanges).not.toHaveBeenCalled();
    const saveBtn = getByTestId("add-new-user-btn") as HTMLButtonElement;
    expect(saveBtn.disabled).toEqual(true);
    const btn = (await findByText("Add New User")) as HTMLButtonElement;
    await user.click(btn);
    await findBySelector(".modal-dialog");
    const userInp = (await findBySelector(
      'input[name="username"]'
    )) as HTMLInputElement;
    await user.clear(userInp);
    await user.type(userInp, username);
    expect(saveChanges).not.toHaveBeenCalled();
    const emailInp = (await findBySelector(
      'input[name="email"]'
    )) as HTMLInputElement;
    await user.clear(emailInp);
    await user.type(emailInp, email);
    expect(saveBtn.disabled).toEqual(false);
    expect(saveChanges).not.toHaveBeenCalled();
    const pwdInp = (await findBySelector(
      'input[name="password"]'
    )) as HTMLInputElement;
    const password = pwdInp.value;
    const confirmInp = (await findBySelector(
      'input[name="confirmPassword"]'
    )) as HTMLInputElement;
    expect(confirmInp.value).toEqual(password);
    expect(saveChanges).not.toHaveBeenCalled();
    await user.click(saveBtn);
    expect(saveChanges).toHaveBeenCalledTimes(1);
    expect(saveChanges).toHaveBeenCalledWith({
      email,
      username,
      password,
      adminGroup: false,
      confirmPassword: password,
      lastLogin: null,
      mediaGroup: false,
      mustChange: true,
      userGroup: true,
    });
    if (success) {
        expect(useMessagesHook.appendMessage).toHaveBeenCalledTimes(1);
        expect(useMessagesHook.appendMessage).toHaveBeenCalledWith('success', `Added new user "${username}"`);
    } else {
        expect(useMessagesHook.appendMessage).not.toHaveBeenCalled();
        await findByText("a server error message", { exact: false });
        const dismiss = await findBySelector('.alert .btn-close') as HTMLButtonElement;
        await user.click(dismiss);
        expect(queryByText("a server error message", { exact: false })).toBeNull();
    }
  });

  test("shows validation errors", async () => {
    dialog.value = {
      backdrop: true,
      addUser: {
        active: true,
      },
    };
    const errs: UserValidationErrors = {
      username: `${username} already exists`,
      password: "passwords do not match",
      email: `${email} email address already exists`,
    };
    validateUser.mockReturnValue(errs);
    const { findByText } = renderWithProviders(
      <AddUserDialog
        onClose={onClose}
        saveChanges={saveChanges}
        validateUser={validateUser}
      />,
      { appState }
    );
    await findByText(errs.username);
    await findByText(errs.email);
    await findByText(errs.password);
  });
});
