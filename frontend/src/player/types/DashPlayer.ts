export abstract class DashPlayer {
    // eslint-disable-next-line no-useless-constructor
    constructor(protected version?: number) {
        /* no op */
    }

    abstract initialize(videoElement: HTMLVideoElement, mpd: string): Promise<boolean>;
}