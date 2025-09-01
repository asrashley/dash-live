import { useComputed, type ReadonlySignal } from "@preact/signals";

import { createTimeObject, timeObjectToString } from "../utils/formatTimecode";
import { Icon } from "../../components/Icon";
import { PlayerControls } from "../types/PlayerControls";
import { MediaTrack } from "../types/MediaTrack";
import { TextTrackSelection } from "./TextTrackSelection";

export interface PlaybackControlsProps {
  currentTime: ReadonlySignal<number>;
  controls: ReadonlySignal<PlayerControls | null>;
  tracks: ReadonlySignal<MediaTrack[]>;
  setTextTrack: (track: MediaTrack | null) => void;
}

export function PlaybackControls({
  currentTime,
  controls,
  tracks,
  setTextTrack,
}: PlaybackControlsProps) {
  const hasPlayer = useComputed<boolean>(() => {
    return controls.value?.hasPlayer.value === true;
  });
  const timeCodeText = useComputed<string>(() => {
    if (!hasPlayer.value) {
        return '--:--:--';
    }
    return timeObjectToString(createTimeObject(currentTime.value))
  });
  const playPauseIcon = useComputed<string>(() =>
    hasPlayer.value && !controls.value?.isPaused.value ? "pause-fill" : "play-fill"
  );
  const disablePlayBtn = useComputed<boolean>(() => !controls.value);
  const disableTrickButtons = useComputed<boolean>(() => !hasPlayer.value);

  const playPause = () => {
    const player = controls.value;
    if (!player.hasPlayer.value || player.isPaused.value) {
      player.play();
    } else {
      player.pause();
    }
  };

  const skipBackwards = () => {
    controls.value?.skip(-15);
  };

  const stop = () => {
    controls.value?.stop();
  };

  const skipForward = () => {
    controls.value?.skip(15);
  };

  return (
    <div
      id="playback-controls"
      data-testid="playback-controls"
      className="d-flex flex-row btn-group border border-secondary">
      <button class="btn btn-secondary pe-1" disabled={disablePlayBtn} onClick={playPause} data-testid="play-pause-btn">
        <Icon name={playPauseIcon} />
      </button>
      <button
        class="btn btn-secondary"
        onClick={skipBackwards}
        disabled={disableTrickButtons} data-testid="skip-back-btn">
        <Icon name="skip-backward-fill" />
      </button>
      <button
        class="btn btn-secondary"
        onClick={stop}
        disabled={disableTrickButtons}  data-testid="stop-btn">
        <Icon name="stop-fill" />
      </button>
      <button
        class="btn btn-secondary"
        onClick={skipForward}
        disabled={disableTrickButtons}  data-testid="skip-fwd-btn">
        <Icon name="skip-forward-fill" />
      </button>
      <TextTrackSelection tracks={tracks} setTrack={setTextTrack} />
      <div className="play-position flex-grow-1">{timeCodeText}</div>
    </div>
  );
}
