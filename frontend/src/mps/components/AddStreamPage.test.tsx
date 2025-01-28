import { beforeEach, describe, expect, test } from "vitest";
import { mock } from 'vitest-mock-extended';

import { renderWithProviders } from "../../test/renderWithProviders";
import AddStreamPage from "./AddStreamPage";
import { ApiRequests, EndpointContext } from "../../endpoints";
import { AllStreamsJson } from "../../types/AllStreams";
import { mediaUser } from "../../test/MockServer";

describe("AddStreamPage component", () => {
  const apiRequests = mock<ApiRequests>();

  beforeEach(() => {
    apiRequests.getAllStreams.mockImplementation(async () => {
        const streams = await import("../../test/fixtures/streams.json") as AllStreamsJson;
        return streams;
      });
  });

  test("allows a new stream to be added", async () => {
    const { asFragment, findByText, getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}><AddStreamPage /></EndpointContext.Provider>,
      { userInfo: mediaUser }
    );
    await findByText("Add new Multi-Period stream");
    await findByText("At least one Period is required");
    const btn = getByText("Save new stream") as HTMLButtonElement;
    expect(btn.disabled).toEqual(true);
    expect(asFragment()).toMatchSnapshot();
  });
});
