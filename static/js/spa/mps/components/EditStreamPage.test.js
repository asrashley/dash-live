import { beforeEach, describe, expect, test, vi } from "vitest";
import { act } from "@testing-library/preact";
import { html } from "htm/preact";
import { Route } from "wouter-preact";

import { renderWithProviders } from "../../../test/renderWithProviders.js";
import EditStreamPage from "./EditStreamPage.js";
import { EndpointContext } from "../../endpoints.js";
import { routeMap } from "../../../mocks/routemap.js";

describe("EditStreamPage component", () => {
  const apiRequests = {
    getAllStreams: vi.fn(),
    getMultiPeriodStream: vi.fn(),
  };
  const userInfo = {
    isAuthenticated: true,
    groups: ["MEDIA"],
  };
  let fetchPromises;

  beforeEach(() => {
    fetchPromises = Promise.all([
      new Promise((resolve) => {
        apiRequests.getAllStreams.mockImplementation(async () => {
          const streams = await import("../../../mocks/streams.json");
          resolve();
          return streams;
        });
      }),
      new Promise((resolve) => {
        apiRequests.getMultiPeriodStream.mockImplementation(async () => {
          const demo = await import("../../../mocks/demo-mps.json");
          resolve();
          return demo;
        });
      }),
    ]);
  });

  test("allows an existing stream to be edited", async () => {
    const path = "/multi-period-streams/demo";
    const { asFragment, findByText, getBySelector, getByText } = renderWithProviders(
      html`<${EndpointContext.Provider} value=${apiRequests}>
      <${Route} component=${EditStreamPage} path="${routeMap.editMps.route}"/>
      </${EndpointContext.Provider}>`,
      { userInfo, path }
    );
    await act(async () => {
        await fetchPromises;
    })
    await findByText('Editing Multi-Period stream "demo"');
    const btn = getByText("Save Changes");
    expect(btn.disabled).toEqual(true);
    expect(getBySelector('#field-name').value).toEqual('demo');
    expect(getBySelector('#field-title').value).toEqual('first title');
    getByText('Delete Stream');
    expect(asFragment()).toMatchSnapshot();
  });
});
