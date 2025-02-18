import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";
import { act, render } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";
import fetchMock from '@fetch-mock/vitest';
import { useContext } from "preact/hooks";
import { useLocation } from 'wouter-preact';
import { io, Socket } from "socket.io-client";
import log from "loglevel";

import { routeMap, uiRouteMap } from "@dashlive/routemap";

import { App } from "./App";
import { AppStateContext, AppStateType } from "./appState";
import { adminUser, mediaUser, MockDashServer, UserModel } from "./test/MockServer";
import { FakeEndpoint, HttpRequestHandlerResponse } from "./test/FakeEndpoint";
import { JWToken } from "./user/types/JWToken";
import { LocalStorageKeys } from "./hooks/useLocalStorage";
import { wssUrl } from "./validator/utils/wssUrl";
import { MockWebsocketServer } from "./test/MockWebsocketServer";

vi.mock('wouter-preact', async (importOriginal) => {
  return {
    ...await importOriginal(),
    useLocation: vi.fn(),
  };
});

vi.mock("socket.io-client");

vi.mock("./validator/utils/wssUrl");

describe("main entry-point app", () => {
  const useLocationSpy = vi.mocked(useLocation);
  const setLocation = vi.fn();
  const mockLocation = {
    ...new URL(document.location.href),
    pathname: '/',
    replace: vi.fn(),
  };
  const websocketUrl = "wss://localhost:3456";
  const wssUrlMock = vi.mocked(wssUrl);
  const ioMock = vi.mocked(io);
  const mockSocket = mock<Socket>();

  let endpoint: FakeEndpoint;
  let dashServer: MockDashServer;
  let wssServer: MockWebsocketServer;
  let baseElement: HTMLDivElement;
  let user: UserModel;
  let userPromise: Promise<HttpRequestHandlerResponse>;
  let manifestPromise: Promise<HttpRequestHandlerResponse>;

  beforeAll(() => {
    vi.stubGlobal('location', mockLocation);
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    log.setLevel('error');
    useLocationSpy.mockImplementation(() => [mockLocation.pathname, setLocation]);
    endpoint = new FakeEndpoint(document.location.origin);
    dashServer = new MockDashServer({
      endpoint,
    });
    wssUrlMock.mockReturnValue(websocketUrl);
    const { server } = MockWebsocketServer.create(websocketUrl, mockSocket);
    expect(server).toBeDefined();
    wssServer = server;
    ioMock.mockImplementation(() => mockSocket);
    user = dashServer.login(mediaUser.email, mediaUser.password);
    expect(user).not.toBeNull();
    localStorage.setItem(LocalStorageKeys.REFRESH_TOKEN, JSON.stringify(user.refreshToken));
    document.body.innerHTML = '<div id="app" />';
    const app = document.getElementById('app');
    expect(app).not.toBeNull();
    baseElement = app as HTMLDivElement;
    userPromise = endpoint.addResponsePromise('get', routeMap.login.url());
    manifestPromise = endpoint.addResponsePromise('get', routeMap.listManifests.url());
  });

  afterEach(async () => {
    await wssServer.destroy();
    vi.clearAllMocks();
    localStorage.clear();
    endpoint.shutdown();
    fetchMock.mockReset();
  });

  test("matches snapshot for home page", async () => {
    mockLocation.pathname = "/";
    const { asFragment, findByText } = render(
      <App />,
      { baseElement }
    );
    await userPromise;
    await manifestPromise;
    await findByText("Log Out");
    await findByText("Stream to play");
    await findByText("Video Player:");
    await findByText("Hand-made manifest");
    await findByText("/dash/vod/bbb/hand_made.mpd", { exact: false });
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot for home page when user not logged in", async () => {
    mockLocation.pathname = "/";
    localStorage.clear();
    const { asFragment, findByText } = render(
      <App />,
      { baseElement }
    );
    await manifestPromise;
    await findByText("Log In");
    await findByText("/dash/vod/bbb/hand_made.mpd");
    await findByText("Stream to play");
    await findByText("Video Player:");
    await findByText("Play Big Buck Bunny");
    await findByText("/dash/vod/bbb/hand_made.mpd", { exact: false });
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot for CGI options", async () => {
    mockLocation.pathname = uiRouteMap.cgiOptions.url();
    const listMpsProm = endpoint.addResponsePromise('get', routeMap.cgiOptions.url());
    const { asFragment, findByText } = render(
      <App />,
      { baseElement }
    );
    await userPromise;
    await listMpsProm;
    await findByText("Log Out");
    await findByText("Enable or disable adaptive bitrate");
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot for list MPS", async () => {
    mockLocation.pathname = uiRouteMap.listMps.url();
    const listMpsProm = endpoint.addResponsePromise('get', routeMap.listMps.url());
    const { asFragment, findByText } = render(
      <App />,
      { baseElement }
    );
    await userPromise;
    await listMpsProm;
    await findByText("Log Out");
    await findByText('first title');
    await findByText('Add a Stream');
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot for edit MPS", async () => {
    mockLocation.pathname = uiRouteMap.editMps.url({ mps_name: 'demo' });
    const { asFragment, findByText, findAllByText } = render(
      <App />,
      { baseElement }
    );
    await userPromise;
    await findByText("Log Out");
    await findByText("Delete Stream");
    await findByText('"europe-ntp"');
    await findAllByText("2/3 tracks");
    expect(asFragment()).toMatchSnapshot();
  });

  test('matches snapshot for list users', async () => {
    user = dashServer.login(adminUser.email, adminUser.password);
    expect(user).not.toBeNull();
    localStorage.setItem(LocalStorageKeys.REFRESH_TOKEN, JSON.stringify(user.refreshToken));
    mockLocation.pathname = uiRouteMap.listUsers.url();
    const { asFragment, findByText } = render(
      <App />,
      { baseElement }
    );
    await userPromise;
    await findByText("Log Out");
    await findByText(mediaUser.email);
    expect(asFragment()).toMatchSnapshot();
  });

  test('matches snapshot for DASH validator', async () => {
    mockLocation.pathname = uiRouteMap.validator.url();
    const { asFragment, findByText } = render(
      <App />,
      { baseElement }
    );
    await userPromise;
    await findByText("Manifest to check:");
    expect(asFragment()).toMatchSnapshot();
  });

  test("unknown page", async () => {
    mockLocation.pathname = '/unknown';
    const { findByText } = render(
      <App />,
      { baseElement }
    );
    await findByText("Sorry I don't know about this page");
  });

  test("modal backdrop is displayed", async () => {
    let appState: AppStateType;
    const StateSpy = () => {
      appState = useContext(AppStateContext);
      return <div />;
    };
    mockLocation.pathname = "/";
    const { findByText } = render(
      <App><StateSpy /></App>,
      { baseElement }
    );
    await findByText("Stream to play");
    expect(appState).toBeDefined();
    const elt = document.querySelector('.modal-backdrop');
    expect(elt.className).toEqual('modal-backdrop d-none');
    act(() => {
      appState!.dialog.value = {
        backdrop: true,
      };
    });
    expect(elt.className).toEqual('modal-backdrop show');
    act(() => {
      appState!.dialog.value = {
        backdrop: false,
      };
    });
    expect(elt.className).toEqual('modal-backdrop d-none');
  });

  test("doesn't reload page when navigating to another SPA page", async () => {
    mockLocation.pathname = "/";
    const { findByText } = render(
      <App />,
      { baseElement }
    );
    await findByText("Stream to play");
    const elt = document.querySelector('a[href="/multi-period-streams"]');
    expect(elt).not.toBeNull();
    expect(elt.classList.contains('spa')).toEqual(true);
  });

  test("redirects to login page if refresh token has expired", async () => {
    mockLocation.pathname = uiRouteMap.editMps.url({ mps_name: 'demo' });
    const refreshProm = endpoint.addResponsePromise('get', routeMap.refreshAccessToken.url());
    const locationProm = new Promise<string>(resolve => {
      setLocation.mockImplementationOnce((url: string) => {
        mockLocation.pathname = url;
        resolve(url);
      });
    });
    const expired: JWToken ={
      jwt: 'expired',
      expires: '2021-01-01T00:00:00Z',
    };
    localStorage.setItem(LocalStorageKeys.REFRESH_TOKEN, JSON.stringify(expired));
    const { findByText } = render(
      <App />,
      { baseElement }
    );
    await refreshProm;
    await expect(locationProm).resolves.toEqual(uiRouteMap.login.url());
    await findByText("Log In");
    expect(setLocation).toHaveBeenCalledTimes(1);
    expect(setLocation).toHaveBeenCalledWith(uiRouteMap.login.url());
  });
});
