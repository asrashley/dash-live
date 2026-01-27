import {
  type ReadonlySignal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals";
import { useState } from "preact/hooks";

import { useMessages } from "../../hooks/useMessages";
import { LoadingSuspense } from "../../components/LoadingSuspense";

export interface ViewManifestProps {
    manifestUrl: ReadonlySignal<URL>;
}

export function ViewManifest({ manifestUrl }: ViewManifestProps) {
  const loadedUrl = useSignal<string>("");
  const [xmlText, setXmlText] = useState<string>("");
  const loaded = useSignal<boolean>(false);
  const error = useSignal<string | null>(null);
  const { appendMessage } = useMessages();
  const heading = useComputed<string>(() => `Manifest ${manifestUrl.value.href}`);

  useSignalEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchManifestIfRequired = async (url: string) => {
      if (url && loadedUrl.value !== url) {
        const headers = new Headers({
          accept: "application/dash+xml",
        });
        try {
          loaded.value = false;
          const response = await fetch(url, {
            headers,
            signal,
          });
          loadedUrl.value = url;
          if (response.ok) {
            const parser = new DOMParser();
            const doc = parser.parseFromString(
              await response.text(),
              "text/xml"
            );
            const ser = new XMLSerializer();
            setXmlText(ser.serializeToString(doc));
            error.value = null;
          } else {
            appendMessage(
              "danger",
              `Fetching manifest failed: ${response.status}: ${response.statusText}`
            );
            error.value = `Fetching manifest failed: ${response.status}: ${response.statusText}`;
          }
        } catch (err) {
          if (!signal.aborted) {
            appendMessage("danger", `Fetching manifest failed: ${err}`);
            error.value = `Fetching manifest failed: ${err}`;
          }
        } finally {
            loaded.value = true;
        }
      }
    };
    const fetchUrl = manifestUrl.value.href;
    fetchManifestIfRequired(fetchUrl);
    return () => {
      if (fetchUrl !== manifestUrl.value.href) {
        controller.abort("URL changed");
      }
    };
  });

  return (
    <div className="display-manifest">
      <LoadingSuspense action="fetching manifest" heading={heading} loaded={loaded} error={error}>
        <pre id="manifest-xml">{xmlText}</pre>
      </LoadingSuspense>
    </div>
  );
}
