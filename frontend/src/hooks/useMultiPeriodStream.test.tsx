import {
  afterAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";
import { type ComponentChildren } from "preact";
import { act } from "@testing-library/preact";

import { renderHookWithProviders } from "../test/renderHookWithProviders";
import { useMultiPeriodStream, blankModel } from "./useMultiPeriodStream";
import { ApiRequests, EndpointContext } from '../endpoints';
import { mock } from "vitest-mock-extended";
import { MultiPeriodStreamJson } from "../types/MultiPeriodStream";

const expectedModel = {
  name: "demo",
  options: { ntps: "europe-ntp", st: true },
  periods: [
    {
      duration: "PT1M4S",
      ordering: 1,
      parent: 1,
      pid: "p2",
      pk: 2,
      start: "PT0S",
      stream: 2,
      tracks: [
        {
          codec_fourcc: "avc1",
          content_type: "video",
          encrypted: false,
          lang: null,
          pk: 3,
          role: "main",
          track_id: 1,
          enabled: true,
        },
        {
          codec_fourcc: "mp4a",
          content_type: "audio",
          encrypted: false,
          lang: null,
          pk: 4,
          role: "main",
          track_id: 2,
          enabled: true,
        },
      ],
    },
    {
      duration: "PT51S",
      ordering: 2,
      parent: 1,
      pid: "p1",
      pk: 1,
      start: "PT0S",
      stream: 1,
      tracks: [
        {
          codec_fourcc: "avc3",
          content_type: "video",
          encrypted: false,
          lang: null,
          pk: 1,
          role: "main",
          track_id: 1,
          enabled: true,
        },
        {
          codec_fourcc: "mp4a",
          content_type: "audio",
          encrypted: false,
          lang: null,
          pk: 2,
          role: "main",
          track_id: 2,
          enabled: true,
        },
      ],
    },
  ],
  pk: 1,
  title: "first title",
  lastModified: 0,
  modified: false,
};

describe("useMultiPeriodStream hook", () => {
  const apiRequests = mock<ApiRequests>();
  const Wrapper = ({ children }: {children: ComponentChildren}) => {
    return <EndpointContext.Provider value={apiRequests}>{children}</EndpointContext.Provider>;
  };
  let getMultiPeriodStreamPromise;

  beforeEach(() => {
    getMultiPeriodStreamPromise = new Promise<void>((resolve) => {
      apiRequests.getMultiPeriodStream.mockImplementation(async () => {
        const data = await import("../test/fixtures/multi-period-streams/demo.json");
        resolve();
        return data.default as MultiPeriodStreamJson;
      });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  test("fetches model from server", async () => {
    const { result } = renderHookWithProviders(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { Wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { errors, loaded, modified } = result;
    expect(loaded.value).toEqual("demo");
    expect(modified.value).toEqual(false);
    expect(errors.value).toEqual({});
    expect(result.model.value).toEqual(expectedModel);
  });

  test("creates a blank model for a new stream", async () => {
    const { result } = renderHookWithProviders(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: true,
        }),
      { Wrapper }
    );
    const { errors, loaded, modified } = result;
    expect(loaded.value).toEqual("demo");
    expect(modified.value).toEqual(false);
    expect(result.model.value).toEqual(blankModel);
    expect(errors.value).toEqual({
      name: "Name is required",
      periods: {
        _: "At least one Period is required",
      },
      title: "Title is required",
    });
    expect(apiRequests.getMultiPeriodStream).not.toHaveBeenCalled();
  });

  test("can add a period", async () => {
    const { result } = renderHookWithProviders(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: true,
        }),
      { Wrapper }
    );
    const { addPeriod, modified } = result;
    addPeriod();
    expect(modified.value).toEqual(true);
    expect(result.model.value).toEqual({
      ...blankModel,
      lastModified: expect.any(Number),
      modified: true,
      periods: [
        {
          duration: "",
          new: true,
          ordering: 1,
          parent: null,
          pid: "p1",
          pk: "p1",
          start: "",
          stream: 0,
          tracks: [],
        },
      ],
    });
  });

  test("can modify a track within a period", async () => {
    const { result } = renderHookWithProviders(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { Wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { modifyPeriod } = result;
    act(() => {
      modifyPeriod({
        periodPk: 2,
        track: {
          encrypted: true,
          role: "alternate",
          track_id: 2,
        },
      });
    });
    expect(result.model.value).not.toEqual(expectedModel);
    const periods = [
      {
        ...expectedModel.periods[0],
        tracks: [
          expectedModel.periods[0].tracks[0],
          {
            ...expectedModel.periods[0].tracks[1],
            encrypted: true,
            role: "alternate",
          },
        ],
      },
      expectedModel.periods[1],
    ];
    expect(result.model.value).toEqual({
      ...expectedModel,
      modified: true,
      lastModified: expect.any(Number),
      periods,
    });
  });
});
