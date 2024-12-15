import { createContext } from "preact";
import { useEffect, useState, useContext, useCallback } from "preact/hooks";
import { useSignal } from "@preact/signals";

import { EndpointContext } from "../endpoints.js";

export const AllMultiPeriodStreamsContext = createContext();

function sortStreams(streams, field, ascending) {
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

export function useAllMultiPeriodStreams() {
  const apiRequests = useContext(EndpointContext);
  const streams = useSignal([]);
  const loaded = useSignal(false);
  const error = useSignal(null);
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
          const data = await apiRequests.getAllMultiPeriodStreams({ signal });
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
