import { afterAll, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";
import { act, fireEvent, render } from "@testing-library/preact";
import { useContext } from "preact/hooks";
import { useLocation } from 'wouter-preact';

import { ApiRequests } from "./endpoints";
import { App } from "./App";
import { AllStreamsJson } from "./types/AllStreams";
import { AppStateContext, AppStateType } from "./appState";

vi.mock('./endpoints.js', async (importOriginal) => {
  const ApiRequests = vi.fn();
  ApiRequests.prototype.getAllManifests = vi.fn();
  ApiRequests.prototype.getAllMultiPeriodStreams = vi.fn();
  ApiRequests.prototype.getAllStreams = vi.fn();
  ApiRequests.prototype.getMultiPeriodStream = vi.fn();
  ApiRequests.prototype.getContentRoles = vi.fn();
  return {
    ...await importOriginal(),
    ApiRequests,
   };
});

vi.mock('wouter-preact', async (importOriginal) => {
  return {
    ...await importOriginal(),
    useLocation: vi.fn(),
  };
});

type ApiRequestPromises = {
  getAllManifests: Promise<void>;
  getAllStreams: Promise<void>;
  getAllMultiPeriodStreams: Promise<void>;
  getMultiPeriodStream: Promise<void>;
  getContentRoles: Promise<void>;
};

describe("main entry-point app", () => {
  const useLocationSpy = vi.mocked(useLocation);
  const setLocation = vi.fn();
  const initialTokens = {
    accessToken: {
      expires: "2024-12-14T16:42:22.606208Z",
      jwt: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTczNDE4NzM0MiwianRpIjoiYmJiYzRmZGQtODk5Ni00Zjg0LThlNjAtOTBiNjU4ZWViYjQ0IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImFkbWluIiwibmJmIjoxNzM0MTg3MzQyLCJjc3JmIjoiODVhMmFlNjktNzJlZi00OTgyLTg0YzktNjM2ZGQ0ZjAwMTZhIiwiZXhwIjoxNzM0MTg4MjQyfQ.7drJGq_ZVEkqOAO9R1JOPPNjpHHPv-mlopAlweRblJs",
    },
    csrfTokens: {
      files: null,
      kids: null,
      streams: "afU1XsoYb%27jhIBvJbHhwNJ1/Dq3Bqamj174Gk%3D%27",
      upload: null,
    },
    refreshToken: {
      expires: "2024-12-21T14:42:22.611946Z",
      jwt: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTczNDE4NzM0MiwianRpIjoiODI4OWYxMTUtMzg4OC00ODVkLTlmMWUtZWM2YzAwMzA1N2RiIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImFkbWluIiwibmJmIjoxNzM0MTg3MzQyLCJjc3JmIjoiYjJiMjI4ZTgtZjliMS00ODc5LThhMTAtNzZkZmU1OWI4Mjc4IiwiZXhwIjoxNzM0MTg4MjQyfQ.LOuYwbGVbnyQUMCJJ4b0E0Jm0bGO41z07b9ZTa-l34c",
    },
  };
  const user = {
    groups: ["USER", "MEDIA", "ADMIN"],
    isAuthenticated: true,
    pk: 1,
    username: "admin",
  };
  const mockLocation = {
    ...new URL(document.location.href),
    pathname: '/',
    replace: vi.fn(),
  };
  const apiRequestMock = vi.mocked(ApiRequests.prototype);
  let baseElement: HTMLDivElement;
  let promises: ApiRequestPromises;

  beforeAll(() => {
    vi.stubGlobal('location', mockLocation);
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    promises = {
      getAllManifests: new Promise<void>(resolve => {
        apiRequestMock.getAllManifests.mockImplementation(async () => {
          const manifests = await import("./test/fixtures/manifests.json");
          resolve();
          return manifests.default;
        });
      }),
      getAllStreams: new Promise<void>(resolve => {
        apiRequestMock.getAllStreams.mockImplementation(async () => {
          const streams = await import("./test/fixtures/streams.json");
          resolve();
          return streams.default as AllStreamsJson;
        });
      }),
      getAllMultiPeriodStreams: new Promise<void>(resolve => {
        apiRequestMock.getAllMultiPeriodStreams.mockImplementation(async () => {
          const {streams} = await import("./test/fixtures/multi-period-streams/index.json");
          resolve();
          return streams;
        });
      }),
      getMultiPeriodStream: new Promise<void>(resolve => {
        apiRequestMock.getMultiPeriodStream.mockImplementation(async () => {
          const { model } = await import("./test/fixtures/multi-period-streams/demo.json");
          resolve();
          return model;
        });
      }),
      getContentRoles: new Promise<void>(resolve => {
        apiRequestMock.getContentRoles.mockImplementation(async () => {
          const roles = await import('./test/fixtures/content_roles.json');
          resolve();
          return roles.default;
        });
      })
    };
    document.body.innerHTML = '<div id="app" />';
    const app = document.getElementById('app');
    expect(app).not.toBeNull();
    baseElement = app as HTMLDivElement;
  });

  test("matches snapshot for home page", async () => {
    mockLocation.pathname = "/";
    useLocationSpy.mockReturnValue([mockLocation.pathname, setLocation]);
    const { asFragment, findByText } = render(
      <App tokens={initialTokens} user={user} />,
      { baseElement }
    );
    await Promise.all([promises.getAllManifests, promises.getAllStreams, promises.getAllMultiPeriodStreams]);
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
      <App tokens={initialTokens} user={user} />,
      { baseElement }
    );
    await promises.getAllMultiPeriodStreams;
    await findByText('first title');
    await findByText('Add a Stream');
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot for edit MPS", async () => {
    mockLocation.pathname = '/multi-period-streams/demo';
    useLocationSpy.mockReturnValue([mockLocation.pathname, setLocation]);
    const { asFragment, findByText } = render(
      <App tokens={initialTokens} user={user} />,
      { baseElement }
    );
    await Promise.all([promises.getAllStreams, promises.getMultiPeriodStream]);
    await findByText("Delete Stream");
    expect(asFragment()).toMatchSnapshot();
  });

  test("unknown page", () => {
    mockLocation.pathname = '/unknown';
    useLocationSpy.mockReturnValue([mockLocation.pathname, setLocation]);
    const { getByText } = render(
      <App tokens={initialTokens} user={user} />,
      { baseElement }
    );
    getByText("Sorry I don't know about this page");
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
      <App tokens={initialTokens} user={user}><StateSpy /></App>,
      { baseElement }
    );
    await Promise.all([promises.getAllManifests, promises.getAllStreams, promises.getAllMultiPeriodStreams]);
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
      <App tokens={initialTokens} user={user} />,
      { baseElement }
    );
    await Promise.all([promises.getAllManifests, promises.getAllStreams, promises.getAllMultiPeriodStreams]);
    await findByText("Stream to play");
    const elt = document.querySelector('a[href="/multi-period-streams"]');
    expect(elt).not.toBeNull();
    fireEvent.click(elt);
    expect(setLocation).toHaveBeenCalled();
    expect(setLocation).toHaveBeenCalledWith('/multi-period-streams');
  });
});
