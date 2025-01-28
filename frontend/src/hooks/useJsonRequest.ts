import { useCallback, useEffect } from "preact/hooks";
import { batch, type ReadonlySignal, useSignal } from "@preact/signals";

export interface UseJsonRequestHook<T> {
  data: ReadonlySignal<T>;
  loaded: ReadonlySignal<boolean>;
  error: ReadonlySignal<string | null>;
  setData: (data: Readonly<T>) => void;
}

export interface UseJsonRequestProps<T> {
  request: (signal: AbortSignal) => Promise<T>;
  initialData: T;
  name: string;
}

export function useJsonRequest<T>({ request, initialData, name }: UseJsonRequestProps<T>): UseJsonRequestHook<T> {
  const data = useSignal<T>(initialData);
  const error = useSignal<string | null>(null);
  const loaded = useSignal<boolean>(false);
  const setData = useCallback((newData: Readonly<T>) => {
    // TODO: how to cancel an in-progress fetch?
    batch(() => {
      data.value = structuredClone(newData);
      loaded.value = true;
      error.value = null;
    });
  }, [data, error, loaded]);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchDataIfRequired = async () => {
      if (!loaded.value) {
        try {
          const response = await request(signal);
          batch(() => {
            data.value = response as T;
            error.value = null;
            loaded.value = true;

          });
        } catch (err) {
          if (!signal.aborted) {
            error.value = `Failed to fetch ${name} - ${err}`;
          }
        }
      }
    };

    fetchDataIfRequired();

    return () => {
      if (!loaded.value) {
        controller.abort();
      }
    };
  }, [data, error, loaded, name, request]);

  return { data, error, loaded, setData };
}
