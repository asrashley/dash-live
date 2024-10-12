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

export function AddOrEditStreamPage({name, newStream=false }) {
  const apiRequests = useContext(EndpointContext);
  const [loaded, setLoaded] = useState(null);
  const state = useMemo(createPageState, []);
  const { allStreams, model } = state;

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchAllStreamsIfRequired = async () => {
      if (!allStreams.value) {
        const data = await apiRequests.getAllStreams({signal, withDetails: true});
        if (!signal.aborted) {
          allStreams.value = decorateAllStreams(data.streams);
        }
      }
    };

    fetchAllStreamsIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, allStreams]);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchStreamIfRequired = async () => {
      if (!allStreams.value) {
        return;
      }
      if (loaded === name && model.value !== undefined) {
        return;
      }
      if (newStream && model.value === undefined) {
        setLoaded(name);
        model.value = JSON.parse(JSON.stringify(blankModel));
        return;
      }
      if (name == '.add') {
        return;
      }
      const data = await apiRequests.getMultiPeriodStream(name, {signal});
      if (!signal.aborted) {
        setLoaded(name);
        model.value = data.model;
      }
    };

    fetchStreamIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, loaded, name, newStream, allStreams, model]);

  return html`
<${PageStateContext.Provider} value=${state}>
  <${EditStreamCard} name=${name} newStream=${newStream} />
  <${TrackSelectionDialog} />
</${PageStateContext.Provider}>`;
}
