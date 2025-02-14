import { createContext } from "preact";
import { useCallback, useContext } from "preact/hooks";
import { useComputed, type ReadonlySignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { Stream } from "../types/Stream";
import { StreamTrack } from "../types/StreamTrack";
import { DecoratedStream } from "../types/DecoratedStream";
import { useJsonRequest } from "./useJsonRequest";

function findStreamTracks(stream: Stream): StreamTrack[] {
  const tracks = new Map<number, StreamTrack>();
  for (const mf of stream.media_files) {
    const { track_id, content_type, codec_fourcc } = mf;
    let track: StreamTrack = tracks.get(track_id);
    if (track === undefined) {
      track = {
        clearBitrates: 0,
        encryptedBitrates: 0,
        track_id,
        content_type,
        codec_fourcc,
      };
      tracks.set(track_id, track);
    }
    if (mf.encrypted) {
      track.encryptedBitrates += 1;
    } else {
      track.clearBitrates += 1;
    }
  }
  const ids = [...tracks.keys()];
  ids.sort();
  return ids.map((tid) => tracks.get(tid));
}

export function decorateAllStreams(streams: Stream[]): DecoratedStream[] {
  return streams.map((stream) => {
    const decoratedStream: DecoratedStream = {
      ...stream,
      tracks: findStreamTracks(stream),
    };
    return decoratedStream;
  });
}

export interface UseAllStreamsHook {
  allStreams: ReadonlySignal<DecoratedStream[]>,
  loaded: ReadonlySignal<boolean>,
  streamsMap: ReadonlySignal<Map<string, DecoratedStream>>,
  error: ReadonlySignal<string | null>;
}

export const AllStreamsContext = createContext<UseAllStreamsHook>(null);

export function useAllStreams(): UseAllStreamsHook {
  const apiRequests = useContext(EndpointContext);
  const request = useCallback(async (signal: AbortSignal) => {
    const { streams } = await apiRequests.getAllStreams({
      signal,
      withDetails: true,
    });
    return decorateAllStreams(streams);
  }, [apiRequests]);
  const { data: allStreams, loaded, error } = useJsonRequest<DecoratedStream[]>({
    request,
    initialData: [],
    name: 'streams',
  });
  const streamsMap = useComputed<Map<string, DecoratedStream>>(() => {
    const rv = new Map();
    if (allStreams.value) {
      for (const stream of allStreams.value) {
        rv.set(`${stream.pk}`, stream);
      }
    }
    return rv;
  });

  return { allStreams, loaded, streamsMap, error };
}
