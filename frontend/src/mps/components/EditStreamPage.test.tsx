import { beforeEach, describe, expect, test } from "vitest";
import { act } from "@testing-library/preact";
import { Route } from "wouter-preact";

import { renderWithProviders } from "../../test/renderWithProviders";
import EditStreamPage from "./EditStreamPage";
import { ApiRequests, EndpointContext } from "../../endpoints";
import { routeMap } from "../../test/fixtures/routemap.js";
import { mock } from "vitest-mock-extended";
import { AllStreamsJson } from "../../types/AllStreams";
import { MultiPeriodStreamJson } from "../../types/MultiPeriodStream";

describe("EditStreamPage component", () => {
  const apiRequests = mock<ApiRequests>();
  const userInfo = {
    isAuthenticated: true,
    groups: ["MEDIA"],
  };
  let fetchPromises;

  beforeEach(() => {
    fetchPromises = Promise.all([
      new Promise<void>((resolve) => {
        apiRequests.getAllStreams.mockImplementation(async () => {
          const streams = await import("../../test/fixtures/streams.json");
          resolve();
          return streams.default as AllStreamsJson;
        });
      }),
      new Promise<void>((resolve) => {
        apiRequests.getMultiPeriodStream.mockImplementation(async () => {
          const demo = await import("../../test/fixtures/multi-period-streams/demo.json");
          resolve();
          return demo.default as MultiPeriodStreamJson;
        });
      }),
    ]);
  });

  test("allows an existing stream to be edited", async () => {
    const path = "/multi-period-streams/demo";
    const { asFragment, findByText, getBySelector, getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
      <Route component={EditStreamPage} path={routeMap.editMps.route} />
      </EndpointContext.Provider>,
      { userInfo, path }
    );
    await act(async () => {
        await fetchPromises;
    })
    await findByText('Editing Multi-Period stream "demo"');
    const btn = getByText("Save Changes") as HTMLButtonElement;
    expect(btn.disabled).toEqual(true);
    const nameField = getBySelector('#field-name') as HTMLInputElement;
    expect(nameField.value).toEqual('demo');
    const titleField = getBySelector('#field-title') as HTMLInputElement;
    expect(titleField.value).toEqual('first title');
    getByText('Delete Stream');
    expect(asFragment()).toMatchSnapshot();
  });
});
