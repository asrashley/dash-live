import { html } from "htm/preact";

import { renderWithProviders } from "./renderWithProviders";

function DefaultWrapper({ children }) {
  return html`<div>${children}</div>`;
}

export function renderHookWithProviders(
  hook,
  { initialState, Wrapper = DefaultWrapper, ...props } = {}
) {
  let result;

  function HookWrapper({ text }) {
    result = hook(initialState);
    return html`<div>${text}</div>`;
  }
  const now = new Date().toISOString();
  const { getByText, rerender } = renderWithProviders(
    html`<${Wrapper}><${HookWrapper} text=${now} /></${Wrapper}>`,
    props
  );
  getByText(now);
  return { result, rerender };
}
