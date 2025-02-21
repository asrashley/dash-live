export interface PlayerControls {
    pause(): void;
    play(): void;
    skip(seconds: number): void;
    stop(): void;
}