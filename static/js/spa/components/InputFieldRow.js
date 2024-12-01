import { html } from "htm/preact";
import { useComputed } from "@preact/signals";

import { FormRow } from "./FormRow.js";
import { Input } from "./Input.js";

export function InputFieldRow({
  name: cgiName,
  shortName,
  fullName,
  prefix,
  title,
  data,
  layout,
  mode,
  text,
  ...props
}) {
  const value = useComputed(() => {
    if (mode === "shortName") {
      return data.value[shortName];
    }
    if (mode === "cgi") {
      return data.value[cgiName];
    }
    if (prefix) {
      return data.value[prefix][fullName];
    }
    return data.value[fullName];
  });
  const name = mode === 'shortName' ? shortName : mode === 'cgi' ? cgiName: `${prefix}${prefix ? '__': ''}${fullName}`;
  return html`<${FormRow} name="${name}" label="${title}" text="${text}" layout=${layout} ...${props} >
    <${Input} ...${props} name="${name}" value=${value} title="${title}"
  /><//>`;
}
