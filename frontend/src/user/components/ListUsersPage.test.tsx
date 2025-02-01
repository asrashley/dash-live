import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import log from "loglevel";
import fetchMock from "@fetch-mock/vitest";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../../endpoints";
import ListUsersPage from "./ListUsersPage";

import { routeMap } from "@dashlive/routemap";
import { FakeEndpoint } from "../../test/FakeEndpoint";
import {
  adminUser,
  mediaUser,
  MockDashServer,
  normalUser,
  UserModel,
} from "../../test/MockServer";

describe("ListUsersPage component", () => {
  const needsRefreshToken = vi.fn();
  const hasUserInfo = vi.fn();
  let endpoint: FakeEndpoint;
  let server: MockDashServer;
  let user: UserModel;
  let apiReq: ApiRequests;

  beforeEach(() => {
    log.setLevel('error');
    endpoint = new FakeEndpoint(document.location.origin);
    server = new MockDashServer({
      endpoint,
    });
    user = server.login(adminUser.username, adminUser.password);
    expect(user).not.toBeNull();
    apiReq = new ApiRequests({ needsRefreshToken, hasUserInfo });
    apiReq.setRefreshToken(user.refreshToken);
    apiReq.setAccessToken(user.accessToken);
  });

  afterEach(() => {
    vi.clearAllMocks();
    endpoint.shutdown();
    fetchMock.mockReset();
  });

  test("matches snapshot", async () => {
    const { asFragment, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiReq}>
        <ListUsersPage />
      </EndpointContext.Provider>
    );
    await findByText(adminUser.email);
    await findByText(mediaUser.email);
    await findByText(normalUser.email);
    expect(asFragment()).toMatchSnapshot();
  });

  test("can add a new user", async () => {
    const user = userEvent.setup();
    const { findByText, findBySelector, getByTestId } = renderWithProviders(
      <EndpointContext.Provider value={apiReq}>
        <ListUsersPage />
      </EndpointContext.Provider>
    );
    const username = "new.username";
    const email = "new.username@test.local";
    const password = "s3cret!";
    const btn = (await findByText("Add New User")) as HTMLButtonElement;
    await user.click(btn);
    await findBySelector(".modal-dialog");
    const userInp = (await findBySelector(
      'input[name="username"]'
    )) as HTMLInputElement;
    await user.clear(userInp);
    await user.type(userInp, username);
    const emailInp = (await findBySelector(
      'input[name="email"]'
    )) as HTMLInputElement;
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
    const addProm = endpoint.addResponsePromise(
      "put",
      routeMap.listUsers.url()
    );
    await user.click(getByTestId("add-new-user-btn") as HTMLButtonElement);
    const result = await addProm;
    expect(result).toEqual(
      expect.objectContaining({
        status: 200,
        body: expect.any(String),
      })
    );
    const body = JSON.parse(result.body as string);
    const newUser = server.getUser({ username });
    expect(newUser).toBeDefined();
    expect(newUser.password).toEqual(password);
    expect(body).toEqual({
      errors: [],
      success: true,
      user: {
        email,
        username,
        groups: ["USER"],
        lastLogin: null,
        mustChange: true,
        pk: newUser.pk,
      },
    });
  });
});
