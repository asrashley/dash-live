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
import { act, renderHook } from "@testing-library/preact";

import { useMultiPeriodStream, blankModel, decorateMultiPeriodStream } from "./useMultiPeriodStream";
import { ApiRequests, EndpointContext } from "../endpoints";
import { mock } from "vitest-mock-extended";
import { MultiPeriodStream } from "../types/MultiPeriodStream";
import { ModifyMultiPeriodStreamJson } from "../types/ModifyMultiPeriodStreamResponse";
import { model } from "../test/fixtures/multi-period-streams/demo.json";

const expectedModel = decorateMultiPeriodStream(model);

describe("useMultiPeriodStream hook", () => {
  const apiRequests = mock<ApiRequests>();
  const wrapper = ({ children }: { children: ComponentChildren }) => {
    return (
      <EndpointContext.Provider value={apiRequests}>
        {children}
      </EndpointContext.Provider>
    );
  };
  let getMultiPeriodStreamPromise;

  beforeEach(() => {
    getMultiPeriodStreamPromise = new Promise<void>((resolve) => {
      apiRequests.getMultiPeriodStream.mockImplementation(async () => {
        resolve();
        return model as MultiPeriodStream;
      });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  test("can update stream options", async () => {
    const { result } = renderHook(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { setFields } = result.current;
    act(() => {
      setFields({ options: { ntps: "asia-ntp", st: false } });
    });
    expect(result.current.model.value.options).toEqual({
      ntps: "asia-ntp",
      st: false,
    });
  });

  test("can discard changes", async () => {
    const { result } = renderHook(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { modifyPeriod, discardChanges } = result.current;
    modifyPeriod({
      periodPk: 2,
      track: {
        encrypted: true,
        role: "alternate",
        track_id: 2,
      },
    });
    expect(result.current.model.value).not.toEqual(expectedModel);
    act(() => {
      discardChanges();
    });
    expect(result.current.model.value).toEqual(expectedModel);
  });

  test("failure to request multi-period stream", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getMultiPeriodStream.mockImplementation(async () => {
        resolve();
        throw new Error("API Error");
      });
    });
    const { result } = renderHook(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { wrapper }
    );
    await act(async () => {
      await prom;
    });
    const { errors, loaded } = result.current;
    expect(loaded.value).toEqual("demo");
    expect(errors.value).toEqual(expect.objectContaining({
      fetch: 'Failed to get multi-period stream "demo": Error: API Error'
    }));
  });

  test("fetches model from server", async () => {
    const { result } = renderHook(
      () => useMultiPeriodStream({ name: "demo", newStream: false }),
      { wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { errors, loaded, modified } = result.current;
    expect(loaded.value).toEqual("demo");
    expect(modified.value).toEqual(false);
    expect(errors.value).toEqual({});
    expect(result.current.model.value).toEqual(expectedModel);
  });

  test("creates a blank model for a new stream", async () => {
    const { result } = renderHook(
      () => useMultiPeriodStream({ name: "demo", newStream: true }),
      { wrapper }
    );

    const { errors, loaded, modified } = result.current;
    expect(loaded.value).toEqual("demo");
    expect(modified.value).toEqual(false);
    expect(result.current.model.value).toEqual(decorateMultiPeriodStream(blankModel));
    expect(errors.value).toEqual({
      name: "Name is required",
      allPeriods: "At least one Period is required",
      title: "Title is required",
    });
    expect(apiRequests.getMultiPeriodStream).not.toHaveBeenCalled();
  });

  test("can add a period", async () => {
    const { result } = renderHook(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: true,
        }),
      { wrapper }
    );
    const { addPeriod, modified } = result.current;
    addPeriod();
    expect(modified.value).toEqual(true);
    expect(result.current.model.value).toEqual({
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

  test("can remove a period", async () => {
    const { result } = renderHook(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { removePeriod, modified } = result.current;
    removePeriod(expectedModel.periods[0].pk);
    expect(modified.value).toEqual(true);
    expect(result.current.model.value).toEqual({
      ...expectedModel,
      lastModified: expect.any(Number),
      modified: true,
      periods: [expectedModel.periods[1]],
    });
  });

  test("can modify a track within a period", async () => {
    const { result } = renderHook(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { modifyPeriod } = result.current;
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
    expect(result.current.model.value).not.toEqual(expectedModel);
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
    expect(result.current.model.value).toEqual({
      ...expectedModel,
      modified: true,
      lastModified: expect.any(Number),
      periods,
    });
  });

  test("can save changes", async () => {
    const { result } = renderHook(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { modifyPeriod, setFields, saveChanges } = result.current;
    act(() => {
      modifyPeriod({
        periodPk: 2,
        track: {
          encrypted: true,
          role: "alternate",
          track_id: 2,
        },
      });
      setFields({ title: "a new title" });
    });
    const model = structuredClone(result.current.model.value);
    const modifyMps: ModifyMultiPeriodStreamJson = {
      csrfTokens: undefined,
      errors: [],
      success: true,
      model,
    };
    apiRequests.modifyMultiPeriodStream.mockResolvedValueOnce(modifyMps);
    const controller = new AbortController();
    await expect(saveChanges({ signal: controller.signal })).resolves.toEqual(
      true
    );
  });

  test("fails to save changes", async () => {
    const { result } = renderHook(
      () =>
        useMultiPeriodStream({
          name: "demo",
          newStream: false,
        }),
      { wrapper }
    );
    await act(async () => {
      await getMultiPeriodStreamPromise;
    });
    const { modifyPeriod, saveChanges } = result.current;
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
    const model = structuredClone(result.current.model.value);
    const modifyMps: ModifyMultiPeriodStreamJson = {
      csrfTokens: undefined,
      errors: [
        'duplicate name',
      ],
      success: false,
      model,
    };
    apiRequests.modifyMultiPeriodStream.mockResolvedValueOnce(modifyMps);
    const controller = new AbortController();
    await expect(saveChanges({ signal: controller.signal })).resolves.toEqual(
      false
    );
  });
});
