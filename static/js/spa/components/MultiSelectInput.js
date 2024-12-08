import { html } from "htm/preact";
import { useCallback } from "preact/hooks";

export function MultiSelectInput({ className, options, name, setValue }) {
  const onClick = useCallback((ev) => {
    const { name, checked } = ev.target;
    setValue(name, checked);
  }, [setValue]);

  return html`<div data-testid="msi-${name}" className=${className}>
    ${options.map(
      ({ name, title, checked }) => html`<div
        className="form-check form-check-inline"
      >
        <input
          name=${name}
          className="form-check-input"
          type="checkbox"
          id="msi${name}"
          checked=${checked}
          onClick=${onClick}
        />
        <label className="form-check-label me-3" for="msi${name}"
          >${title}</label
        >
      </div>`
    )}
  </div>`;
}
