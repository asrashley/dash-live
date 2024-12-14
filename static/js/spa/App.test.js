import { afterAll, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";
import { render } from "@testing-library/preact";

import { ApiRequests } from "./endpoints.js";
import { App } from "./App.js";

vi.mock('./endpoints.js', async (importOriginal) => {
  const ApiRequests = vi.fn();
  ApiRequests.prototype.getAllManifests = vi.fn();
  ApiRequests.prototype.getAllMultiPeriodStreams = vi.fn();
  ApiRequests.prototype.getAllStreams = vi.fn();
  ApiRequests.prototype.getMultiPeriodStream = vi.fn();
  return {
    ...await importOriginal(),
    ApiRequests,
   };
});

describe("main entry-point app", () => {
  const initialTokens = {
    accessToken: {
      expires: "2024-12-14T16:42:22.606208Z",
      jti: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTczNDE4NzM0MiwianRpIjoiYmJiYzRmZGQtODk5Ni00Zjg0LThlNjAtOTBiNjU4ZWViYjQ0IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImFkbWluIiwibmJmIjoxNzM0MTg3MzQyLCJjc3JmIjoiODVhMmFlNjktNzJlZi00OTgyLTg0YzktNjM2ZGQ0ZjAwMTZhIiwiZXhwIjoxNzM0MTg4MjQyfQ.7drJGq_ZVEkqOAO9R1JOPPNjpHHPv-mlopAlweRblJs",
    },
    csrfTokens: {
      files: null,
      kids: null,
      streams: "afU1XsoYb%27jhIBvJbHhwNJ1/Dq3Bqamj174Gk%3D%27",
      upload: null,
    },
    refreshToken: {
      expires: "2024-12-21T14:42:22.611946Z",
      jti: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTczNDE4NzM0MiwianRpIjoiODI4OWYxMTUtMzg4OC00ODVkLTlmMWUtZWM2YzAwMzA1N2RiIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImFkbWluIiwibmJmIjoxNzM0MTg3MzQyLCJjc3JmIjoiYjJiMjI4ZTgtZjliMS00ODc5LThhMTAtNzZkZmU1OWI4Mjc4IiwiZXhwIjoxNzM0MTg4MjQyfQ.LOuYwbGVbnyQUMCJJ4b0E0Jm0bGO41z07b9ZTa-l34c",
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
  };
  let baseElement;
  let promises;

  beforeAll(() => {
    vi.stubGlobal('location', mockLocation);
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    promises = {
      getAllManifests: new Promise(resolve => {
        ApiRequests.prototype.getAllManifests.mockImplementation(async () => {
          const manifests = await import("../mocks/manifests.json");
          resolve();
          return manifests;
        });
      }),
      getAllStreams: new Promise(resolve => {
        ApiRequests.prototype.getAllStreams.mockImplementation(async () => {
          const streams = await import("../mocks/streams.json");
          resolve();
          return streams;
        });
      }),
      getAllMultiPeriodStreams: new Promise(resolve => {
        ApiRequests.prototype.getAllMultiPeriodStreams.mockImplementation(async () => {
          const streams = await import("../mocks/multi-period-streams.json");
          resolve();
          return streams;
        });
      }),
      getMultiPeriodStream: new Promise(resolve => {
        ApiRequests.prototype.getMultiPeriodStream.mockImplementation(async () => {
          const demo = await import("../mocks/demo-mps.json");
          resolve();
          return demo;
        });
      }),
    };
    document.body.innerHTML = `<header><nav class="breadcrumbs"><ol class="breadcrumb" /></nav></header>
    <div class="content"><div id="app" /></div>
    <div class="modal-backdrop" />`;
    baseElement = document.getElementById('app');
  });

  test("matches snapshot for home page", async () => {
    mockLocation.pathname = "/";
    const { asFragment, findByText } = render(
      html`<${App} tokens=${initialTokens} user=${user} />`,
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
    const { asFragment, findByText } = render(
      html`<${App} tokens=${initialTokens} user=${user} />`,
      { baseElement }
    );
    await promises.getAllMultiPeriodStreams;
    await findByText('first title');
    await findByText('Add a Stream');
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot for edit MPS", async () => {
    mockLocation.pathname = '/multi-period-streams/demo';
    const { asFragment, findByText } = render(
      html`<${App} tokens=${initialTokens} user=${user} />`,
      { baseElement }
    );
    await Promise.all([promises.getAllStreams, promises.getMultiPeriodStream]);
    await findByText("Delete Stream");
    expect(asFragment()).toMatchSnapshot();
  });
});
