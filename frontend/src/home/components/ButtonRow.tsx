import { type ReadonlySignal, useComputed } from "@preact/signals";
import { useCallback, useContext } from "preact/hooks";

import { Icon } from "../../components/Icon";
import { StreamOptionsContext } from "../types/StreamOptionsHook";
import { CombinedStream } from "../../hooks/useCombinedStreams";
import { PlayVideoButton } from "./PlayVideoButton";

interface ButtonRowProps {
  videoUrl: ReadonlySignal<URL>;
  stream: ReadonlySignal<CombinedStream>;
  viewing: ReadonlySignal<boolean>;
  setViewing: (flag: boolean) => void;
}

export function ButtonRow({
  videoUrl,
  viewing,
  stream,
  setViewing,
}: ButtonRowProps) {
  const { resetAllValues } = useContext(StreamOptionsContext);
  const viewText = useComputed<string>(() =>
    viewing.value ? "Change Options" : "View Manifest"
  );
  const viewIcon = useComputed<string>(() =>
    viewing.value ? "menu-button-wide" : "eyeglasses"
  );
  const onClickView = useCallback(
    (ev: Event) => {
      ev.preventDefault();
      setViewing(!viewing.value);
    },
    [setViewing, viewing]
  );

  return (
    <div className="d-flex flex-row align-self-stretch pb-3">
      <div className="play-button flex-fill text-center">
        <PlayVideoButton stream={stream} videoUrl={videoUrl} />
      </div>
      <div className="view-manifest-button flex-fill text-center">
        <button className="btn btn-lg btn-primary" onClick={onClickView}>
          <Icon name={viewIcon.value} className="pe-2" />
          {viewText}
        </button>
      </div>
      <div className="reset-all-button flex-fill text-center">
        <button className="btn btn-lg btn-primary" onClick={resetAllValues}>
          <Icon name="trash3-fill" className="pe-2" />
          Reset Options
        </button>
      </div>
    </div>
  );
}
