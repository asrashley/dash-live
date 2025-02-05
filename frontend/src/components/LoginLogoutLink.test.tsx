import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock } from "vitest-mock-extended";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";
import { renderWithProviders } from "../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../endpoints";
import { useMessages, UseMessagesHook } from "../hooks/useMessages";
import { normalUser } from "../test/MockServer";

import { LoginLogoutLink } from "./LoginLogoutLink";
import userEvent from "@testing-library/user-event";

vi.mock("wouter-preact", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useLocation: vi.fn(),
  };
});

vi.mock("../hooks/useMessages", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useMessages: vi.fn(),
  };
});

describe("LoginLogoutLink component", () => {
  const useLocationMock = vi.mocked(useLocation);
  const useMessagesMock = vi.mocked(useMessages);
  const setLocation = vi.fn();
  const apiRequests = mock<ApiRequests>();
  const messagesMock = mock<UseMessagesHook>();

  beforeEach(() => {
    useLocationMock.mockReturnValue(["/", setLocation]);
    useMessagesMock.mockReturnValue(messagesMock);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("shows login link", async () => {
    const user = userEvent.setup();
    const { asFragment, getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <LoginLogoutLink />
      </EndpointContext.Provider>
    );
    const btn = getByText("Log In") as HTMLButtonElement;
    await user.click(btn);
    expect(setLocation).toHaveBeenCalledTimes(1);
    expect(setLocation).toHaveBeenCalledWith(uiRouteMap.login.url());
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows log out link", async () => {
    const user = userEvent.setup();
    const prom = new Promise<void>((resolve) => {
      apiRequests.logoutUser.mockImplementationOnce(() => {
        resolve();
        return Promise.resolve(
          new Response(null, {
            status: 204,
          })
        );
      });
    });

    const { asFragment, getByTestId, findByText, whoAmI } =
      renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <LoginLogoutLink />
        </EndpointContext.Provider>,
        { userInfo: normalUser }
    );
    const toggle = getByTestId("toggle-user-menu") as HTMLButtonElement;
    await user.click(toggle);
    const btn = await findByText("Log Out") as HTMLButtonElement;
    expect(whoAmI.user.value.isAuthenticated).toEqual(true);
    await user.click(btn);
    await prom;
    expect(whoAmI.user.value.isAuthenticated).toEqual(false);
    expect(setLocation).toHaveBeenCalledTimes(1);
    expect(setLocation).toHaveBeenCalledWith(uiRouteMap.home.url());
    await findByText("Log In");
    expect(messagesMock.appendMessage).toHaveBeenCalledTimes(1);
    expect(messagesMock.appendMessage).toHaveBeenCalledWith(
      "success",
      "You have successfully logged out"
    );
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows error if log out fails", async () => {
    const user = userEvent.setup();
    const prom = new Promise<void>((resolve) => {
      apiRequests.logoutUser.mockImplementationOnce(() => {
        resolve();
        return Promise.reject(new Error("500: Server Error"));
      });
    });

    const { findByText, getByTestId, whoAmI } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <LoginLogoutLink />
      </EndpointContext.Provider>,
      { userInfo: normalUser }
    );
    const toggle = getByTestId("toggle-user-menu") as HTMLButtonElement;
    await user.click(toggle);
    const btn = await findByText('Log Out') as HTMLButtonElement;
    await user.click(btn);
    await prom;
    expect(whoAmI.user.value.isAuthenticated).toEqual(false);
    expect(setLocation).toHaveBeenCalledTimes(1);
    expect(setLocation).toHaveBeenCalledWith(uiRouteMap.home.url());
    await findByText("Log In");
    expect(messagesMock.appendMessage).toHaveBeenCalledTimes(1);
    expect(messagesMock.appendMessage).toHaveBeenCalledWith(
      "danger",
      "Logout failed: Error: 500: Server Error"
    );
  });
});
