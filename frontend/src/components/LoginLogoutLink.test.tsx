import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";
import { renderWithProviders } from "../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../endpoints";
import { InitialUserState } from "../types/UserState";
import { useMessages, UseMessagesHook } from "../hooks/useMessages";

import { LoginLogoutLink } from "./LoginLogoutLink";

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
  const userInfo: InitialUserState = {
    pk: 3,
    isAuthenticated: true,
    groups: ["USER"],
  };

  beforeEach(() => {
    useLocationMock.mockReturnValue(["/", setLocation]);
    useMessagesMock.mockReturnValue(messagesMock);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("shows login link", () => {
    const { asFragment, getByText, getBySelector } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <LoginLogoutLink />
      </EndpointContext.Provider>
    );
    getByText("Log In");
    const link = getBySelector(".nav-link") as HTMLAnchorElement;
    fireEvent.click(link);
    expect(setLocation).toHaveBeenCalledTimes(1);
    expect(setLocation).toHaveBeenCalledWith(uiRouteMap.login.url());
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows log out link", async () => {
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

    const { asFragment, findByText, getBySelector, state } =
      renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <LoginLogoutLink />
        </EndpointContext.Provider>,
        { userInfo }
      );
    await findByText("Log Out");
    expect(state.user.value.isAuthenticated).toEqual(true);
    const link = getBySelector(".nav-link") as HTMLAnchorElement;
    fireEvent.click(link);
    await prom;
    expect(state.user.value.isAuthenticated).toEqual(false);
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
    const prom = new Promise<void>((resolve) => {
      apiRequests.logoutUser.mockImplementationOnce(() => {
        resolve();
        return Promise.reject(new Error("500: Server Error"));
      });
    });

    const { findByText, getBySelector, state } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <LoginLogoutLink />
      </EndpointContext.Provider>,
      { userInfo }
    );
    const link = getBySelector(".nav-link") as HTMLAnchorElement;
    fireEvent.click(link);
    await prom;
    expect(state.user.value.isAuthenticated).toEqual(false);
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
