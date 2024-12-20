import { MediaFile } from "./MediaFile";
import { TimingReference } from "./TimingReference";

export interface Stream {
    defaults: object | null;
    directory: string;
    duration: string;
    marlin_la_url: string | null;
    media_files: MediaFile[];
    pk: number;
    playready_la_url: string | null;
    timing_ref: TimingReference | null;
    title: string;
}
