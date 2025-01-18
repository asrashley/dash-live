import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";
import { act, fireEvent, render } from "@testing-library/preact";
import { useContext } from "preact/hooks";
import { useLocation } from 'wouter-preact';

import { navbar } from "@dashlive/init";

import { App } from "./App";
import { AppStateContext, AppStateType } from "./appState";
import { mediaUser, MockDashServer, UserModel } from "./test/MockServer";
import { FakeEndpoint } from "./test/FakeEndpoint";
import { InitialApiTokens } from "./types/InitialApiTokens";
import log from "loglevel";

vi.mock('wouter-preact', async (importOriginal) => {
  return {
    ...await importOriginal(),
    useLocation: vi.fn(),
  };
});

describe("main entry-point app", () => {
  const useLocationSpy = vi.mocked(useLocation);
  const setLocation = vi.fn();
  const mockLocation = {
    ...new URL(document.location.href),
    pathname: '/',
    replace: vi.fn(),
  };
  let endpoint: FakeEndpoint;
  let server: MockDashServer;
  let baseElement: HTMLDivElement;
  let user: UserModel;
  let tokens: InitialApiTokens;

  beforeAll(() => {
    vi.stubGlobal('location', mockLocation);
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    log.setLevel('error');
    endpoint = new FakeEndpoint(document.location.origin);
    server = new MockDashServer({
      endpoint,
    });
    user = server.login(mediaUser.email, mediaUser.password);
    expect(user).not.toBeNull();
    tokens = {
      accessToken: user.accessToken,
      refreshToken: user.refreshToken,
    };
    document.body.innerHTML = '<div id="app" />';
    const app = document.getElementById('app');
    expect(app).not.toBeNull();
    baseElement = app as HTMLDivElement;
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  test("matches snapshot for home page", async () => {
    mockLocation.pathname = "/";
    useLocationSpy.mockReturnValue([mockLocation.pathname, setLocation]);
    const { asFragment, findByText } = render(
      <App tokens={tokens} navbar={navbar} />,
      { baseElement }
    );
    await findByText("Log Out");
    await findByText("Hand-made manifest");
    await findByText("Stream to play");
    await findByText("Video Player:");
    await findByText("Play Big Buck Bunny");
    await findByText("/dash/vod/bbb/hand_made.mpd", { exact: false });
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot for list MPS", async () => {
    mockLocation.pathname = '/multi-period-streams';
    useLocationSpy.mockReturnValue([mockLocation.pathname, setLocation]);
    const { asFragment, findByText } = render(
      <App tokens={tokens} navbar={navbar} />,
      { baseElement }
    );
    await findByText('first title');
    await findByText('Add a Stream');
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot for edit MPS", async () => {
    mockLocation.pathname = '/multi-period-streams/demo';
    useLocationSpy.mockReturnValue([mockLocation.pathname, setLocation]);
    const { asFragment, findByText } = render(
      <App tokens={tokens} navbar={navbar} />,
      { baseElement }
    );
    await findByText("Log Out");
    await findByText("Delete Stream");
    await findByText('"europe-ntp"');
    expect(asFragment()).toMatchSnapshot();
  });

  test("unknown page", async () => {
    mockLocation.pathname = '/unknown';
    useLocationSpy.mockReturnValue([mockLocation.pathname, setLocation]);
    const { findByText } = render(
      <App tokens={tokens} navbar={navbar} />,
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
    useLocationSpy.mockReturnValue([mockLocation.pathname, setLocation]);
    const { findByText } = render(
      <App tokens={tokens} navbar={navbar}><StateSpy /></App>,
      { baseElement }
    );
    await findByText("Stream to play");
    expect(appState).toBeDefined();
    const elt = document.querySelector('.modal-backdrop');
    expect(elt.className).toEqual('modal-backdrop hidden');
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
    expect(elt.className).toEqual('modal-backdrop hidden');
  });

  test("doesn't reload page when navigating to another SPA page", async () => {
    mockLocation.pathname = "/";
    useLocationSpy.mockReturnValue(["/", setLocation]);
    const { findByText } = render(
      <App tokens={tokens}  navbar={navbar} />,
      { baseElement }
    );
    await findByText("Stream to play");
    const elt = document.querySelector('a[href="/multi-period-streams"]');
    expect(elt).not.toBeNull();
    fireEvent.click(elt);
    expect(setLocation).toHaveBeenCalled();
    expect(setLocation).toHaveBeenCalledWith('/multi-period-streams');
  });
});
