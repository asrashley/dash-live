import { createContext } from "preact";
import { useContext, useEffect } from "preact/hooks";
import { useSignal, useComputed } from "@preact/signals";

import { EndpointContext } from "../endpoints.js";

export const AllStreamsContext = createContext();

function findStreamTracks(stream) {
  const tracks = new Map();
  for (const mf of stream.media_files) {
    const { track_id, content_type, codec_fourcc } = mf;
    let track = tracks.get(track_id);
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

export function decorateAllStreams(streams) {
  return streams.map((stream) => {
    const decoratedStream = {
      ...stream,
      tracks: findStreamTracks(stream),
    };
    return decoratedStream;
  });
}

export function useAllStreams() {
  const apiRequests = useContext(EndpointContext);
  const streams = useSignal();
  const loaded = useSignal(false);
  const error = useSignal(null);
  const allStreams = useComputed(() => streams.value ?? []);
  const streamsMap = useComputed(() => {
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

    fetchAllStreamsIfRequired({ streams, apiRequests, signal });

    return () => {
      controller.abort();
    };
  }, [apiRequests, error, loaded, streams]);

  return { allStreams, loaded, streamsMap, error };
}
