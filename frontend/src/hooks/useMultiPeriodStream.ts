import { createContext } from "preact";
import { useCallback, useContext, useEffect, useRef } from "preact/hooks";
import { useSignal, useSignalEffect, useComputed, type Signal, type ReadonlySignal, batch } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { useMessages } from "./useMessages";
import { MultiPeriodStream } from "../types/MultiPeriodStream";
import { DecoratedMultiPeriodStream } from "../types/DecoratedMultiPeriodStream";
import { MpsPeriod } from "../types/MpsPeriod";
import { MpsTrack } from "../types/MpsTrack";

export type MpsPeriodValidationErrors = {
  pid?: string;
  duration?: string;
  start?: string;
  stream?: string;
  tracks?: string;
};

export type MpsPeriodValidationErrorsMap = {
  [pid: string]:  MpsPeriodValidationErrors;
};

export type MpsModelValidationErrors = {
  fetch?: string;
  name?: string;
  title?: string;
  allPeriods?: string;
  periods?: MpsPeriodValidationErrorsMap;
};

export interface ServerMpsModelValidationErrors {
  errors: MpsModelValidationErrors;
  lastChecked: number;
}


export function validatePeriod(period: MpsPeriod): MpsPeriodValidationErrors {
  const errors: MpsPeriodValidationErrors = {};

  if (period.pid === "") {
    errors.pid = "Period ID is mandatory";
  }
  if (period.duration === "" || period.duration === "PT0S") {
    errors.duration = "Duration must be greater than zero";
  }
  if (Object.keys(period.tracks).length === 0) {
    errors.tracks = "At least one track is required";
  }
  return errors;
}

export function validateModel({ model }: {model: Signal<DecoratedMultiPeriodStream>}): MpsModelValidationErrors {
  const { value } = model;
  const errors: MpsModelValidationErrors = {};
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
    errors.allPeriods = "At least one Period is required";
  }
  //TODO: add check for duplicate period IDs
  value.periods.forEach((prd) => {
    const err = validatePeriod(prd);
    if (Object.keys(err).length > 0) {
      const periods: MpsPeriodValidationErrorsMap = errors.periods ?? {};
      errors.periods = {
        ...periods,
        [prd.pk]: err,
      };
    }
  });
  return errors;
}

interface ModifyPeriodProps {
  model: Signal<DecoratedMultiPeriodStream>;
  periodPk: number | string;
  track?: Partial<MpsTrack>;
  tracks?: MpsTrack[];
  period?: Partial<MpsPeriod>;
}

function modifyPeriod({ model, periodPk, track, tracks: newTracks, period }: ModifyPeriodProps) {
  // eslint-disable-next-line prefer-const
  let { modified, lastModified = 0 } = model.value;
  const periods = model.value.periods.map((prd) => {
    if (prd.pk !== periodPk) {
      return prd;
    }
    let tracks = newTracks ? newTracks : prd.tracks;
    if (track) {
      const { track_id } = track;
      tracks = tracks.map((tk) => {
        if (tk.track_id === track_id) {
          return {
            ...tk,
            ...track,
          };
        }
        return tk;
      });
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

interface SetOrderingProps {
  model: Signal<DecoratedMultiPeriodStream>;
  periodPks: (number|string)[];
}

function setOrdering({ model, periodPks }: SetOrderingProps) {
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
    ...model.value,
    periods,
    modified: true,
  };
}

function addPeriodToModel({ model }: {model: Signal<DecoratedMultiPeriodStream>}) {
  const { periods } = model.value;
  let index = periods.length + 1;
  let newPid = `p${index}`;

  while (periods.some((p) => p.pid === newPid)) {
    index += 1;
    newPid = `p${index}`;
  }

  const ordering = 1 + periods.reduce((a, c) => Math.max(a, c.ordering), 0);

  const newPeriod: MpsPeriod = {
    parent: model.value.pk,
    pid: newPid,
    pk: newPid,
    new: true,
    ordering,
    stream: 0,
    start: "",
    duration: "",
    tracks: [],
  };

  model.value = {
    ...model.value,
    periods: [...periods, newPeriod],
    lastModified: Date.now(),
    modified: true,
  };
}

export function decorateMultiPeriodStream(model: MultiPeriodStream): DecoratedMultiPeriodStream {
  const periods: MpsPeriod[] = model.periods.map((prd: MpsPeriod) => {
    const tracks: MpsTrack[] = prd.tracks.map((tk) => ({ ...tk, enabled: true }));
    const dmp: MpsPeriod = {
      ...prd,
      tracks,
    };
    return dmp;
  });
  const dps: DecoratedMultiPeriodStream = {
    ...model,
    periods,
    options: model.options ?? {},
    lastModified: 0,
    modified: false,
  };
  return dps;
}

function createDataFromModel(model: Signal<DecoratedMultiPeriodStream>): DecoratedMultiPeriodStream {
  const periods = model.value.periods.map((prd) => {
    const period = {
      ...prd,
      pk: typeof prd.pk === "number" ? prd.pk : null,
      tracks: prd.tracks.filter((tk) => tk.enabled),
    };
    return period;
  });
  return {
    ...model.value,
    periods,
  };
}

async function deleteMpsStream({ apiRequests, name, signal, appendMessage }): Promise<boolean> {
  try {
    const result = await apiRequests.deleteMultiPeriodStream(name, {
      signal,
    });
    if (result.ok) {
      appendMessage(`Deleted stream ${name}`, "success");
      return true;
    }
    appendMessage(
      `Failed to delete {name}: {result.status} {result.statusText}`,
      "warning"
    );
  } catch (err) {
    appendMessage(`${err}`, "warning");
  }
  return false;
}

export const blankModel: MultiPeriodStream = {
  pk: null,
  name: "",
  title: "",
  options: {},
  periods: [],
};

export interface UseMultiPeriodStreamHook {
  loaded: ReadonlySignal<string | null>;
  model: ReadonlySignal<DecoratedMultiPeriodStream>;
  modified: ReadonlySignal<boolean>;
  errors: ReadonlySignal<MpsModelValidationErrors>;
  isValid: ReadonlySignal<boolean>;
  discardChanges: () => void;
  setFields: (fields: Partial<MultiPeriodStream>) => void;
  addPeriod: () => void;
  setPeriodOrdering: (pks: (number | string)[]) => void;
  removePeriod: (pk: number | string) => void;
  modifyPeriod: (props: Omit<ModifyPeriodProps, 'model'>) => void;
  saveChanges: ({signal}: { signal: AbortSignal}) => Promise<boolean>;
  deleteStream: ({signal}: { signal: AbortSignal}) => Promise<boolean>;
}

export interface UseMultiPeriodStreamProps {
  name: string;
  newStream: boolean;
}

export const MultiPeriodModelContext = createContext<UseMultiPeriodStreamHook>(null);

export function useMultiPeriodStream({ name, newStream }: UseMultiPeriodStreamProps): UseMultiPeriodStreamHook {
  const apiRequests = useContext(EndpointContext);
  const { appendMessage } = useMessages();
  const originalData = useRef<MultiPeriodStream|null>(null);
  const loaded = useSignal<string | null>(null);
  const model = useSignal<DecoratedMultiPeriodStream>(decorateMultiPeriodStream(blankModel));
  const modified = useComputed<boolean>(() => model.value?.modified ?? false);
  const lastModified = useComputed<number>(() => model.value?.lastModified ?? 0);
  const localErrors = useComputed<MpsModelValidationErrors>(() => validateModel({ model }));
  const serverErrors = useSignal<ServerMpsModelValidationErrors>({ errors: {}, lastChecked: Date.now() });
  const errors = useComputed<MpsModelValidationErrors>(() => ({
    ...localErrors.value,
    ...serverErrors.value.errors,
  }));
  const isValid = useComputed<boolean>(
    () =>
      Object.keys(localErrors.value).length === 0 &&
      Object.keys(serverErrors.value).length === 0
  );

  const addPeriod = useCallback(() => addPeriodToModel({ model }), [model]);

  const removePeriod = useCallback(
    (pk: number | string) => {
      model.value = {
        ...model.value,
        periods: model.value.periods.filter((prd: MpsPeriod) => prd.pk !== pk),
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
    ({ periodPk, track, tracks, period = {} }: Omit<ModifyPeriodProps, 'model'>) =>
      modifyPeriod({ model, periodPk, track, tracks, period }),
    [model]
  );

  const setFields = useCallback(
    (props: Partial<MultiPeriodStream>) => {
      model.value = {
        ...model.value,
        ...props,
        modified: true,
        lastModified: Date.now(),
      };
    },
    [model]
  );

  const saveChanges = useCallback(async ({ signal }: { signal: AbortSignal}) => {
      if (!model.value || signal.aborted) {
        return false;
      }
      const data = createDataFromModel(model);
      try {
        const result =
          data.pk === null
            ? await apiRequests.addMultiPeriodStream(data, { signal })
            : await apiRequests.modifyMultiPeriodStream(name, data, { signal });

        result.errors?.forEach((err) => appendMessage("warning", err));
        if (result?.success === true) {
          if (data.pk === null) {
            appendMessage("success", `Added new stream ${name}`);
          } else {
            appendMessage("success", `Saved changes to ${name}`);
          }
          model.value = {
            ...decorateMultiPeriodStream(result.model),
            lastModified: Date.now(),
          };
          originalData.current = result.model;
          return true;
        }
      } catch (err) {
        appendMessage("warning", `${err}`);
      }
      return false;
    },
    [apiRequests, appendMessage, model, name]
  );

  const deleteStream = useCallback(
    ({ signal }) =>
      deleteMpsStream({ apiRequests, name, signal, appendMessage }),
    [apiRequests, appendMessage, name]
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

  const discardChanges = useCallback(() => {
    if (loaded.value !== name || !originalData.current) {
      return;
    }
    batch(() => {
      model.value = decorateMultiPeriodStream(originalData.current);
      loaded.value = null;
    });
  }, [loaded, model, name]);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchStreamIfRequired = async () => {
      if (loaded.value !== name) {
        if (newStream) {
          loaded.value = name;
          originalData.current = structuredClone(blankModel);
          model.value = decorateMultiPeriodStream(blankModel);
          return;
        }
        try{
          const data: MultiPeriodStream = await apiRequests.getMultiPeriodStream(name, { signal });
          originalData.current = data;
          batch(() => {
            loaded.value = name;
            model.value = decorateMultiPeriodStream(data);
          });
        } catch(err) {
          const msg = `Failed to get multi-period stream "${name}": ${err}`;
          appendMessage("danger", msg);
          originalData.current = null;
          batch(() => {
            loaded.value = name;
            serverErrors.value = {
              errors: {
                fetch: msg,
              },
              lastChecked: Date.now(),
            };
          });
        }
      }
    };

    fetchStreamIfRequired();

    return () => {
      if (loaded.value !== name) {
        controller.abort();
      }
    };
  }, [apiRequests, loaded, name, newStream, model, appendMessage, serverErrors]);

  return {
    setFields,
    addPeriod,
    setPeriodOrdering,
    removePeriod,
    modifyPeriod: modify,
    saveChanges,
    deleteStream,
    discardChanges,
    modified,
    errors,
    isValid,
    model,
    loaded,
  };
}
