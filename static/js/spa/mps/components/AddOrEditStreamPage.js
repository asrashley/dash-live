import { html } from 'htm/preact';
import { useContext, useEffect, useMemo, useState } from 'preact/hooks';

import { createPageState, PageStateContext } from '../state.js';
import { EndpointContext } from '../../endpoints.js';
import { EditStreamCard } from './EditStreamCard.js';
import { TrackSelectionDialog } from './TrackSelectionDialog.js';

const blankModel = {
  pk: null,
  name: '',
  title: '',
  periods: [],
};

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
  return ids.map(tid => tracks.get(tid));
}

function decorateAllStreams(streams) {
  return streams.map(stream => {
    const decoratedStream = {
      ...stream,
      tracks: findStreamTracks(stream),
    };
    return decoratedStream;
  });
}

export function AddOrEditStreamPage({name, newStream}) {
  const apiRequests = useContext(EndpointContext);
  const [loaded, setLoaded] = useState(null);
  const state = useMemo(createPageState, []);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchAllStreamsIfRequired = async () => {
      if (!state.allStreams.value) {
        const data = await apiRequests.getAllStreams({signal, withDetails: true});
        if (!signal.aborted) {
          state.allStreams.value = decorateAllStreams(data.streams);
        }
      }
    };

    fetchAllStreamsIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, state.allStreams]);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchStreamIfRequired = async () => {
      if (!state.allStreams.value) {
        return;
      }
      if (newStream && state.model.value === undefined) {
        setLoaded(name);
        state.model.value = JSON.parse(JSON.stringify(blankModel));
        return;
      }
      if (loaded !== name || state.model.value === undefined) {
        const data = await apiRequests.getMultiPeriodStream(name, {signal});
        if (!signal.aborted) {
          setLoaded(name);
          state.model.value = data.model;
        }
      }
    };

    fetchStreamIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, name, state.allStreams.value, state.streamsMap.value]);

  return html`
<${PageStateContext.Provider} value=${state}>
  <${EditStreamCard} name=${name} newStream=${newStream} />
  <${TrackSelectionDialog} />
</${PageStateContext.Provider}>`;
}
