import { createContext } from 'preact';
import { signal, computed } from "@preact/signals";

export const PageStateContext = createContext();

export function createPageState() {
  const allStreams = signal(undefined);
  const model = signal(undefined);
  const modified = signal(false);

  const streamsMap = computed(() => {
    const rv = new Map();
    if (allStreams.value) {
      for (const stream of allStreams.value) {
        rv.set(stream.pk, stream);
      }
    }
    return rv;
  });

  return { allStreams, model, modified, streamsMap };
}

export function modifyModel({model, periodPk, track, period = {}}) {
  const periods = model.periods.map(prd => {
    if (prd.pk !== periodPk) {
      return prd;
    }
    const tracks = {
      ...prd.tracks,
    };
    if (track) {
      if (track.enabled) {
        tracks[track.track_id] = track.role;
      } else {
        delete tracks[track.track_id];
      }
    }
    return {
      ...prd,
      ...period,
      tracks,
    };
  });
  return {
    ...model,
    periods,
  };
}

export function setOrdering(model, periodPks) {
  const periods = model.periods.map(p => {
    return {
      ...p,
      ordering: periodPks.indexOf(p.pk) + 1,
    };
  });
  periods.sort((a, b) => a.ordering - b.ordering);
  return {
    ...model,
    periods,
  };
}

export function addPeriod(model) {
    let index = model.periods.length + 1;
    let newPid = `p${index}`;

    while(model.periods.some(p => p.pid === newPid)) {
      index += 1;
      newPid = `p${index}`;
    }

    const ordering = 1 + model.periods.reduce(
      (a, c) => Math.max(a, c.ordering), 0);

    const newPeriod = {
      pid: newPid,
      pk: newPid,
      new: true,
      ordering,
      stream: '',
      start: '',
      duration: '',
      tracks: {},
    };

    return {
      ...model,
      periods: [
        ...model.periods,
        newPeriod,
      ],
    };
}

export function removePeriod(model, pk) {
  return {
    ...model,
    periods: model.periods.filter(prd => prd.pk !== pk),
  };
}

export function validatePeriod(period) {
  const errors = {};

  if (period.pid === '') {
    errors.pid = 'Period ID is mandatory';
  }
  if (period.duration === '' || period.duration === 'PT0S') {
    errors.duration = 'Duration must be greater than zero';
  }
  if (Object.keys(period.tracks).length === 0) {
    errors.tracks = 'At least one track is requred';
  }
  return errors;
}

export function validateModel(model) {
  const errors = {};
  if (model.name === '') {
    errors.name = 'Name is required';
  }
  if (model.title === '') {
    errors.title = 'Title is required';
  }
  if (model.periods.length === 0) {
    errors.periods = 'At least one Period is required';
  }
  //TODO: add check for duplicate period IDs
  model.periods.forEach(prd => {
    const err = validatePeriod(prd);
    if (Object.keys(err).length > 0) {
      errors[`periods__${prd.pk}`] = err;
    }
  });
  return errors;
}

