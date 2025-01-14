import {
  type ReadonlySignal,
  useSignal,
  useSignalEffect,
} from "@preact/signals";
import { useMessages } from "../../hooks/useMessages";
import { useCallback, useRef, useState } from "preact/hooks";
import { LoadingSpinner } from "../../components/LoadingSpinner";

export interface ViewManifestProps {
  url: ReadonlySignal<URL>;
}

export function ViewManifest({ url: initialUrl }: ViewManifestProps) {
  const manifestUrl = useSignal<string>("");
  const loadedUrl = useSignal<string>("");
  const [xmlText, setXmlText] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const { appendMessage } = useMessages();
  const form = useRef<HTMLFormElement>();
  const onSubmit = useCallback(
    (ev: Event) => {
      ev.preventDefault();
      manifestUrl.value = form.current["mpd_url"].value;
    },
    [manifestUrl]
  );

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
    if (manifestUrl.value === "") {
      manifestUrl.value = initialUrl.value.href;
    }
    const fetchUrl = manifestUrl.value;
    fetchManifestIfRequired(fetchUrl);
    return () => {
      if (fetchUrl !== manifestUrl.value) {
        controller.abort("URL changed");
      }
    };
  });

  return (
    <div className="display-manifest">
      <form id="mpd-form" onSubmit={onSubmit} ref={form}>
        <div className="row mb-3 form-group row-field-title">
          <label className="col-1 col-form-label" for="model-title">
            MPD URL:
          </label>
          <div className="col-11">
            <input
              type="text"
              value={manifestUrl}
              name="mpd_url"
              id="id_mpd_url"
              className="form-control"
            />
          </div>
        </div>
      </form>
      {loading ? <LoadingSpinner /> : <pre id="manifest-xml">{xmlText}</pre>}
    </div>
  );
}
