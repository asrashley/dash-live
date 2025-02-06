import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock } from "vitest-mock-extended";
import userEvent from "@testing-library/user-event";
import { useLocation } from "wouter-preact";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../../endpoints";
import { useMessages, UseMessagesHook } from "../../hooks/useMessages";
import { normalUser, UserModel } from "../../test/MockServer";
import { ModifyUserResponse } from "../../types/ModifyUserResponse";
import { EditUserState } from "../../types/EditUserState";

import ChangePasswordPage, { ChangePassword } from "./ChangePasswordPage";

vi.mock("wouter-preact", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useLocation: vi.fn(),
  };
});

vi.mock("../../hooks/useMessages", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useMessages: vi.fn(),
  };
});

describe("ChangePassword component", () => {
  const useLocationMock = vi.mocked(useLocation);
  const useMessagesMock = vi.mocked(useMessages);
  const setLocation = vi.fn();
  const apiRequests = mock<ApiRequests>();
  const messagesMock = mock<UseMessagesHook>();
  const userInfo: UserModel = {
    pk: normalUser.pk,
    username: normalUser.username,
    email: normalUser.email,
    password: "",
    mustChange: false,
    lastLogin: "",
    groups: normalUser.groups,
    refreshToken: null,
    accessToken: null,
  };

  beforeEach(() => {
    useLocationMock.mockReturnValue(["/change-password", setLocation]);
    useMessagesMock.mockReturnValue(messagesMock);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("ChangePassword component matches snapshot", () => {
    const { asFragment, getByText, getByLabelText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <ChangePassword />
      </EndpointContext.Provider>,
      { userInfo }
    );
    getByText("Change my password");
    const emailInp = getByLabelText("Email:") as HTMLInputElement;
    expect(emailInp.value).toEqual(normalUser.email);
    expect(asFragment()).toMatchSnapshot();
  });

  test("ChangePasswordPage matches snapshot", async () => {
    const { asFragment, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <ChangePasswordPage />
      </EndpointContext.Provider>,
      { userInfo }
    );
    await findByText("Change my password");
    expect(asFragment()).toMatchSnapshot();
  });

  test("can change password", async () => {
    const user = userEvent.setup();
    const { getByLabelText, getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <ChangePassword />
      </EndpointContext.Provider>,
      { userInfo }
    );
    const saveChanges = new Promise<EditUserState>((resolve) => {
      apiRequests.editUser.mockImplementation(async (user: EditUserState) => {
        const resp: ModifyUserResponse = {
          success: true,
          errors: [],
          user: {
            ...user,
            groups: [],
          },
        };
        resolve(user);
        return resp;
      });
    });
    const newPassword = "new!password!";
    const pwdInp = getByLabelText("Password:") as HTMLInputElement;
    const confirm = getByLabelText("Confirm Password:") as HTMLInputElement;
    await user.click(pwdInp);
    await user.clear(pwdInp);
    await user.type(pwdInp, newPassword);
    const saveBtn = getByText("Change Password") as HTMLButtonElement;
    expect(saveBtn.disabled).toEqual(true);
    await user.click(confirm);
    await user.clear(confirm);
    await user.type(confirm, newPassword);
    expect(saveBtn.disabled).toEqual(false);
    await user.click(saveBtn);
    await expect(saveChanges).resolves.toEqual(
      expect.objectContaining({
        pk: normalUser.pk,
        email: normalUser.email,
        password: newPassword,
        confirmPassword: newPassword,
      })
    );
    expect(messagesMock.appendMessage).toHaveBeenCalledWith(
      "success",
      "Password successfully modified"
    );
  });

  test("fails to change password", async () => {
    const user = userEvent.setup();
    const { getByLabelText, getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <ChangePassword />
      </EndpointContext.Provider>,
      { userInfo }
    );
    const saveChanges = new Promise<EditUserState>((resolve) => {
      apiRequests.editUser.mockImplementation(async (user: EditUserState) => {
        const resp: ModifyUserResponse = {
          success: false,
          errors: ["server error"],
        };
        resolve(user);
        return resp;
      });
    });
    const newPassword = "new!password!";
    const pwdInp = getByLabelText("Password:") as HTMLInputElement;
    const confirm = getByLabelText("Confirm Password:") as HTMLInputElement;
    await user.click(pwdInp);
    await user.clear(pwdInp);
    await user.type(pwdInp, newPassword);
    const saveBtn = getByText("Change Password") as HTMLButtonElement;
    await user.click(confirm);
    await user.clear(confirm);
    await user.type(confirm, newPassword);
    expect(saveBtn.disabled).toEqual(false);
    await user.click(saveBtn);
    await expect(saveChanges).resolves.toEqual(
      expect.objectContaining({
        pk: normalUser.pk,
        email: normalUser.email,
        password: newPassword,
        confirmPassword: newPassword,
      })
    );
    expect(messagesMock.appendMessage).toHaveBeenCalledWith(
      "warning",
      "Failed to change password"
    );
  });

  test("can change email address", async () => {
    const user = userEvent.setup();
    const { getByLabelText, getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <ChangePassword />
      </EndpointContext.Provider>,
      { userInfo }
    );
    const saveChanges = new Promise<EditUserState>((resolve) => {
      apiRequests.editUser.mockImplementation(async (user: EditUserState) => {
        const resp: ModifyUserResponse = {
          success: true,
          errors: [],
          user: {
            ...user,
            groups: [],
          },
        };
        resolve(user);
        return resp;
      });
    });
    const newEmail = "new.email@account.local";
    const email = getByLabelText("Email:") as HTMLInputElement;
    await user.click(email);
    await user.clear(email);
    await user.type(email, newEmail);
    const saveBtn = getByText("Change Password") as HTMLButtonElement;
    expect(saveBtn.disabled).toEqual(false);
    await user.click(saveBtn);
    await expect(saveChanges).resolves.toEqual(
      expect.objectContaining({
        pk: normalUser.pk,
        email: newEmail,
      })
    );
    expect(messagesMock.appendMessage).toHaveBeenCalledWith(
      "success",
      "Password successfully modified"
    );
  });
});
