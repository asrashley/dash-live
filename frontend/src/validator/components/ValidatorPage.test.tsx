import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { io, Socket } from "socket.io-client";
import { mock, mockReset } from "vitest-mock-extended";
import { act } from "@testing-library/preact";
import userEvent from "@testing-library/user-event";
import log from "loglevel";

import { wssUrl } from "../utils/wssUrl";
import { MockWebsocketServer } from "../../test/MockWebsocketServer";
import ProtectedValidatorPage, { ValidatorPage } from "./ValidatorPage";
import { renderWithFormAccess } from "../test/renderWithFormAccess";
import { ApiRequests, EndpointContext } from "../../endpoints";
import { LoginResponse } from "../../types/LoginResponse";
import { mediaUser } from "../../test/MockServer";
import { renderWithProviders } from "../../test/renderWithProviders";

vi.mock("socket.io-client");

vi.mock("../utils/wssUrl");

describe("ValidatorPage component", () => {
  const manifest = "http://localhost:8765/dash/vod/bbb/hand_made.mpd";
  const websocketUrl = "wss://localhost:3456";
  const ioMock = vi.mocked(io);
  const wssUrlMock = vi.mocked(wssUrl);
  const mockSocket = mock<Socket>();
  let server: MockWebsocketServer;

  beforeEach(() => {
    wssUrlMock.mockReturnValue(websocketUrl);
    server = MockWebsocketServer.create(websocketUrl, mockSocket).server;
    ioMock.mockImplementation(() => mockSocket);
  });

  afterEach(async () => {
    await server.destroy();
    vi.clearAllMocks();
    mockReset(mockSocket);
    log.setLevel("error");
  });

  test("initial state", async () => {
    const { asFragment, getByTestId, startBtn, cancelBtn } =
      renderWithFormAccess(<ValidatorPage />);
    await expect(server.getConnectedPromise()).resolves.toBeUndefined();
    expect(startBtn.disabled).toEqual(true);
    expect(cancelBtn.disabled).toEqual(true);
    const stateElt = getByTestId("validator-state-badge") as HTMLElement;
    expect(stateElt.innerHTML).toEqual("idle");
    expect(ioMock).toHaveBeenCalledTimes(1);
    expect(ioMock).toHaveBeenCalledWith(websocketUrl, {
      autoConnect: false,
    });
    expect(asFragment()).toMatchSnapshot();
  });

  test("can validate a stream", async () => {
    const userEv = userEvent.setup();

    const { getByTestId, manifestElt, startBtn } = renderWithFormAccess(
      <ValidatorPage />
    );
    await userEv.click(manifestElt);
    await userEv.clear(manifestElt);
    await userEv.type(manifestElt, manifest);
    expect(startBtn.disabled).toEqual(false);
    const done = server.getDonePromise();
    await userEv.click(startBtn);
    let finished = false;
    while (!finished) {
      await act(async () => {
        finished = await server.nextTick(0.5);
      });
    }
    await expect(done).resolves.toBeUndefined();
    const stateElt = getByTestId("validator-state-badge") as HTMLElement;
    expect(stateElt.innerHTML).toEqual("done");
  });

  describe("ProtectedValidatorPage component", () => {
    const apiRequests = mock<ApiRequests>();

    afterEach(() => {
      vi.clearAllMocks();
      mockReset(apiRequests);
    });

    test("initial state, not logged in", async () => {
      apiRequests.getUserInfo.mockImplementation(
        async () => new Response(null, { status: 401 })
      );
      const { asFragment, findByLabelText } = renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <ProtectedValidatorPage />
        </EndpointContext.Provider>
      );
      await expect(server.getConnectedPromise()).resolves.toBeUndefined();
      const saveElt = (await findByLabelText(
        "Add stream to this server?"
      )) as HTMLInputElement;
      expect(saveElt.disabled).toEqual(true);
      expect(asFragment()).toMatchSnapshot();
    });

    test("initial state, logged in user", async () => {
      const login: LoginResponse = {
        success: true,
        csrf_token: "123",
        user: mediaUser,
      };
      apiRequests.getUserInfo.mockImplementation(async () => login);
      const { asFragment, findByLabelText } = renderWithProviders(
        <EndpointContext.Provider value={apiRequests}>
          <ProtectedValidatorPage />
        </EndpointContext.Provider>,
        { userInfo: mediaUser }
      );
      await expect(server.getConnectedPromise()).resolves.toBeUndefined();
      const saveElt = (await findByLabelText(
        "Add stream to this server?"
      )) as HTMLInputElement;
      expect(saveElt.disabled).toEqual(false);
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
