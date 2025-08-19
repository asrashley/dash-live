import { Component, createRef } from "preact";
import type { ReadonlySignal, Signal } from "@preact/signals";

import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { AbstractDashPlayer, DashPlayerProps } from "../types/AbstractDashPlayer";
import { playerFactory } from "../players/playerFactory";
import { PlayerControls } from "../types/PlayerControls";
import { StatusEvent } from "../types/StatusEvent";
import { DashParameters } from "../types/DashParameters";
import { KeyParameters } from "../types/KeyParameters";
import { PlaybackIconType } from "../types/PlaybackIconType";

export const STATUS_EVENTS = [
  'stalled','loadedmetadata', 'error', 'canplay', 'canplaythrough',
  'playing', 'ended', 'pause', 'resize', 'loadstart', 'seeking', 'seeked',
];


export interface VideoElementProps {
  mpd: string;
  playerName: DashPlayerTypes;
  playerVersion?: string;
  dashParams: ReadonlySignal<DashParameters>;
  keys: ReadonlySignal<Map<string, KeyParameters>>;
  currentTime: Signal<number>;
  controls: Signal<PlayerControls | undefined>;
  activeIcon: Signal<PlaybackIconType | null>;
  events: Signal<StatusEvent[]>;
  maxEvents?: number;
}

export class VideoElement extends Component<VideoElementProps, undefined> implements PlayerControls {
  static DEFAULT_MAX_EVENTS = 10;
  private videoElt = createRef<HTMLVideoElement>();
  private player?: AbstractDashPlayer;
  private nextId = 1;
  private subtitlesElement: HTMLDivElement | null = null;

  shouldComponentUpdate() {
    // do not re-render via diff:
    return false;
  }

  componentWillReceiveProps(nextProps: VideoElementProps) {
    if (!this.player && nextProps.dashParams.value) {
      this.tryInitializePlayer(nextProps);
    }
  }

  componentDidMount() {
    this.tryInitializePlayer(this.props);
  }

  componentWillUnmount() {
    for (const name of STATUS_EVENTS) {
      this.videoElt.current.removeEventListener(name, this.logDomEvent);
    }
    this.props.controls.value = undefined;
    this.videoElt.current.removeEventListener("timeupdate", this.onTimeUpdate);
    this.player?.destroy();
    this.player = undefined;
    this.subtitlesElement = null;
  }

  render() {
    return <video ref={this.videoElt} />;
  }

  pause() {
    this.videoElt.current.pause();
  }

  isPaused() {
    return this.videoElt.current.paused;
  }

  play() {
    this.videoElt.current.play();
  }

  skip(seconds: number) {
    const video = this.videoElt.current;
    const newTime = Math.min(
      Math.max(0, video.currentTime + seconds),
      video.duration
    );
    this.videoElt.current.currentTime = newTime;
  }

  stop() {
    this.videoElt.current.pause();
  }

  setSubtitlesElement = (subtitlesElement: HTMLDivElement | null) => {
    this.subtitlesElement = subtitlesElement;
    this.player?.setSubtitlesElement(subtitlesElement);
  }

  private tryInitializePlayer(props: VideoElementProps) {
    const { dashParams, keys, mpd, playerName, playerVersion: version } = props;
    if (!this.videoElt.current || !dashParams.value) {
      return;
    }
    this.videoElt.current.addEventListener("timeupdate", this.onTimeUpdate);
    const playerProps: DashPlayerProps = {
      version,
      logEvent: this.logEvent,
      autoplay: true,
      videoElement: this.videoElt.current,
    };
    this.player = playerFactory(playerName, playerProps);
    this.player.initialize(mpd, dashParams.value.options, keys.value);
    this.props.controls.value = this;
    for (const name of STATUS_EVENTS) {
      this.videoElt.current.addEventListener(name, this.logDomEvent);
    }
    if (this.subtitlesElement) {
      this.player.setSubtitlesElement(this.subtitlesElement);
    }
  }

  private onTimeUpdate = (ev: Event) => {
    const video = ev.target as HTMLVideoElement;
    this.props.currentTime.value = video.currentTime;
  };

  private logEvent = (event: string, text: string) => {
    const status: StatusEvent = {
      id: this.nextId++,
      timecode: new Date().toISOString(),
      position: this.videoElt.current?.currentTime,
      event,
      text,
    };
    this.appendStatusEvent(status);
  };

  private logDomEvent = (ev: Event) => {
    const video = ev.target as HTMLVideoElement;
    const status: StatusEvent = {
      id: this.nextId++,
      timecode: new Date().toISOString(),
      position: video.currentTime,
      event: ev.type,
      text: '',
    };
    if (ev.type === "error"){
        const { error } = video;
        if (error) {
          status.text = `${error.code}: ${error.message}`;

        }
    }
    this.appendStatusEvent(status);
  };

  private appendStatusEvent(status: StatusEvent) {
    const evList = [status, ...this.props.events.value];
    const { maxEvents = VideoElement.DEFAULT_MAX_EVENTS } = this.props;
    while(evList.length > maxEvents) {
      evList.pop();
    }
    this.props.events.value = evList;
  }
}
