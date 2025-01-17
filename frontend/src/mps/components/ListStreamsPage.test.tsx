import { beforeEach, describe, expect, test } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import ListStreamsPage from "./ListStreamsPage";
import { ApiRequests, EndpointContext } from "../../endpoints";
import { mock } from "vitest-mock-extended";
import { AllMultiPeriodStreamsJson } from "../../types/AllMultiPeriodStreams";

describe("ListStreamsPage", () => {
  const apiRequests = mock<ApiRequests>();
  const userInfo = {
    isAuthenticated: true,
    groups: ["MEDIA"],
  };

  beforeEach(() => {
    apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
      const { streams } = await import("../../test/fixtures/multi-period-streams/index.json") as AllMultiPeriodStreamsJson;
      return streams;
    });
  });

  test("should display list of multi-period streams", async () => {
    const { asFragment, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}><ListStreamsPage /></EndpointContext.Provider>,
      { userInfo }
    );
    await findByText("first title");
    await findByText("Add a Stream");
    expect(asFragment()).toMatchSnapshot();
  });

  test("should not show add stream button when user not logged in", async () => {
    const { queryByText, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}><ListStreamsPage /></EndpointContext.Provider>,
    );
    await findByText("first title");
    expect(queryByText("Add a Stream")).toBeNull();
  });
});
