import { createContext } from "preact";
import { useEffect, useState, useContext, useCallback } from "preact/hooks";
import { type ReadonlySignal, useSignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { AllMultiPeriodStreamsJson, MultiPeriodStreamSummary } from "../types/AllMultiPeriodStreams";

export interface UseAllMultiPeriodStreamsHook {
  error: ReadonlySignal<string | null>;
  streams: ReadonlySignal<MultiPeriodStreamSummary[]>;
  loaded: ReadonlySignal<boolean>;
  sort: (field: string, ascending: boolean) => void;
  sortField: string;
  sortAscending: boolean;
}

export const AllMultiPeriodStreamsContext = createContext<UseAllMultiPeriodStreamsHook>(null);

function sortStreams(streams: ReadonlySignal<MultiPeriodStreamSummary[]>, field: string, ascending: boolean): MultiPeriodStreamSummary[] {
  const newOrder = [...streams.value];
  newOrder.sort((a, b) => {
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
  return newOrder;
}

export function useAllMultiPeriodStreams(): UseAllMultiPeriodStreamsHook {
  const apiRequests = useContext(EndpointContext);
  const streams = useSignal<MultiPeriodStreamSummary[]>([]);
  const loaded = useSignal<boolean>(false);
  const error = useSignal<string | null>(null);
  const [sortField, setSortField] = useState<string>("name");
  const [sortAscending, setSortAscending] = useState<boolean>(true);

  const sort = useCallback(
    (field: string, ascending: boolean) => {
      setSortField(field);
      setSortAscending(ascending);
      streams.value = sortStreams(streams, field, ascending);
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
            error.value = `Fetching multi-period streams list failed: ${err}`;
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
