import { createContext } from "preact";
import { useEffect, useState, useContext, useCallback } from "preact/hooks";
import { Signal, useSignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { AllMultiPeriodStreamsJson, MultiPeriodStreamSummary } from "../types/AllMultiPeriodStreams";

export interface UseAllMultiPeriodStreamsHook {
  error: Signal<string | null>;
  streams: Signal<MultiPeriodStreamSummary[]>;
  loaded: Signal<boolean>;
  sort: (field: string, ascending: boolean) => void;
  sortField: string;
  sortAscending: boolean;
}

export const AllMultiPeriodStreamsContext = createContext<UseAllMultiPeriodStreamsHook>(null);

function sortStreams(streams: Signal<MultiPeriodStreamSummary[]>, field: string, ascending: boolean) {
  streams.value.sort((a, b) => {
    const left = a[field];
    const right = b[field];
    if (left === right) {
      return 0;
    }
    if (left < right) {
      return ascending ? -1 : 1;
    }
    return ascending ? 1 : -1;
  });
}

export function useAllMultiPeriodStreams(): UseAllMultiPeriodStreamsHook {
  const apiRequests = useContext(EndpointContext);
  const streams = useSignal<MultiPeriodStreamSummary[]>([]);
  const loaded = useSignal<boolean>(false);
  const error = useSignal<string | null>(null);
  const [sortField, setSortField] = useState("name");
  const [sortAscending, setSortAscending] = useState(true);

  const sort = useCallback(
    (field, ascending) => {
      setSortField(field);
      setSortAscending(ascending);
      sortStreams(streams, field, ascending);
    },
    [streams]
  );

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchStreamsIfRequired = async () => {
      if (!loaded.value) {
        try {
          const data: AllMultiPeriodStreamsJson = await apiRequests.getAllMultiPeriodStreams({ signal });
          if (!signal.aborted) {
            loaded.value = true;
            streams.value = data.streams;
            error.value = null;
            sortStreams(streams, sortField, sortAscending);
          }
        } catch (err) {
          if (!signal.aborted) {
            console.error(err);
            error.value = `${err}`;
          }
        }
      }
    };

    fetchStreamsIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, error, loaded, sortAscending, sortField, streams]);

  return { error, streams, loaded, sort, sortField, sortAscending };
}
