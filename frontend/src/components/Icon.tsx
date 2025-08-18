import { type ReadonlySignal, useComputed } from "@preact/signals";

export interface IconProps {
  name: string | ReadonlySignal<string>;
  className?: string | ReadonlySignal<string>;
}

export function Icon({name, className}: IconProps) {
  const cname = useComputed<string>(() => {
    const nm = typeof name === "string" ? name : name.value;
    const cls = className ? typeof className === "string" ? className : className.value : "";
    return `bi icon bi-${nm} ${cls}`;
  });
  const label = useComputed<string>(() => `${typeof name === "string" ? name : name.value} icon`);
  return <span className={cname} role="img" aria-label={label} />;
}
