import { useComputed, type ReadonlySignal } from "@preact/signals";
import { DecoratedStream } from "../../types/DecoratedStream";
import { MpsPeriod } from "../../types/MpsPeriod";
import { MpsTrack } from "../../types/MpsTrack";

function tracksDescription(tracks: MpsTrack[], stream: ReadonlySignal<DecoratedStream|undefined>) {
  const enabledCount = tracks.filter(tk => tk.enabled).length;
  const numTracks = stream.value?.tracks.length ?? 0;
  if (numTracks === 0) {
    return "----";
  }
  if (tracks.length === 1 && numTracks === 1) {
    return "1 track";
  }
  return `${enabledCount}/${numTracks} tracks`;
}

export interface TrackSelectionButtonProps {
  period: MpsPeriod;
  stream: ReadonlySignal<DecoratedStream | undefined>;
  selectTracks: (ev: Event) => void;
}

export function TrackSelectionButton({ period, stream, selectTracks }: TrackSelectionButtonProps) {
  const { tracks } = period;
  const description = useComputed<string>(() => tracksDescription(tracks, stream));
  const hasActiveTracks = tracks.some(tk => tk.enabled);
  const disabled = useComputed<boolean>(() => stream.value === undefined);
  const className = useComputed<string>(
    () => `btn btn-sm m-1 ${hasActiveTracks ? "btn-success" : "btn-warning"}${disabled.value ? ' disabled': ''}`
  );

  return <div className="col period-tracks">
  <button className={className} onClick={selectTracks} disabled={disabled} aria-disabled={disabled}>
    {description}
  </button>
</div>;
}

