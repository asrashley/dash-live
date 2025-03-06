import { type ReadonlySignal, useComputed } from "@preact/signals";
import { useCallback, useContext } from "preact/hooks";
import { Link } from "wouter-preact";

import { Icon } from '../../components/Icon';
import { StreamOptionsContext } from '../types/StreamOptionsHook';
import { CombinedStream } from "../../hooks/useCombinedStreams";

interface ButtonRowProps {
   videoUrl: ReadonlySignal<URL>;
   stream: ReadonlySignal<CombinedStream>;
   viewing: ReadonlySignal<boolean>;
   setViewing: (flag: boolean) => void;
}

export function ButtonRow({ videoUrl, viewing, stream, setViewing }: ButtonRowProps) {
  const { resetAllValues } = useContext(StreamOptionsContext);
  const viewText = useComputed<string>(() => viewing.value ? "Change Options" : "View Manifest");
  const viewIcon = useComputed<string>(() => viewing.value ? "menu-button-wide": "eyeglasses");
  const onClickView = useCallback((ev: Event) => {
    ev.preventDefault();
    setViewing(!viewing.value);
  }, [setViewing, viewing]);

  return <div className="d-flex flex-row align-self-stretch pb-3">
    <div className="play-button flex-fill text-center">
      <Link className="btn btn-lg btn-primary" href={videoUrl.value.href}>
        <Icon name="play-fill" />
        <span className="title ps-2">Play {stream.value.title}</span>
      </Link>
    </div>
    <div className="view-manifest-button flex-fill text-center">
      <button className="btn btn-lg btn-primary" onClick={onClickView}>
        <Icon name={viewIcon.value} className="pe-2" />{viewText}
      </button>
    </div>
    <div className="reset-all-button flex-fill text-center">
      <button className="btn btn-lg btn-primary" onClick={resetAllValues}>
        <Icon name="trash3-fill" className="pe-2" />Reset Options
      </button>
    </div>
  </div>;
}
