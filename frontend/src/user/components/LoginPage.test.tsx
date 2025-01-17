import { describe, expect, test } from "vitest";
import userEvent from "@testing-library/user-event";
import { mock } from "vitest-mock-extended";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../../endpoints";
import LoginPage from "./LoginPage";
import { LoginResponse } from "../../types/LoginResponse";
import { LoginRequest } from "../../types/LoginRequest";

describe("LoginPage component", () => {
  const apiRequests = mock<ApiRequests>();

  test("matches snapshot", () => {
    const { asFragment } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <LoginPage />
      </EndpointContext.Provider>
    );
    expect(asFragment()).toMatchSnapshot();
  });

  test('successful login', async () => {
    const loginResponse: LoginResponse = {
        success: true,
        accessToken: {
            jwt: 'access.abc123',
            expires: '2025-01-09T22:33:44Z',
        },
        refreshToken: {
            jwt: 'refresh.abc123',
            expires: '2025-01-09T22:33:44Z',
        },
        user: {
            isAuthenticated: true,
            pk: 42,
            username: 'my.username',
            email: 'unit.test@local',
            groups: ['USERS'],
        },
        csrf_token: "csrf.7654"
    };
    const loginPromise = new Promise<LoginRequest>((resolve => {
        apiRequests.loginUser.mockImplementation((req: LoginRequest) => {
            resolve(req);
            return Promise.resolve(loginResponse);
        });
    }))
    const user = userEvent.setup();
    const { getByLabelText, getByText } = renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <LoginPage />
        </EndpointContext.Provider>
      );
      const userInp = getByLabelText("Username", {
        exact: false,
      }) as HTMLInputElement;
      const pwdInp = getByLabelText("Password", {
        exact: false,
      }) as HTMLInputElement;
      await user.type(userInp, "test");
      await user.type(pwdInp, "secret");
      const submit = getByText('Login') as HTMLButtonElement;
      expect(submit.disabled).toEqual(false);
      await user.click(submit);
      await expect(loginPromise).resolves.toEqual({
        username: 'test',
        password: 'secret',
        rememberme: false,
      });
  });

  test('failed login', async () => {
    const loginResponse: LoginResponse = {
        success: false,
        error: 'Incorrect username or password',
        csrf_token: "csrf.7654"
    };
    const loginPromise = new Promise<void>((resolve => {
        apiRequests.loginUser.mockImplementation(() => {
            resolve();
            return Promise.resolve(loginResponse);
        });
    }))
    const user = userEvent.setup();
    const { getByLabelText, getBySelector, getByText, findByText } = renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <LoginPage />
        </EndpointContext.Provider>
      );
      const userInp = getByLabelText("Username", {
        exact: false,
      }) as HTMLInputElement;
      const pwdInp = getByLabelText("Password", {
        exact: false,
      }) as HTMLInputElement;
      await user.type(userInp, "test");
      await user.type(pwdInp, "secret");
      const submit = getByText('Login') as HTMLButtonElement;
      expect(submit.disabled).toEqual(false);
      await user.click(submit);
      await loginPromise;
      await findByText('Incorrect username or password');
      expect((getBySelector("#login-form") as HTMLElement).className).toEqual("");
  });

  test('fails to make login API call', async () => {
    const loginPromise = new Promise<void>((resolve => {
        apiRequests.loginUser.mockImplementation(() => {
            resolve();
            return Promise.reject(new Error('NetworkError when attempting to fetch resource'));
        });
    }));
    const user = userEvent.setup();
    const { getByLabelText, getBySelector, getByText, findByText } = renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <LoginPage />
        </EndpointContext.Provider>
      );
      const userInp = getByLabelText("Username", {
        exact: false,
      }) as HTMLInputElement;
      const pwdInp = getByLabelText("Password", {
        exact: false,
      }) as HTMLInputElement;
      await user.type(userInp, "test");
      await user.type(pwdInp, "secret");
      const submit = getByText('Login') as HTMLButtonElement;
      expect(submit.disabled).toEqual(false);
      await user.click(submit);
      await loginPromise;
      await findByText('NetworkError when attempting to fetch resource', { exact: false });
      expect((getBySelector("#login-form") as HTMLElement).className).toEqual("");
  });
});
