import { createContext } from "preact";
import { useCallback, useContext, useEffect } from "preact/hooks";
import { useSignal, useSignalEffect, useComputed } from "@preact/signals";

import { AppStateContext, appendMessage } from "../appState.js";
import { EndpointContext } from "../endpoints.js";

export const MultiPeriodModelContext = createContext();

export function validatePeriod(period) {
  const errors = {};

  if (period.pid === "") {
    errors.pid = "Period ID is mandatory";
  }
  if (period.duration === "" || period.duration === "PT0S") {
    errors.duration = "Duration must be greater than zero";
  }
  if (Object.keys(period.tracks).length === 0) {
    errors.tracks = "At least one track is requred";
  }
  return errors;
}

export function validateModel({ model }) {
  const { value } = model;
  const errors = {};
  if (value === undefined) {
    return errors;
  }
  if (value.name === "") {
    errors.name = "Name is required";
  }
  if (value.title === "") {
    errors.title = "Title is required";
  }
  if (value.periods.length === 0) {
    errors.periods = { 0: "At least one Period is required" };
  }
  //TODO: add check for duplicate period IDs
  value.periods.forEach((prd) => {
    const err = validatePeriod(prd);
    if (Object.keys(err).length > 0) {
      const { periods = {} } = errors;
      errors.periods = {
        ...periods,
        [prd.pk]: err,
      };
    }
  });
  return errors;
}

function modifyPeriod({ model, periodPk, track, period }) {
  let { modified, lastModified = 0 } = model.value;
  const periods = model.value.periods.map((prd) => {
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
    modified = true;
    return {
      ...prd,
      ...period,
      tracks,
    };
  });
  model.value = {
    ...model.value,
    periods,
    modified,
    lastModified: modified ? Date.now() : lastModified,
  };
}

function setOrdering({ model, periodPks }) {
  if (!model.value) {
    return;
  }
  const periods = model.value.periods.map((p) => {
    return {
      ...p,
      ordering: periodPks.indexOf(p.pk) + 1,
    };
  });
  periods.sort((a, b) => a.ordering - b.ordering);
  model.value = {
    ...model,
    periods,
    modified: true,
  };
}

function addPeriodToModel({ model }) {
  const { periods } = model.value;
  let index = periods.length + 1;
  let newPid = `p${index}`;

  while (periods.some((p) => p.pid === newPid)) {
    index += 1;
    newPid = `p${index}`;
  }

  const ordering = 1 + periods.reduce((a, c) => Math.max(a, c.ordering), 0);

  const newPeriod = {
    pid: newPid,
    pk: newPid,
    new: true,
    ordering,
    stream: "",
    start: "",
    duration: "",
    tracks: {},
  };

  model.value = {
    ...model.value,
    periods: [...periods, newPeriod],
    lastModified: Date.now(),
    modified: true,
  };
}

function createDataFromModel(model) {
  const periods = model.value.periods.map((prd) => {
    const period = {
      ...prd,
      pk: typeof prd.pk === "number" ? prd.pk : null,
    };
    return period;
  });
  return {
    ...model.value,
    periods,
  };
}

async function saveChangesToModel({ apiRequests, messages, model, signal }) {
  if (!model.value || signal.aborted) {
    return false;
  }
  const data = createDataFromModel(model);
  try {
    const result =
      data.pk === null
        ? await apiRequests.addMultiPeriodStream(data, { signal })
        : await apiRequests.modifyMultiPeriodStream(name, data, { signal });
    if (signal.aborted) {
      return false;
    }
    result.errors?.forEach((err) => appendMessage(messages, err, "warning"));
    if (result?.success === true) {
      if (data.pk === null) {
        appendMessage(messages, `Added new stream ${name}`, "success");
      } else {
        appendMessage(messages, `Saved changes to ${name}`, "success");
      }
      model.value = {
        ...result.model,
        modified: false,
        lastModified: Date.now(),
      };
      return true;
    }
  } catch (err) {
    appendMessage(messages, `${err}`, "warning");
  }
}

async function deleteMpsStream({ apiRequests, messages, name, signal }) {
  try {
    const result = await apiRequests.deleteMultiPeriodStream(name, {
      signal,
    });
    if (result.ok) {
      appendMessage(messages, `Deleted stream ${name}`, "success");
      return true;
    }
    appendMessage(
      messages,
      `Failed to delete {name}: {result.status} {result.statusText}`,
      "warning"
    );
  } catch (err) {
    appendMessage(messages, `${err}`, "warning");
  }
  return false;
}

export function useMultiPeriodModel({ model, name }) {
  const apiRequests = useContext(EndpointContext);
  const { messages } = useContext(AppStateContext);
  const modified = useComputed(() => model.value?.modified ?? false);
  const lastModified = useComputed(() => model.value?.lastModified ?? 0);
  const localErrors = useComputed(() => validateModel({ model }));
  const serverErrors = useSignal({ errors: {}, lastChecked: Date.now() });
  const errors = useComputed(() => ({
    ...localErrors.value,
    ...serverErrors.value.errors,
  }));
  const isValid = useComputed(
    () =>
      Object.keys(localErrors.value).length === 0 &&
      Object.keys(serverErrors.value).length === 0
  );

  const addPeriod = useCallback(() => addPeriodToModel({ model }), [model]);

  const removePeriod = useCallback(
    (pk) => {
      model.value = {
        ...model.value,
        periods: model.value.periods.filter((prd) => prd.pk !== pk),
        modified: true,
        lastModified: Date.now(),
      };
    },
    [model]
  );

  const setPeriodOrdering = useCallback(
    (periodPks) => setOrdering({ model, periodPks }),
    [model]
  );

  const modify = useCallback(
    ({ periodPk, track, period = {} }) =>
      modifyPeriod({ model, periodPk, track, period }),
    [model]
  );

  const setFields = useCallback(
    (props) => {
      model.value = {
        ...model.value,
        ...props,
        modified: true,
        lastModified: Date.now(),
      };
    },
    [model]
  );

  const saveChanges = useCallback(
    ({ signal }) =>
      saveChangesToModel({ apiRequests, messages, model, modified, signal }),
    [apiRequests, messages, model, modified]
  );

  const deleteStream = useCallback(
    ({ signal }) => deleteMpsStream({ apiRequests, messages, name, signal }),
    [apiRequests, messages, name]
  );

  useSignalEffect(() => {
    if (
      !modified.value ||
      serverErrors.value.lastChecked >= lastModified.value ||
      Object.keys(localErrors.value).length > 0
    ) {
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    const timeout = window.setTimeout(async () => {
      if (signal.aborted) {
        return;
      }
      const data = createDataFromModel(model);
      try {
        const errs = await apiRequests.validateMultiPeriodStream(data, {
          signal,
        });
        if (signal.aborted) {
          return;
        }
        serverErrors.value = {
          errors: errs?.errors ?? {},
          lastChecked: Date.now(),
        };
      } catch (err) {
        if (!signal.aborted) {
          console.error(err);
        }
      }
    }, 250);
    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  });

  return {
    setFields,
    addPeriod,
    setPeriodOrdering,
    removePeriod,
    modifyPeriod: modify,
    saveChanges,
    deleteStream,
    modified,
    errors,
    isValid,
  };
}

const blankModel = {
  pk: null,
  name: "",
  title: "",
  periods: [],
  modified: false,
};

async function fetchStreamIfRequired({
  apiRequests,
  name,
  newStream,
  model,
  loaded,
  signal,
}) {
  if (newStream && model.value === undefined) {
    loaded.value = name;
    model.value = JSON.parse(JSON.stringify(blankModel));
    return;
  }
  if (loaded.value !== name || model.value === undefined) {
    const data = await apiRequests.getMultiPeriodStream(name, { signal });
    if (!signal.aborted) {
      loaded.value = name;
      model.value = {
        ...data.model,
        lastModified: 0,
        modified: false,
      };
    }
  }
}

export function useMultiPeriodStream({ name, newStream }) {
  const apiRequests = useContext(EndpointContext);
  const loaded = useSignal();
  const model = useSignal();
  const modifiers = useMultiPeriodModel({ model, name });

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    fetchStreamIfRequired({
      apiRequests,
      name,
      newStream,
      model,
      loaded,
      signal,
    });

    return () => {
      controller.abort();
    };
  }, [apiRequests, loaded, name, newStream, model]);

  return {
    model,
    loaded,
    ...modifiers,
  };
}
