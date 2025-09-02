import type { ReadonlySignal } from "@preact/signals";
import { MediaTrack } from "./MediaTrack";

export interface PlayerControls {
    isPaused: ReadonlySignal<boolean>;
    hasDashPlayer: ReadonlySignal<boolean>;
    pause(): void;
    play(): Promise<void>;
    skip(seconds: number): void;
    stop(): void;
    setSubtitlesElement(subtitlesElement: HTMLDivElement | null): void;
    setTextTrack(track: MediaTrack | null): void;
}