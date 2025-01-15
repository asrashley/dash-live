import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { MpsPeriod } from "../../types/MpsPeriod";
import {
  AllStreamsContext,
  decorateAllStreams,
  UseAllStreamsHook,
} from "../../hooks/useAllStreams";
import { DecoratedStream } from "../../types/DecoratedStream";
import { GuestPeriodRow } from "./GuestPeriodRow";

import { streams } from "../../test/fixtures/streams.json";
import { model } from "../../test/fixtures/multi-period-streams/demo.json";

describe("GuestPeriodRow component", () => {
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

  beforeEach(() => {
    loaded.value = true;
    error.value = null;
    allStreams.value = decorateAllStreams(streams);
    const sMap = new Map<string, DecoratedStream>();
    allStreams.value.forEach((item) => {
      sMap.set(`${item.pk}`, item);
    });
    streamsMap.value = sMap;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test.each(model.periods)(
    "matches snapshot for period $pid",
    async (item: MpsPeriod) => {
      const { asFragment, findByText } = renderWithProviders(
        <AllStreamsContext.Provider value={allStreamsHook}>
          <GuestPeriodRow index={2} item={item} className="guest-period-row" />
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
    const { getBySelector, state } = renderWithProviders(
      <AllStreamsContext.Provider value={allStreamsHook}>
        <GuestPeriodRow index={2} item={period} className="guest-period-row" />
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
        guest: true,
        stream: decStream,
      },
    });
  });
});
