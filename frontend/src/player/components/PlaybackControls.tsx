import { useComputed, type ReadonlySignal } from "@preact/signals";

import { createTimeObject, timeObjectToString } from "../utils/formatTimecode";
import { Icon } from "../../components/Icon";
import { PlayerControls } from "../types/PlayerControls";

export interface PlaybackControlsProps {
  currentTime: ReadonlySignal<number>;
  controls: ReadonlySignal<PlayerControls | null>;
}

export function PlaybackControls({
  currentTime,
  controls,
}: PlaybackControlsProps) {
  const timecode = useComputed<string>(() => {
    if (!controls.value?.hasPlayer.value) {
        return '--:--:--';
    }
    return timeObjectToString(createTimeObject(currentTime.value))
  });
  const playPauseIcon = useComputed<string>(() =>
    controls.value?.hasPlayer.value && !controls.value?.isPaused.value ? "pause-fill" : "play-fill"
  );
  const disableButtons = useComputed<boolean>(
    () => controls.value?.hasPlayer.value !== true
  );

  const playPause = () => {
    const player = controls.value;
    if (!player) {
      return;
    }
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
      <button class="btn btn-secondary pe-1" onClick={playPause}>
        <Icon name={playPauseIcon} />
      </button>
      <button
        class="btn btn-secondary"
        onClick={skipBackwards}
        disabled={disableButtons}>
        <Icon name="skip-backward-fill" />
      </button>
      <button
        class="btn btn-secondary"
        onClick={stop}
        disabled={disableButtons}>
        <Icon name="stop-fill" />
      </button>
      <button
        class="btn btn-secondary"
        onClick={skipForward}
        disabled={disableButtons}>
        <Icon name="skip-forward-fill" />
      </button>
      <div className="play-position flex-grow-1">{timecode}</div>
    </div>
  );
}
