import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import fetchMock from "@fetch-mock/vitest";
import userEvent from "@testing-library/user-event";
import { mock } from "vitest-mock-extended";
import { useLocation, useParams } from "wouter-preact";
import log from "loglevel";

import { routeMap, uiRouteMap } from "@dashlive/routemap";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../../endpoints";
import EditUserPage from "./EditUserPage";

import { FakeEndpoint, jsonResponse } from "../../test/FakeEndpoint";
import {
  adminUser,
  mediaUser,
  MockDashServer,
  normalUser,
  UserModel,
} from "../../test/MockServer";
import { useMessages, UseMessagesHook } from "../../hooks/useMessages";

vi.mock("wouter-preact", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useLocation: vi.fn(),
    useParams: vi.fn(),
  };
});

vi.mock("../../hooks/useMessages");

describe("EditUserPage component", () => {
  const needsRefreshToken = vi.fn();
  const hasUserInfo = vi.fn();
  const setLocation = vi.fn();
  const useParamsMock = vi.mocked(useParams);
  const useLocationMock = vi.mocked(useLocation);
  const useMessagesSpy = vi.mocked(useMessages);
  const useMessagesHook = mock<UseMessagesHook>();
  let endpoint: FakeEndpoint;
  let server: MockDashServer;
  let user: UserModel;
  let apiReq: ApiRequests;

  beforeEach(() => {
    log.setLevel("error");
    endpoint = new FakeEndpoint(document.location.origin);
    server = new MockDashServer({
      endpoint,
    });
    user = server.login(adminUser.username, adminUser.password);
    expect(user).not.toBeNull();
    apiReq = new ApiRequests({ needsRefreshToken, hasUserInfo });
    apiReq.setRefreshToken(user.refreshToken);
    apiReq.setAccessToken(user.accessToken);
    useParamsMock.mockReturnValue({
      username: mediaUser.username,
    });
    useLocationMock.mockReturnValue([
      uiRouteMap.editUser.url({ username: mediaUser.username }),
      setLocation,
    ]);
    useMessagesSpy.mockReturnValue(useMessagesHook);
  });

  afterEach(() => {
    vi.clearAllMocks();
    endpoint.shutdown();
    fetchMock.mockReset();
  });

  test("matches snapshot", async () => {
    const { asFragment, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiReq}>
        <EditUserPage />
      </EndpointContext.Provider>
    );
    await findByText(`Editing user ${mediaUser.username}`);
    expect(asFragment()).toMatchSnapshot();
  });

  test.each<boolean>([true, false])(
    "can edit a user, success=%s",
    async (success: boolean) => {
      const user = userEvent.setup();
      const { findByText, findBySelector, getByText } = renderWithProviders(
        <EndpointContext.Provider value={apiReq}>
          <EditUserPage />
        </EndpointContext.Provider>
      );
      const username = "new.username";
      const email = "new.username@test.local";
      const password = "s3cret!";
      const userInp = (await findBySelector(
        'input[name="username"]'
      )) as HTMLInputElement;
      await user.click(userInp);
      await user.clear(userInp);
      await user.type(userInp, success ? username : normalUser.username);
      expect(userInp.value).toEqual(success ? username : normalUser.username);
      const emailInp = (await findBySelector(
        'input[name="email"]'
      )) as HTMLInputElement;
      await user.click(emailInp);
      await user.clear(emailInp);
      await user.type(emailInp, email);
      const pwdInp = (await findBySelector(
        'input[name="password"]'
      )) as HTMLInputElement;
      await user.clear(pwdInp);
      await user.type(pwdInp, password);
      const confirmInp = (await findBySelector(
        'input[name="confirmPassword"]'
      )) as HTMLInputElement;
      await user.clear(confirmInp);
      await user.type(confirmInp, password);
      const editProm = endpoint.addResponsePromise(
        "post",
        routeMap.editUser.url({ upk: mediaUser.pk })
      );
      const btn = (await findByText("Save Changes")) as HTMLButtonElement;
      expect(btn.disabled).toEqual(!success);
      if (!success) {
        getByText("user already exists");
        await user.click(userInp);
        await user.clear(userInp);
        await user.type(userInp, username);
        expect(btn.disabled).toEqual(false);
        server.addUser({
          username,
          email,
        });
      }
      await user.click(btn);
      const result = await editProm;
      expect(result).toEqual(
        expect.objectContaining({
          status: 200,
          body: expect.any(String),
        })
      );
      const body = JSON.parse(result.body as string);
      if (success) {
        const newUser = server.getUser({ username });
        expect(newUser).toBeDefined();
        expect(newUser.password).toEqual(password);
        expect(body).toEqual({
          errors: [],
          success,
          user: {
            email,
            username,
            groups: ["USER", "MEDIA"],
            lastLogin: null,
            mustChange: false,
            pk: mediaUser.pk,
          },
        });
      } else {
        expect(body).toEqual({
          errors: [
            `${username} already exists`,
            `${email} email address already exists`,
          ],
          success,
        });
      }
    }
  );

  test("can delete a user", async () => {
    const user = userEvent.setup();
    const { findByText, findBySelector, getByTestId } = renderWithProviders(
      <EndpointContext.Provider value={apiReq}>
        <EditUserPage />
      </EndpointContext.Provider>
    );
    const delBtn = (await findByText("Delete User")) as HTMLButtonElement;
    await user.click(delBtn);
    await findBySelector(".modal-dialog");
    await findByText("Are you sure you want to delete this user?");
    const delProm = endpoint.addResponsePromise(
      "delete",
      routeMap.editUser.url({ upk: mediaUser.pk })
    );
    const btn = getByTestId("confirm-delete") as HTMLButtonElement;
    await user.click(btn);
    await expect(delProm).resolves.toEqual(
      expect.objectContaining({
        status: 204,
      })
    );
    expect(useMessagesHook.appendMessage).toHaveBeenCalledWith(
      "success",
      "User mediamgr successfully deleted"
    );
  });

  test("failing to delete a user", async () => {
    const user = userEvent.setup();
    const { findByText, findBySelector, getByTestId } = renderWithProviders(
      <EndpointContext.Provider value={apiReq}>
        <EditUserPage />
      </EndpointContext.Provider>
    );
    const delBtn = (await findByText("Delete User")) as HTMLButtonElement;
    await user.click(delBtn);
    await findBySelector(".modal-dialog");
    await findByText("Are you sure you want to delete this user?");
    const delProm = new Promise<void>((resolve) => {
      endpoint.setResponseModifier(
        "delete",
        routeMap.editUser.url({ upk: mediaUser.pk }),
        async () => {
          resolve();
          return jsonResponse("", 404);
        }
      );
    });
    const btn = getByTestId("confirm-delete") as HTMLButtonElement;
    await user.click(btn);
    await delProm;
    expect(useMessagesHook.appendMessage).toHaveBeenCalledWith(
      "warning",
      "Failed to delete user - Error: http://localhost:3000/api/users/101: 404"
    );
  });
});
