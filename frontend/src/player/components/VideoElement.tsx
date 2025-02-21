import { Component, createRef } from "preact";
import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { DashPlayer } from "../types/DashPlayer";

export interface VideoElementProps {
  mpd: string;
  player: DashPlayerTypes;
  playerVersion?: number;
}

interface VideoElementState {
  player?: DashPlayer;
}

export class VideoElement extends Component<
  VideoElementProps,
  VideoElementState
> {
    private videoElt = createRef<HTMLVideoElement>();

  constructor(props: VideoElementProps) {
    super(props);
    this.state = {};
  }

  shouldComponentUpdate() {
    // do not re-render via diff:
    return false;
  }

  /*
  componentWillReceiveProps(nextProps) {
  }*/

  componentDidMount() {
    // now mounted, can freely modify the DOM:
  }

  componentWillUnmount() {
    // component is about to be removed from the DOM, perform any cleanup.
  }

  render() {
    return <video controls ref={this.videoElt} />;
  }
}
