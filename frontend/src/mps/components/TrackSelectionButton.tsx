import { DecoratedStream } from "../../types/DecoratedStream";
import { MpsPeriod } from "../../types/MpsPeriod";
import { MpsTrack } from "../../types/MpsTrack";

function tracksDescription(tracks: MpsTrack[], stream?: DecoratedStream) {
  const enabledCount = tracks.filter(tk => tk.enabled).length;
  const numTracks = stream?.tracks.length ?? 0;
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
  stream?: DecoratedStream;
  selectTracks: (ev: Event) => void;
}

export function TrackSelectionButton({ period, stream, selectTracks }: TrackSelectionButtonProps) {
  const { tracks } = period;
  const description = tracksDescription(tracks, stream);
  const hasActiveTracks = tracks.some(tk => tk.enabled);
  const disabled = stream === undefined;
  const className = `btn btn-sm m-1 ${hasActiveTracks ? "btn-success" : "btn-warning"}${disabled ? ' disabled': ''}`;

  return <div className="col period-tracks">
  <button className={className} onClick={selectTracks} disabled={disabled} aria-disabled={disabled}>
    {description}
  </button>
</div>;
}

