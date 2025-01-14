import {
  type ReadonlySignal,
  useSignal,
  useSignalEffect,
} from "@preact/signals";
import { useState } from "preact/hooks";

import { useMessages } from "../../hooks/useMessages";
import { LoadingSpinner } from "../../components/LoadingSpinner";

export interface ViewManifestProps {
    manifestUrl: ReadonlySignal<URL>;
}

export function ViewManifest({ manifestUrl }: ViewManifestProps) {
  const loadedUrl = useSignal<string>("");
  const [xmlText, setXmlText] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const { appendMessage } = useMessages();

  useSignalEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchManifestIfRequired = async (url: string) => {
      if (url && loadedUrl.value !== url) {
        const headers = new Headers({
          accept: "application/dash+xml",
        });
        try {
          setLoading(true);
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
          } else {
            appendMessage(
              "danger",
              `Fetching manifest failed: ${response.status}: ${response.statusText}`
            );
            setXmlText(`Fetching manifest failed: ${response.status}: ${response.statusText}`);
          }
        } catch (err) {
          if (!signal.aborted) {
            appendMessage("danger", `Fetching manifest failed: ${err}`);
            setXmlText(`Fetching manifest failed: ${err}`);
          }
        } finally {
            setLoading(false);
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
      {loading ? <LoadingSpinner /> : <pre id="manifest-xml">{xmlText}</pre>}
    </div>
  );
}
