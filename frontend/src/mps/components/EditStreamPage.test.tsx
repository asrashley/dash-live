import { beforeEach, describe, expect, test } from "vitest";
import { mock } from "vitest-mock-extended";
import { act } from "@testing-library/preact";
import { Route } from "wouter-preact";

import { renderWithProviders } from "../../test/renderWithProviders";
import EditStreamPage from "./EditStreamPage";
import { ApiRequests, EndpointContext } from "../../endpoints";
import { uiRouteMap } from "../../test/fixtures/routemap.js";
import { AllStreamsJson } from "../../types/AllStreams";
import { mediaUser } from "../../test/MockServer";

describe("EditStreamPage component", () => {
  const apiRequests = mock<ApiRequests>();
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
          const { model } = await import("../../test/fixtures/multi-period-streams/demo.json");
          resolve();
          return model;
        });
      }),
    ]);
  });

  test("allows an existing stream to be edited", async () => {
    const path = "/multi-period-streams/demo";
    const { asFragment, findByText, getBySelector, getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
      <Route component={EditStreamPage} path={uiRouteMap.editMps.route} />
      </EndpointContext.Provider>,
      { userInfo: mediaUser, path }
    );
    await act(async () => {
        await fetchPromises;
    });
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
