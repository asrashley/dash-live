export interface PlayerControls {
    isPaused(): boolean;
    pause(): void;
    play(): void;
    skip(seconds: number): void;
    stop(): void;
    setSubtitlesElement(subtitlesElement: HTMLDivElement | null): void;
}