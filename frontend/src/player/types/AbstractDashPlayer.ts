import type { OptionMapWithChildren } from "@dashlive/options";
import { KeyParameters } from "./KeyParameters";

export interface DashPlayerProps {
    version?: string;
    autoplay?: boolean;
    videoElement: HTMLVideoElement;
    subtitlesElement?: HTMLDivElement;
    logEvent(eventName: string, text: string): void;
}
export abstract class AbstractDashPlayer {

    // eslint-disable-next-line no-useless-constructor
    constructor(protected props: DashPlayerProps) {
        /* no op */
    }

    abstract initialize(mpd: string, options: OptionMapWithChildren, keys: Map<string, KeyParameters>): Promise<void>;

    abstract destroy(): void;

    protected onCanPlayEvent = async () => {
        const { videoElement } = this.props;
        try {
            await videoElement.play();
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        } catch(err) {
            videoElement.muted = true;
            videoElement.play();
        }
        videoElement.removeEventListener('canplay', this.onCanPlayEvent);
    };

}