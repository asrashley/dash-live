import { useComputed } from "@preact/signals";
import { type ReadonlySignal } from "@preact/signals-core";
import { useCallback, useRef } from "preact/hooks";

interface ManifestUrlProps {
   manifestUrl: ReadonlySignal<URL>;
   editable: ReadonlySignal<boolean>;
   setValue: (url: string) => void;
}

export function ManifestUrl({ manifestUrl, editable, setValue }: ManifestUrlProps) {
  const inpElt = useRef<HTMLInputElement>();
  const inputClass = useComputed<string>(() => `form-control${ editable.value ? "" : " d-none"}`);
  const linkClass = useComputed<string>(() => editable.value ? "d-none": "link link-underline-opacity-25");
  const onSubmit = useCallback(
    (ev: Event) => {
      ev.preventDefault();
      setValue(inpElt.current.value);
    },
    [setValue]
  );

  return <div className="manifest-url rounded border">
      <form id="mpd-form" onSubmit={onSubmit}>
        <div className="form-group d-flex flex-row row-field-title">
          <label className="col-form-label fw-semibold me-1" for="id_mpd_url">
            MPD URL :
          </label>
          <div className="flex-fill">
            <input
              type="text"
              value={manifestUrl.value.href}
              name="mpd_url"
              id="id_mpd_url"
              className={inputClass}
              ref={inpElt}
            />
            <a id="dashurl" href={manifestUrl.value.href} className={linkClass}>
             {manifestUrl.value.pathname}{manifestUrl.value.search}
            </a>
          </div>
        </div>
      </form>
  </div>;
}
