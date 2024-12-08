import { html } from "htm/preact";
import { useCallback } from "preact/hooks";

function RadioOption({ name, selected, title, value, disabled, setValue }) {
  const onClick = useCallback(() => {
    setValue(name, value);
  }, [name, setValue, value]);
  return html`<div class="form-check">
    <input
      class="form-check-input"
      type="radio"
      name="${name}"
      id="radio-${name}-${value}"
      onClick=${onClick}
      value="${value}"
      checked=${selected}
      disabled=${disabled}
    />
    <label class="form-check-label" for="radio-${name}-${value}"
      >${title}</label
    >
  </div>`;
}

export function RadioInput({ options, ...props }) {
  return html`<div>
    ${options.map(
      (opt) => html`<${RadioOption} key=${opt.value} ...${props} ...${opt} />`
    )}
  </div>`;
}
