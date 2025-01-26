import { useCallback, useContext } from "preact/hooks";
import { type ReadonlySignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { CgiOptionDescription } from "../types/CgiOptionDescription";
import { useJsonRequest } from "./useJsonRequest";

export interface UseCgiOptionsHook {
  allOptions: ReadonlySignal<CgiOptionDescription[]>;
  loaded: ReadonlySignal<boolean>;
  error: ReadonlySignal<string | null>;
}

export function useCgiOptions(): UseCgiOptionsHook {
  const apiRequests = useContext(EndpointContext);
  const request = useCallback((signal: AbortSignal) => apiRequests.getCgiOptions({
    signal,
  }), [apiRequests]);
  const {data: allOptions, error, loaded } = useJsonRequest<CgiOptionDescription[]>({
    request,
    initialData: [],
    name: 'CGI options',
  });

  return { allOptions, error, loaded };
}
