import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import {
  AllStreamsContext,
  decorateAllStreams,
  UseAllStreamsHook,
} from "../../hooks/useAllStreams";
import { DecoratedStream } from "../../types/DecoratedStream";
import { StreamSelection } from "./StreamSelection";

import { streams } from "../../test/fixtures/streams.json";

describe("StreamSelection component", () => {
  const allStreams = signal<DecoratedStream[]>([]);
  const loaded = signal<boolean>(false);
  const streamsMap = signal<Map<string, DecoratedStream>>(new Map());
  const error = signal<string | null>(null);
  const useAllStreamsHookMock: UseAllStreamsHook = {
    allStreams,
    loaded,
    streamsMap,
    error,
  };
  const onChange = vi.fn();
  const decoratedStreams = decorateAllStreams(streams);
  const value = signal<DecoratedStream | undefined>(decoratedStreams[0]);

  beforeEach(() => {
    allStreams.value = decoratedStreams;
    value.value = decoratedStreams[0];
    loaded.value = true;
    error.value = null;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", () => {
    const { asFragment, getBySelector } = renderWithProviders(
      <AllStreamsContext.Provider value={useAllStreamsHookMock}>
        <StreamSelection
          name="sel"
          required
          value={value}
          onChange={onChange}
        />
      </AllStreamsContext.Provider>
    );
    expect(getBySelector('select').className).toEqual('form-select is-valid');
    expect(asFragment()).toMatchSnapshot();
  });

  test('select with an error', () => {
    const streamSelectionError = signal<string | undefined>("value is bad");
    const { getBySelector } = renderWithProviders(
        <AllStreamsContext.Provider value={useAllStreamsHookMock}>
          <StreamSelection
            name="sel"
            required
            value={value}
            onChange={onChange}
            error={streamSelectionError}
          />
        </AllStreamsContext.Provider>
      );
      expect(getBySelector('select').className).toEqual('form-select is-invalid');
  });

  test('select with no value', () => {
    value.value = undefined;
    const { getBySelector } = renderWithProviders(
        <AllStreamsContext.Provider value={useAllStreamsHookMock}>
          <StreamSelection
            name="sel"
            value={value}
            required
            onChange={onChange}
          />
        </AllStreamsContext.Provider>
      );
      expect(getBySelector('select').className).toEqual('form-select');
  });

  test('change value', async () => {
    const user = userEvent.setup();
    const { getBySelector } = renderWithProviders(
        <AllStreamsContext.Provider value={useAllStreamsHookMock}>
          <StreamSelection
            name="sel"
            required
            value={value}
            onChange={onChange}
          />
        </AllStreamsContext.Provider>
      );
      const elt = getBySelector('select') as HTMLSelectElement;
      await user.selectOptions(elt, [decoratedStreams[1].title]);
      expect(onChange).toHaveBeenCalledTimes(1);
      expect(onChange).toHaveBeenCalledWith({ name: "sel", value: decoratedStreams[1].pk});
  });
});
