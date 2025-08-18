import { type ReadonlySignal, useComputed } from "@preact/signals";
import { PlaybackIconType } from "../types/PlaybackIconType";
import { Icon } from "../../components/Icon";

export interface PlaybackIconProps {
  active: ReadonlySignal<PlaybackIconType | null>;
}

export function PlaybackIcon({ active }: PlaybackIconProps) {
  const name = useComputed<string | null>(() => {
    const act = active.value;
    if (act === null) {
      return null;
    }
    if (act === "backward" || act === "forward") {
      return `skip-${act}-fill`;
    }
    return `${act}-fill`;
  });

  if (name.value === null) {
    return null;
  }
  return <Icon name={name} />;
}
