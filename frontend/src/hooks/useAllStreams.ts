import { createContext } from "preact";
import { useContext, useEffect } from "preact/hooks";
import { useSignal, useComputed, type Signal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { Stream } from "../types/Stream";
import { StreamTrack } from "../types/StreamTrack";
import { DecoratedStream } from "../types/DecoratedStream";

function findStreamTracks(stream: Stream): StreamTrack[] {
  const tracks = new Map();
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
  allStreams: Signal<DecoratedStream[]>,
  loaded: Signal<boolean>,
  streamsMap: Signal<Map<string, DecoratedStream>>,
  error: Signal<string | null>;
}

export const AllStreamsContext = createContext<UseAllStreamsHook>(null);

export function useAllStreams(): UseAllStreamsHook {
  const apiRequests = useContext(EndpointContext);
  const streams = useSignal<DecoratedStream[] | undefined>();
  const loaded = useSignal<boolean>(false);
  const error = useSignal<string | null>(null);
  const allStreams = useComputed<DecoratedStream[]>(() => streams.value ?? []);
  const streamsMap = useComputed<Map<string, DecoratedStream>>(() => {
    const rv = new Map();
    if (allStreams.value) {
      for (const stream of allStreams.value) {
        rv.set(stream.pk, stream);
      }
    }
    return rv;
  });

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchAllStreamsIfRequired = async () => {
      if (!streams.value) {
        try {
          const data = await apiRequests.getAllStreams({
            signal,
            withDetails: true,
          });
          if (!signal.aborted) {
            streams.value = decorateAllStreams(data.streams);
            error.value = null;
            loaded.value = true;
          }
        } catch (err) {
          if (!signal.aborted) {
            console.error(err);
            error.value = `${err}`;
          }
        }
      }
    };

    fetchAllStreamsIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, error, loaded, streams]);

  return { allStreams, loaded, streamsMap, error };
}
