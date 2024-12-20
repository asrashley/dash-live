import { Stream } from "./Stream";
import { StreamTrack } from "./StreamTrack";


export interface DecoratedStream extends Stream {
    tracks: StreamTrack[];
}
