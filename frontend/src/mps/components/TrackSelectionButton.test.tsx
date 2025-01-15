import { describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";

import { MpsPeriod } from "../../types/MpsPeriod";
import { DecoratedStream } from "../../types/DecoratedStream";
import { decorateAllStreams } from "../../hooks/useAllStreams";
import { renderWithProviders } from "../../test/renderWithProviders";
import { TrackSelectionButton } from "./TrackSelectionButton";
import { MpsTrack } from "../../types/MpsTrack";

import { streams } from "../../test/fixtures/streams.json";

describe("TrackSelectionButton component", () => {
  const dStream: DecoratedStream = decorateAllStreams(streams)[0];
  const tracks: MpsTrack[] = [{
    ...dStream.tracks[0],
    encrypted: false,
    lang: null,
    pk: 23,
    role: "main",
    enabled: true,
  }, {
    ...dStream.tracks[1],
    encrypted: false,
    lang: "en-gb",
    pk: 34,
    role: "main",
    enabled: true,
  }, {
    ...dStream.tracks[2],
    encrypted: false,
    lang: "en-gb",
    pk: 45,
    role: "alternate",
    enabled: false,
  }];
  const period: MpsPeriod = {
    duration: "PT30S",
    ordering: 1,
    parent: 1,
    pid: "p1",
    pk: 5,
    start: "PT0S",
    stream: dStream.pk,
    tracks,
  };
  const selectTracks = vi.fn();

  test("no selected stream", () => {
    const { getByText, getBySelector } = renderWithProviders(
      <TrackSelectionButton period={period} selectTracks={selectTracks} />
    );
    getByText("----");
    const elt = getBySelector('.btn') as HTMLAnchorElement;
    expect(elt.classList.contains('disabled')).toEqual(true);
  });

  test("no selected tracks", () => {
    const prd = structuredClone(period);
    prd.tracks[0].enabled = false;
    prd.tracks[1].enabled = false;
    const { getByText, getBySelector } = renderWithProviders(
      <TrackSelectionButton period={prd} selectTracks={selectTracks} />
    );
    getByText("----");
    const elt = getBySelector('.btn') as HTMLAnchorElement;
    expect(elt.classList.contains('disabled')).toEqual(true);
    expect(elt.classList.contains('btn-warning')).toEqual(true);
  });

  test("one selected track in a stream", () => {
    const prd = structuredClone(period);
    prd.tracks = [period.tracks[0]];
    const dStream2 = structuredClone(dStream);
    dStream2.tracks = [dStream.tracks[0]];
    const { getByText } = renderWithProviders(
      <TrackSelectionButton
        period={prd}
        stream={dStream2}
        selectTracks={selectTracks}
      />
    );
    getByText("1 track");
  });

  test("1/3 selected tracks", () => {
    const prd = structuredClone(period);
    prd.tracks[1].enabled = false;
    const { getByText } = renderWithProviders(
      <TrackSelectionButton
        period={prd}
        stream={dStream}
        selectTracks={selectTracks}
      />
    );
    getByText("1/3 tracks");
  });

  test("2/3 selected tracks", () => {
    const { getByText } = renderWithProviders(
      <TrackSelectionButton
        period={period}
        stream={dStream}
        selectTracks={selectTracks}
      />
    );
    getByText("2/3 tracks");
  });

  test('change selection', () => {
    const { getBySelector } = renderWithProviders(
        <TrackSelectionButton
          period={period}
          stream={dStream}
          selectTracks={selectTracks}
        />
      );
      const elt = getBySelector('.btn') as HTMLAnchorElement;
      expect(elt.classList.contains('btn-success')).toEqual(true);
      fireEvent.click(elt);
      expect(selectTracks).toHaveBeenCalledTimes(1);
    });
});
