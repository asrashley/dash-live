import { describe, expect, test, vi } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { TextInput } from "./TextInput";

describe("TextInput", () => {
  const onInput = vi.fn();

  test("matches snapshot", () => {
    const { asFragment, getBySelector } = renderWithProviders(
      <TextInput
        name="tname"
        onInput={onInput}
        placeholder="search..."
        required={true}
      />
    );
    const inp = getBySelector(".form-control");
    expect(inp.className.trim()).toEqual("form-control is-valid");
    expect(inp.getAttribute("type")).toEqual("text");
    expect(inp.getAttribute("id")).toEqual("field-tname");
    expect(asFragment()).toMatchSnapshot();
  });

  test("text input with error", () => {
    const { getBySelector } = renderWithProviders(
      <TextInput
        name="tname"
        onInput={onInput}
        error="input has an error"
      />
    );
    const inp = getBySelector(".form-control");
    expect(inp.className.trim()).toEqual("form-control is-invalid");
  });
});
