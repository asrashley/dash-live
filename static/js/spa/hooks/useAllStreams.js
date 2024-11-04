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
        bitrates: 1,
        track_id,
        content_type,
        codec_fourcc,
      };
      tracks.set(track_id, track);
    } else {
      track.bitrates += 1;
    }
  }
  const ids = [...tracks.keys()];
  ids.sort();
  return ids.map((tid) => tracks.get(tid));
}

function decorateAllStreams(streams) {
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
  }, [apiRequests, error, streams]);

  return { allStreams, streamsMap, error };
}
