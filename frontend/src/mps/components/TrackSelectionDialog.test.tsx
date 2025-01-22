import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock } from "vitest-mock-extended";
import { signal } from "@preact/signals";
import { act, fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../../test/renderWithProviders";
import { TrackSelectionDialog } from "./TrackSelectionDialog";
import { createAppState } from "../../appState";
import {
  MpsModelValidationErrors,
  MultiPeriodModelContext,
  UseMultiPeriodStreamHook,
} from "../../hooks/useMultiPeriodStream";
import { TrackPickerDialogState } from "../../types/DialogState";
import { DecoratedStream } from "../../types/DecoratedStream";
import { ApiRequests, EndpointContext } from "../../endpoints";
import { ContentRolesMap } from "../../types/ContentRolesMap";
import { MpsPeriod } from "../../types/MpsPeriod";
import { StreamTrack } from "../../types/StreamTrack";
import { DecoratedMultiPeriodStream } from "../../types/DecoratedMultiPeriodStream";

describe("TrackSelectionDialog component", () => {
  const onClose = vi.fn();
  const appState = createAppState();
  const model = signal<DecoratedMultiPeriodStream>();
  const loaded = signal<string | undefined>();
  const modified = signal<boolean>(false);
  const errors = signal<MpsModelValidationErrors>({});
  const isValid = signal<boolean>(true);
  const mpsContext: UseMultiPeriodStreamHook = {
    model,
    errors,
    loaded,
    modified,
    isValid,
    setFields: vi.fn(),
    addPeriod: vi.fn(),
    setPeriodOrdering: vi.fn(),
    removePeriod: vi.fn(),
    modifyPeriod: vi.fn(),
    saveChanges: vi.fn(),
    deleteStream: vi.fn(),
    discardChanges: vi.fn(),
  };
  const stream: DecoratedStream = {
    tracks: [
      {
        codec_fourcc: "avc1",
        content_type: "video",
        track_id: 1,
        clearBitrates: 3,
        encryptedBitrates: 3,
      },
      {
        codec_fourcc: "mp4a",
        content_type: "audio",
        clearBitrates: 1,
        encryptedBitrates: 0,
        track_id: 2,
      },
      {
        codec_fourcc: "ec3",
        content_type: "audio",
        clearBitrates: 1,
        encryptedBitrates: 0,
        track_id: 3,
      },
    ],
    defaults: null,
    directory: "demo",
    duration: "PT9M",
    marlin_la_url: "",
    media_files: [],
    pk: 10,
    playready_la_url: "",
    timing_ref: undefined,
    title: "stream title",
  };
  const mpsPeriod: MpsPeriod = {
    pk: 5,
    duration: "",
    ordering: 0,
    parent: 0,
    pid: "pid1",
    start: "",
    stream: 10,
    tracks: [{
      ...stream.tracks[0],
      encrypted: false,
      lang: "",
      pk: 15,
      role: "main"
    },
    {
      ...stream.tracks[1],
      encrypted: false,
      lang: "",
      pk: 16,
      role: "main"
    },
    {
      ...stream.tracks[2],
      encrypted: false,
      lang: "",
      pk: 17,
      role: "alternate"
    }]
  };
  const trackPicker: TrackPickerDialogState = {
    pk: mpsPeriod.pk,
    pid: mpsPeriod.pid,
    guest: false,
    stream,
  };
  const apiRequests = mock<ApiRequests>();
  let rolesPromise: Promise<void>;

  beforeEach(() => {
    appState.dialog.value = {
      backdrop: true,
      trackPicker: { ...trackPicker },
    };
    model.value = {
      pk: 12,
      name: "test",
      title: "mps title",
      periods: [mpsPeriod],
      options: null,
      modified: false,
      lastModified: 0,
    };
    rolesPromise = new Promise<void>((resolve) => {
      apiRequests.getContentRoles.mockImplementation(async () => {
        const data = await import("../../test/fixtures/content_roles.json");
        resolve();
        return data.default as ContentRolesMap;
      });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should display dialog box", async () => {
    const { findByText, asFragment } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <MultiPeriodModelContext.Provider value={mpsContext}>
          <TrackSelectionDialog onClose={onClose} />
        </MultiPeriodModelContext.Provider>
      </EndpointContext.Provider>,
      { appState }
    );
    await act(async () => {
      await rolesPromise;
    });
    await findByText("Close");
    expect(asFragment()).toMatchSnapshot();
  });

  test("can close dialog box", () => {
    const { getByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <MultiPeriodModelContext.Provider value={mpsContext}>
          <TrackSelectionDialog onClose={onClose} />
        </MultiPeriodModelContext.Provider>
      </EndpointContext.Provider>,
      { appState }
    );
    const btn = getByText("Close") as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("can select all tracks", async () => {
    const tracks = [
      mpsPeriod.tracks[0],
      mpsPeriod.tracks[1],
    ]
    const prd = {
      ...mpsPeriod,
      tracks,
    };
    model.value = {
      pk: 12,
      name: "test",
      title: "mps title",
      periods: [prd],
      options: null,
      modified: false,
      lastModified: 0,
    };

    const { getByTestId } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <MultiPeriodModelContext.Provider value={mpsContext}>
          <TrackSelectionDialog onClose={onClose} />
        </MultiPeriodModelContext.Provider>
      </EndpointContext.Provider>,
      { appState }
    );
    await act(async () => {
      await rolesPromise;
    });
    const inp = getByTestId("select-all-tracks") as HTMLInputElement;
    expect(inp.checked).toEqual(false);
    fireEvent.click(inp);
    expect(inp.checked).toEqual(true);
    expect(onClose).not.toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledTimes(stream.tracks.length);
    stream.tracks.forEach((trk: StreamTrack, idx: number) => {
      expect(mpsContext.modifyPeriod).toHaveBeenNthCalledWith(idx + 1, {
        periodPk: trackPicker.pk,
        track: expect.objectContaining({
          ...trk,
          enabled: true,
        }),
      });
    });
  });

  test("can toggle one track", async () => {
    const { getBySelector } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <MultiPeriodModelContext.Provider value={mpsContext}>
          <TrackSelectionDialog onClose={onClose} />
        </MultiPeriodModelContext.Provider>
      </EndpointContext.Provider>,
      { appState }
    );
    await act(async () => {
      await rolesPromise;
    });
    const inp = getBySelector("#id_enable_1") as HTMLInputElement;
    expect(inp.checked).toEqual(true);
    fireEvent.click(inp);
    expect(inp.checked).toEqual(false);
    expect(onClose).not.toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledWith({
      periodPk: trackPicker.pk,
      track: {
        ...mpsPeriod.tracks[0],
        enabled: false,
      },
    });
  });

  test("can toggle encryption setting on one track", async () => {
    const { findBySelector } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <MultiPeriodModelContext.Provider value={mpsContext}>
          <TrackSelectionDialog onClose={onClose} />
        </MultiPeriodModelContext.Provider>
      </EndpointContext.Provider>,
      { appState }
    );
    await act(async () => {
      await rolesPromise;
    });
    const inp = await findBySelector('input[name="enc_1"]') as HTMLInputElement;
    expect(inp.checked).toEqual(false);
    fireEvent.click(inp);
    expect(inp.checked).toEqual(true);
    expect(onClose).not.toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledWith({
      periodPk: trackPicker.pk,
      track: {
        ...mpsPeriod.tracks[0],
        encrypted: true,
        enabled: true,
      },
    });
  });

  test("can change role of a track", async () => {
    const { getBySelector } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <MultiPeriodModelContext.Provider value={mpsContext}>
          <TrackSelectionDialog onClose={onClose} />
        </MultiPeriodModelContext.Provider>
      </EndpointContext.Provider>,
      { appState }
    );
    await act(async () => {
      await rolesPromise;
    });
    const inp = getBySelector('select[name="role_2"]') as HTMLInputElement;
    expect(inp.value).toEqual("main");
    fireEvent.change(inp, { target: { value: "alternate" } });
    expect(inp.value).toEqual("alternate");
    expect(onClose).not.toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledWith({
      periodPk: trackPicker.pk,
      track: {
        ...mpsPeriod.tracks[1],
        enabled: true,
        role: "alternate",
      },
    });
  });

  test("hide when not active", () => {
    appState.dialog.value = {
      backdrop: false,
    };
    const { container } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <MultiPeriodModelContext.Provider value={mpsContext}>
          <TrackSelectionDialog onClose={onClose} />
        </MultiPeriodModelContext.Provider>
      </EndpointContext.Provider>,
      { appState }
    );
    expect(container.innerHTML).toEqual("");
  });
});
