import { describe, test } from "vitest";
import { act } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";

import { renderWithProviders } from "../test/renderWithProviders";
import { ProtectedPage } from "./ProtectedPage";
import { ApiRequests, EndpointContext } from "../endpoints";
import { LoginResponse } from "../types/LoginResponse";
import { normalUser } from "../test/MockServer";

describe("ProtectedPage component", () => {
  const apiRequests = mock<ApiRequests>();

  test.each([true, false])(
    "shows loading spinner and then component when completes getUserInfo = %s",
    async (resolvesFetch: boolean) => {
      const blocker = Promise.withResolvers<LoginResponse>();
      apiRequests.getUserInfo.mockReturnValue(blocker.promise);
      const { whoAmI, getBySelector, findByText } = renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <ProtectedPage>
            <h1>Hello</h1>
          </ProtectedPage>
        </EndpointContext.Provider>
      );
      getBySelector(".lds-ring");
      act(() => {
        if (resolvesFetch) {
          const login: LoginResponse = {
            success: true,
            csrf_token: "123",
            user: normalUser,
          };
          blocker.resolve(login);
        }
        whoAmI.setUser(normalUser);
      });
      await findByText("Hello");
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
