import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";
import userEvent from "@testing-library/user-event";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { MpsPeriod } from "../../types/MpsPeriod";
import {
  AllStreamsContext,
  decorateAllStreams,
  UseAllStreamsHook,
} from "../../hooks/useAllStreams";
import { DecoratedStream } from "../../types/DecoratedStream";
import { PeriodRow } from "./PeriodRow";

import { streams } from "../../test/fixtures/streams.json";
import { model } from "../../test/fixtures/multi-period-streams/demo.json";
import {
  MpsModelValidationErrors,
  MultiPeriodModelContext,
  UseMultiPeriodStreamHook,
} from "../../hooks/useMultiPeriodStream";
import { DecoratedMultiPeriodStream } from "../../types/DecoratedMultiPeriodStream";

describe("PeriodRow component", () => {
  const allStreams = signal<DecoratedStream[]>([]);
  const loaded = signal<boolean>(false);
  const streamsMap = signal<Map<string, DecoratedStream>>(new Map());
  const error = signal<string | null>(null);
  const allStreamsHook: UseAllStreamsHook = {
    allStreams,
    loaded,
    streamsMap,
    error,
  };
  let multiPeriodStreamHook: UseMultiPeriodStreamHook;

  beforeEach(() => {
    loaded.value = true;
    error.value = null;
    allStreams.value = decorateAllStreams(streams);
    const sMap = new Map<string, DecoratedStream>();
    allStreams.value.forEach((item) => {
      sMap.set(`${item.pk}`, item);
    });
    streamsMap.value = sMap;
    multiPeriodStreamHook = mock<UseMultiPeriodStreamHook>({
      loaded: signal<string | undefined>(),
      model: signal<DecoratedMultiPeriodStream>(),
      modified: signal<boolean>(false),
      errors: signal<MpsModelValidationErrors>({}),
      isValid: signal<boolean>(false),
    });
    });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test.each(model.periods)(
    "matches snapshot for period $pid",
    async (item: MpsPeriod) => {
      const { asFragment, findByText } = renderWithProviders(
        <AllStreamsContext.Provider value={allStreamsHook}>
          <MultiPeriodModelContext.Provider value={multiPeriodStreamHook}>
            <PeriodRow index={2} item={item} className="guest-period-row" />
          </MultiPeriodModelContext.Provider>
        </AllStreamsContext.Provider>
      );
      const decStream = streamsMap.value.get(`${item.stream}`);
      expect(decStream).toBeDefined();
      await findByText(decStream.title);
      expect(asFragment()).toMatchSnapshot();
    }
  );

  test("opens track view dialog", () => {
    const period = model.periods[0];
    const { getBySelector, appState: state } = renderWithProviders(
      <AllStreamsContext.Provider value={allStreamsHook}>
        <MultiPeriodModelContext.Provider value={multiPeriodStreamHook}>
          <PeriodRow index={2} item={period} className="guest-period-row" />
        </MultiPeriodModelContext.Provider>
      </AllStreamsContext.Provider>
    );
    const elt = getBySelector(".period-tracks > .btn") as HTMLButtonElement;
    fireEvent.click(elt);
    const decStream = streamsMap.value.get(`${period.stream}`);
    expect(decStream).toBeDefined();
    expect(state.dialog.value).toEqual({
      backdrop: true,
      trackPicker: {
        pk: period.pk,
        pid: period.pid,
        guest: false,
        stream: decStream,
      },
    });
  });

  test('can set period ID', async () => {
    const user = userEvent.setup();
    const period = model.periods[0];
    const { getBySelector } = renderWithProviders(
      <AllStreamsContext.Provider value={allStreamsHook}>
        <MultiPeriodModelContext.Provider value={multiPeriodStreamHook}>
          <PeriodRow index={2} item={period} className="guest-period-row" />
        </MultiPeriodModelContext.Provider>
      </AllStreamsContext.Provider>
    );
    const pidElt = getBySelector(".period-id input") as HTMLInputElement;
    await user.clear(pidElt);
    await user.click(pidElt);
    await user.type(pidElt, 'hello{enter}');
    expect(multiPeriodStreamHook.modifyPeriod).toHaveBeenLastCalledWith({
      periodPk: period.pk,
      period: {
        pid: 'hello',
      },
    });
  });

  test('can select stream', async () => {
    const user = userEvent.setup();
    const period = model.periods[0];
    const { getBySelector } = renderWithProviders(
      <AllStreamsContext.Provider value={allStreamsHook}>
        <MultiPeriodModelContext.Provider value={multiPeriodStreamHook}>
          <PeriodRow index={2} item={period} className="guest-period-row" />
        </MultiPeriodModelContext.Provider>
      </AllStreamsContext.Provider>
    );
    const selElt = getBySelector(".period-stream select") as HTMLSelectElement;
    expect(selElt.value).toEqual(`${period.stream}`);
    const newPk = (period.stream + 1) % allStreams.value.length;
    const newStream = streamsMap.value.get(`${newPk}`);
    expect(newStream).toBeDefined();
    await user.selectOptions(selElt, [newStream.title]);
    expect(multiPeriodStreamHook.modifyPeriod).toHaveBeenLastCalledWith({
      periodPk: period.pk,
      period: {
        stream: newPk,
        duration: expect.any(String),
      },
      tracks: expect.any(Array),
    });
  });
});
