import { type ReadonlySignal, useComputed, useSignal } from "@preact/signals";
import { useCallback } from "preact/hooks";
import { MediaTrack } from "../types/MediaTrack";
import { Icon } from "../../components/Icon";
import { BooleanCell } from "../../components/BooleanCell";
import { MediaTrackType } from "../types/MediaTrackType";

function IsActive({active}: {active: boolean}) {
    if (!active) {
        return null;
    }
    return <div className="float-end"><BooleanCell value={true} /></div>;
}

interface TextTrackOptionProps {
  track: MediaTrack | null;
  index: number;
  active: boolean;
  setTrack: (track: MediaTrack | null) => void;
}

function TextTrackOption({
  index,
  track,
  active,
  setTrack,
}: TextTrackOptionProps) {
  const buttonLabel = track ?
    track.language
    ? `${index}: "${track.language}"`
    : `${index}: track ${track.id}` : '- off -';
  const className = `dropdown-item${active ? " fw-bold": ""}`;
  return (
    <li>
      <button className={className} onClick={() => setTrack(track)}>
        {buttonLabel}<IsActive active={active} />
      </button>
    </li>
  );
}

export interface TextTrackSelectionProps {
  tracks: ReadonlySignal<MediaTrack[]>;
  setTrack(track: MediaTrack | null): void;
}

export function TextTrackSelection({
  tracks,
  setTrack,
}: TextTrackSelectionProps) {
  const expanded = useSignal<boolean>(false);
  const textTracks = useComputed<MediaTrack[]>(() =>
    tracks.value.filter((trk) => trk.trackType === MediaTrackType.TEXT)
  );
  const textEnabled = useComputed<boolean>(() =>
    textTracks.value.some((trk) => trk.active)
  );
  const textIcon = useComputed<string>(() =>
    textEnabled.value ? "badge-cc-fill" : "badge-cc"
  );
  const toggleClasses = useComputed<string>(() => `btn btn-secondary dropdown-toggle${expanded.value ? " show": ""}`);
  const menuClasses = useComputed<string>(() => `dropdown-menu ${expanded.value ? " show": ""}`);
  const menuStyle = useComputed<string>(() => {
    if (!expanded.value) {
        return ''
    }
    return `position: absolute; transform: translateY(-${4 + textTracks.value.length}em)`;
  });

  const toggleExpanded = useCallback(() => {
    expanded.value = !expanded.value;
  }, [expanded]);

  const wrappedSetTrack = useCallback((track: MediaTrack | null) => {
    expanded.value = false;
    setTrack(track)
  }, [expanded, setTrack]);

  return (
    <div className="btn-group dropup">
      <button
        className={toggleClasses}
        data-testid="track-track-toggle"
        aria-expanded={expanded}
        onClick={toggleExpanded}>
        <Icon name={textIcon} />
      </button>
      <ul class={menuClasses} style={menuStyle}>
        <TextTrackOption
          track={null}
          index={-1}
          setTrack={wrappedSetTrack}
          active={!textEnabled.value}
        />
        {textTracks.value.map((trk: MediaTrack, index: number) => (
          <TextTrackOption
            key={trk.id}
            index={index}
            track={trk}
            active={trk.active}
            setTrack={wrappedSetTrack}
          />
        ))}
      </ul>
    </div>
  );
}
