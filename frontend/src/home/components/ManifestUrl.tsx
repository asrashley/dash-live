import { type Signal } from "@preact/signals-core";

interface ManifestUrlProps {
   manifestUrl: Signal<URL>;
}
export function ManifestUrl({ manifestUrl }: ManifestUrlProps) {
  return <div className="manifest-url rounded border">
    <span className="fw-semibold">Manifest URL: </span>
    <a id="dashurl" href={manifestUrl.value.href}>
      {manifestUrl.value.pathname}{manifestUrl.value.search}
    </a>
  </div>;
}
