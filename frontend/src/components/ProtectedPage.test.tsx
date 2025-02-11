import { describe, test } from "vitest";
import { act } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";

import { renderWithProviders } from "../test/renderWithProviders";
import { ProtectedPage } from "./ProtectedPage";
import { ApiRequests, EndpointContext } from "../endpoints";
import { LoginResponse } from "../types/LoginResponse";
import { normalUser } from "../test/MockServer";
import { InitialUserState } from "../types/UserState";

type TestCase = {
  title: string;
  resolveFetch: boolean;
  optional: boolean;
  user: InitialUserState | null;
};

describe("ProtectedPage component", () => {
  const apiRequests = mock<ApiRequests>();

  test.each<TestCase>([
    {
      title: "normal user, resolves fetch",
      resolveFetch: true,
      optional: false,
      user: normalUser,
    },
    {
      title: "normal user, fetch does not complete",
      resolveFetch: false,
      optional: false,
      user: normalUser,
    },
    {
      title: "not logged-in optional protection, resolves fetch",
      resolveFetch: true,
      optional: true,
      user: null,
    },
    {
      title: "not logged-in mandatory protection, changes location",
      resolveFetch: true,
      optional: false,
      user: null,
    },
  ])(
    "$title",
    async ({ resolveFetch, optional, user }: TestCase) => {
      const blocker = Promise.withResolvers<LoginResponse | Response>();
      apiRequests.getUserInfo.mockReturnValue(blocker.promise);
      const { whoAmI, getBySelector, findByText } = renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <ProtectedPage optional={optional}>
            <h1>Hello</h1>
          </ProtectedPage>
        </EndpointContext.Provider>
      );
      getBySelector(".lds-ring");
      act(() => {
        if (resolveFetch) {
          const login: LoginResponse = {
            success: true,
            csrf_token: "123",
            user,
          };
          blocker.resolve(user ? login : new Response(null, { status: 401 }));
        }
        whoAmI.setUser(user);
      });
      if (!user && !optional) {
        await findByText("You need to log in to access this page");
      } else {
        await findByText("Hello");
      }
    }
  );

  test("does not show loading spinner if user info already loaded", async () => {
    const blocker = Promise.withResolvers<LoginResponse>();
    apiRequests.getUserInfo.mockReturnValue(blocker.promise);
    const { getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <ProtectedPage>
          <h1>Hello</h1>
        </ProtectedPage>
      </EndpointContext.Provider>,
      { userInfo: normalUser }
    );
    getByText("Hello");
  });
});
