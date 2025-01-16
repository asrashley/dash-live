import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock } from "vitest-mock-extended";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../../endpoints";
import allCgiOptions from '../../test/fixtures/cgiOptions.json';

import CgiOptionsPage from "./CgiOptionsPage";
import { CgiOptionDescription } from "../../types/CgiOptionDescription";
import { fireEvent } from "@testing-library/preact";

describe("CgiOptionsPage component", () => {
  const apiMock = mock<ApiRequests>();
  let getCgiOptionsProm: Promise<void>;

  beforeEach(() => {
    getCgiOptionsProm = new Promise<void>(resolve => {
        apiMock.getCgiOptions.mockImplementation(async () => {
            resolve();
            return allCgiOptions as CgiOptionDescription[];
        });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", async () => {
    const { asFragment, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiMock}>
        <CgiOptionsPage />
      </EndpointContext.Provider>
    );
    await expect(getCgiOptionsProm).resolves.toBeUndefined();
    await findByText("Enable or disable adaptive bitrate");
    expect(asFragment()).toMatchSnapshot();
  });

  test('shows details table', async () => {
    const { getByTestId, findByText } = renderWithProviders(
        <EndpointContext.Provider value={apiMock}>
          <CgiOptionsPage />
        </EndpointContext.Provider>
      );
      await expect(getCgiOptionsProm).resolves.toBeUndefined();
      const elt = getByTestId("toggle-details") as HTMLElement;
      fireEvent.click(elt);
      await findByText("Full Name");
  });
});
