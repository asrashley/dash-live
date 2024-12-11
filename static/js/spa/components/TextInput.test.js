import { describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { TextInput } from "./TextInput.js";

describe("TextInput", () => {
  const onInput = vi.fn();

  test("matches snapshot", () => {
    const { asFragment, getBySelector } = renderWithProviders(
      html`<${TextInput}
        name="tname"
        onInput=${onInput}
        placeholder="search..."
        required=${true}
      />`
    );
    const inp = getBySelector(".form-control");
    expect(inp.className.trim()).toEqual("form-control is-valid");
    expect(inp.getAttribute("type")).toEqual("text");
    expect(inp.getAttribute("id")).toEqual("field-tname");
    expect(asFragment()).toMatchSnapshot();
  });

  test("text input with error", () => {
    const { getBySelector } = renderWithProviders(
      html`<${TextInput}
        name="tname"
        onInput=${onInput}
        error="input has an error"
      />`
    );
    const inp = getBySelector(".form-control");
    expect(inp.className.trim()).toEqual("form-control is-invalid");
  });
});
