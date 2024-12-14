import { beforeEach, describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../../test/renderWithProviders.js";
import ListStreamsPage from "./ListStreamsPage.js";
import { EndpointContext } from "../../endpoints.js";

describe("ListStreamsPage", () => {
  const apiRequests = {
    getAllMultiPeriodStreams: vi.fn(),
  };
  const userInfo = {
    isAuthenticated: true,
    groups: ["MEDIA"],
  };

  beforeEach(() => {
    apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
      return await import("../../../mocks/multi-period-streams.json");
    });
  });

  test("should display list of multi-period streams", async () => {
    const { asFragment, findByText } = renderWithProviders(
      html`<${EndpointContext.Provider} value=${apiRequests}><${ListStreamsPage} /></${EndpointContext.Provider}>`,
      { userInfo }
    );
    await findByText("first title");
    await findByText("Add a Stream");
    expect(asFragment()).toMatchSnapshot();
  });

  test("should not show add stream button when user not logged in", async () => {
    const { queryByText, findByText } = renderWithProviders(
      html`<${EndpointContext.Provider} value=${apiRequests}><${ListStreamsPage} /></${EndpointContext.Provider}>`,
    );
    await findByText("first title");
    expect(queryByText("Add a Stream")).toBeNull();
  });
});
