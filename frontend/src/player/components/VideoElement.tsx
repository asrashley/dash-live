import { Component } from "preact";
import { effect, signal, type ReadonlySignal, type Signal } from "@preact/signals";

import { DashPlayerTypes } from "../types/DashPlayerTypes";
import {
  AbstractDashPlayer,
  DashPlayerProps,
} from "../players/AbstractDashPlayer";
import { playerFactory } from "../players/playerFactory";
import { PlayerControls } from "../types/PlayerControls";
import { StatusEvent } from "../types/StatusEvent";
import { DashParameters } from "../types/DashParameters";
import { KeyParameters } from "../types/KeyParameters";
import { MediaTrack } from "../types/MediaTrack";

export const STATUS_EVENTS = [
  "stalled",
  "loadedmetadata",
  "error",
  "canplay",
  "canplaythrough",
  "playing",
  "ended",
  "pause",
  "resize",
  "loadstart",
  "seeking",
  "seeked",
];

export interface VideoElementProps {
  mpd: string;
  playerName: DashPlayerTypes;
  playerVersion?: string;
  dashParams: ReadonlySignal<DashParameters>;
  keys: ReadonlySignal<Map<string, KeyParameters>>;
  textEnabled: ReadonlySignal<boolean>;
  textLanguage: ReadonlySignal<string>;
  currentTime: Signal<number>;
  events: Signal<StatusEvent[]>;
  maxEvents?: number;
  setPlayer(controls: PlayerControls | null): void;
  tracksChanged(tracks: MediaTrack[]): void;
}

export class VideoElement
  extends Component<VideoElementProps, undefined>
  implements PlayerControls
{
  static DEFAULT_MAX_EVENTS = 25;
  private videoElt: HTMLVideoElement | null = null;
  private player?: AbstractDashPlayer;
  private nextId = 1;
  private subtitlesElement: HTMLDivElement | null = null;
  private signalCleanup: () => void | undefined;
  private unmountController: AbortController = new AbortController();
  public isPaused = signal<boolean>(false);
  public hasPlayer = signal<boolean>(false);

  shouldComponentUpdate() {
    // do not re-render via diff:
    return false;
  }

  componentWillReceiveProps(nextProps: VideoElementProps) {
    if (nextProps.dashParams !== this.props.dashParams) {
      this.signalCleanup?.();
      this.signalCleanup = effect(() => {
        this.tryInitializePlayer();
      });
    }
    //this.tryInitializePlayer(nextProps);
  }

  componentDidMount() {
    this.isPaused.value = this.videoElt?.paused ?? false;
    this.signalCleanup = effect(() => {
      this.tryInitializePlayer();
    });
    //this.tryInitializePlayer(this.props);
  }

  componentWillUnmount() {
    this.signalCleanup?.();
    this.signalCleanup = undefined;
    this.unmountController.abort();
    this.props.setPlayer(null);
    this.player?.destroy();
    this.player = undefined;
    this.subtitlesElement = null;
    this.hasPlayer.value = false;
    this.isPaused.value = true;
  }

  render() {
    return <video ref={this.setVideoElt} />;
  }

  pause() {
    this.videoElt?.pause();
  }

  play() {
    this.tryInitializePlayer();
    this.videoElt?.play();
  }

  skip(seconds: number) {
    if (this.videoElt === undefined) {
      throw new Error('video element not mounted');
    }
    const video = this.videoElt;
    const newTime = Math.min(
      Math.max(0, video.currentTime + seconds),
      video.duration
    );
    video.currentTime = newTime;
  }

  stop() {
    this.videoElt?.pause();
    this.player?.destroy();
    this.player = undefined;
    this.hasPlayer.value = false;
  }

  setSubtitlesElement = (subtitlesElement: HTMLDivElement | null) => {
    this.subtitlesElement = subtitlesElement;
    this.player?.setSubtitlesElement(subtitlesElement);
  };

  setTextTrack = (track: MediaTrack | null) => {
    this.player?.setTextTrack(track);
  };

  private setVideoElt = (elt: HTMLVideoElement | null) => {
    this.videoElt = elt;
    if (!elt) {
      return;
    }
    if (this.unmountController === undefined) {
      throw new Error('unmountController should have been created in constructor');
    }
    const { signal } = this.unmountController;
    elt.addEventListener('pause', () => this.isPaused.value = true, { signal });
    elt.addEventListener('play', () => this.isPaused.value = false, { signal });
  }

  private tryInitializePlayer() {
    const { dashParams, keys, mpd, playerName, textLanguage, textEnabled, playerVersion: version } = this.props;
    if (this.player || !this.videoElt || !dashParams.value) {
      return;
    }
    const { signal } = this.unmountController;
    this.videoElt.addEventListener("timeupdate", this.onTimeUpdate, { signal });
    const playerProps: DashPlayerProps = {
      version,
      logEvent: this.logEvent,
      tracksChanged: this.tracksChanged,
      autoplay: true,
      videoElement: this.videoElt,
      textLanguage: textLanguage.value,
      textEnabled: textEnabled.value,
    };
    this.player = playerFactory(playerName, playerProps);
    this.player.initialize(mpd, dashParams.value.options, keys.value);
    this.props.setPlayer(this);
    for (const name of STATUS_EVENTS) {
      this.videoElt.addEventListener(name, this.logDomEvent, { signal });
    }
    if (this.subtitlesElement) {
      this.player.setSubtitlesElement(this.subtitlesElement);
    }
    this.hasPlayer.value = true;
  }

  private onTimeUpdate = (ev: Event) => {
    const video = ev.target as HTMLVideoElement;
    this.props.currentTime.value = video.currentTime;
  };

  private logEvent = (event: string, text: string) => {
    const status: StatusEvent = {
      id: this.nextId++,
      timecode: new Date().toISOString(),
      position: this.videoElt?.currentTime,
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
      text: "",
    };
    if (ev.type === "error") {
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
    while (evList.length > maxEvents) {
      evList.pop();
    }
    this.props.events.value = evList;
  }

  private tracksChanged = (tracks: MediaTrack[]) => {
    const status: StatusEvent = {
      id: 0,
      timecode: new Date().toISOString(),
      position: this.videoElt.currentTime,
      event: 'TracksChanged',
      text: "",
    };

    tracks.forEach(({active, id, trackType, language}) => {
      this.appendStatusEvent({
        ...status,
        id: this.nextId++,
        text: `${trackType}[${id}] lang="${language}" active=${active}`,
      });
    });
    this.props.tracksChanged(tracks);
  };
}
