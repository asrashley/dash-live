import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";
import { html } from "htm/preact";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../../test/renderWithProviders.js";
import { TrackSelectionDialog } from "./TrackSelectionDialog.js";
import { createAppState } from "../../appState.js";
import { MultiPeriodModelContext } from "../../hooks/useMultiPeriodStream.js";

describe("TrackSelectionDialog component", () => {
  const onClose = vi.fn();
  const userInfo = {
    isAuthenticated: true,
    groups: ["MEDIA"],
  };
  const state = createAppState(userInfo);
  const mpsContext = {
    model: signal(),
    modifyPeriod: vi.fn(),
  };
  const stream = {
    tracks: [
      {
        codec_fourcc: "avc1",
        content_type: "video",
        enabled: true,
        encrypted: false,
        lang: null,
        pk: 3,
        role: "main",
        track_id: 1,
      },
      {
        codec_fourcc: "mp4a",
        content_type: "audio",
        enabled: true,
        encrypted: false,
        lang: null,
        pk: 4,
        role: "main",
        track_id: 2,
      },
      {
        codec_fourcc: "ec3",
        content_type: "audio",
        enabled: false,
        encrypted: false,
        lang: null,
        pk: 5,
        role: "alternate",
        track_id: 3,
      },
    ],
  };
  const trackPicker = {
    pk: 2,
    pid: "p2",
    stream,
  };

  beforeEach(() => {
    state.dialog.value = {
        trackPicker: { ...trackPicker },
    };
    mpsContext.model.value = {
      periods: [],
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should display dialog box", async () => {
    const { getByText, asFragment } = renderWithProviders(
      html`<${MultiPeriodModelContext.Provider} value=${mpsContext}>
        <${TrackSelectionDialog} onClose=${onClose} />
      </${MultiPeriodModelContext.Provider}>`,
      { state }
    );
    getByText("Close");
    expect(asFragment()).toMatchSnapshot();
  });

  test("can close dialog box", async () => {
    const { getByText } = renderWithProviders(
      html`<${MultiPeriodModelContext.Provider} value=${mpsContext}>
        <${TrackSelectionDialog} onClose=${onClose} />
      </${MultiPeriodModelContext.Provider}>`,
      { state }
    );
    const btn = getByText("Close");
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("can select all tracks", async () => {
    const { getByTestId } = renderWithProviders(
      html`<${MultiPeriodModelContext.Provider} value=${mpsContext}>
        <${TrackSelectionDialog} onClose=${onClose} />
      </${MultiPeriodModelContext.Provider}>`,
      { state }
    );
    const inp = getByTestId("select-all-tracks");
    expect(inp.checked).toEqual(false);
    fireEvent.click(inp);
    expect(inp.checked).toEqual(true);
    expect(onClose).not.toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledTimes(stream.tracks.length);
    stream.tracks.forEach((trk, idx) => {
        expect(mpsContext.modifyPeriod).toHaveBeenNthCalledWith(idx + 1,
            {
            periodPk: trackPicker.pk,
            track: {
                ...trk,
                enabled: true,
            },
        });
    });
  });

  test("can toggle one track", async () => {
    const { getBySelector } = renderWithProviders(
      html`<${MultiPeriodModelContext.Provider} value=${mpsContext}>
        <${TrackSelectionDialog} onClose=${onClose} />
      </${MultiPeriodModelContext.Provider}>`,
      { state }
    );
    const inp = getBySelector("#id_enable_1");
    expect(inp.checked).toEqual(true);
    fireEvent.click(inp);
    expect(inp.checked).toEqual(false);
    expect(onClose).not.toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledWith({
        periodPk: trackPicker.pk,
        track: {
            ...stream.tracks[0],
            enabled: false,
        },
    });
  });

  test("can toggle encryption setting on one track", async () => {
    const { getBySelector } = renderWithProviders(
      html`<${MultiPeriodModelContext.Provider} value=${mpsContext}>
        <${TrackSelectionDialog} onClose=${onClose} />
      </${MultiPeriodModelContext.Provider}>`,
      { state }
    );
    const inp = getBySelector('input[name="enc_1"]');
    expect(inp.checked).toEqual(false);
    fireEvent.click(inp);
    expect(inp.checked).toEqual(true);
    expect(onClose).not.toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledWith({
        periodPk: trackPicker.pk,
        track: {
            ...stream.tracks[0],
            encrypted: true,
        },
    });
  });

  test("can change role of a track", async () => {
    const { getBySelector } = renderWithProviders(
      html`<${MultiPeriodModelContext.Provider} value=${mpsContext}>
        <${TrackSelectionDialog} onClose=${onClose} />
      </${MultiPeriodModelContext.Provider}>`,
      { state }
    );
    const inp = getBySelector('select[name="role_2"]');
    expect(inp.value).toEqual("main");
    fireEvent.change(inp, { target: { value: "alternate"}});
    expect(inp.value).toEqual("alternate");
    expect(onClose).not.toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledTimes(1);
    expect(mpsContext.modifyPeriod).toHaveBeenCalledWith({
        periodPk: trackPicker.pk,
        track: {
            ...stream.tracks[1],
            role: "alternate",
        },
    });
  });

  test("hide when not active", async () => {
    state.dialog.value = {};
    const { container } = renderWithProviders(
      html`<${MultiPeriodModelContext.Provider} value=${mpsContext}>
          <${TrackSelectionDialog} onClose=${onClose} />
        </${MultiPeriodModelContext.Provider}>`,
      { state }
    );
    expect(container.innerHTML).toEqual("");
  });
});
