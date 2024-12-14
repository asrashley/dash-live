import { beforeEach, describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../../test/renderWithProviders.js";
import AddStreamPage from "./AddStreamPage.js";
import { EndpointContext } from "../../endpoints.js";

describe("AddStreamPage component", () => {
  const apiRequests = {
    getAllStreams: vi.fn(),
  };
  const userInfo = {
    isAuthenticated: true,
    groups: ["MEDIA"],
  };

  beforeEach(() => {
    apiRequests.getAllStreams.mockImplementation(async () => {
        const streams = await import("../../../mocks/streams.json");
        return streams;
      });
  });

  test("allows a new stream to be added", async () => {
    const { asFragment, findByText, getByText } = renderWithProviders(
      html`<${EndpointContext.Provider} value=${apiRequests}><${AddStreamPage} /></${EndpointContext.Provider}>`,
      { userInfo }
    );
    await findByText("Add new Multi-Period stream");
    await findByText("At least one Period is required");
    const btn = getByText("Save new stream");
    expect(btn.disabled).toEqual(true);
    expect(asFragment()).toMatchSnapshot();
  });
});
