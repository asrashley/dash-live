import { describe, expect, test } from "vitest";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { VideoPlayer } from "./VideoPlayer";
import { DashParameters } from "../types/DashParameters";
import { KeyParameters } from "../types/KeyParameters";
import { PlayerControls } from "../types/PlayerControls";
import { StatusEvent } from "../types/StatusEvent";

describe("VideoPlayer component", () => {
  const params: DashParameters = {
    dash: {
      locationURL: "https://unit.test.local/test.mpd",
      mediaDuration: "PT30S",
      minBufferTime: "PT4S",
      mpd_id: "mpd-id",
      now: "2025-04-05T01:02:03Z",
      periods: [],
      profiles: [],
      publishTime: "2025-01-01T00:00:00Z",
      startNumber: 1,
      suggestedPresentationDelay: 0,
      timeSource: null,
      title: "VideoElement test",
    },
    options: {},
    url: "https://unit.test.local/test.mpd",
  };
  const dashParams = signal<DashParameters>(params);
  const keys = signal<Map<string, KeyParameters>>(new Map());
  const currentTime = signal<number>(0);
  const controls = signal<PlayerControls | undefined>();
  const events = signal<StatusEvent[]>([]);

  test("matches snapshot", () => {
    const { asFragment } = renderWithProviders(<VideoPlayer
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        events={events}
    />);
    expect(asFragment()).toMatchSnapshot();
  });
});
