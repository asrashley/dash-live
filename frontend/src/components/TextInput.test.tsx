import { describe, expect, test, vi } from "vitest";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../test/renderWithProviders";
import { TextInput } from "./TextInput";

describe("TextInput", () => {
  const onInput = vi.fn();
  const error = signal<string|undefined>();

  test("matches snapshot", () => {
    const { asFragment, getBySelector } = renderWithProviders(
      <TextInput
        name="tname"
        onInput={onInput}
        placeholder="search..."
        required={true}
        error={error}
      />
    );
    const inp = getBySelector(".form-control");
    expect(inp.className.trim()).toEqual("form-control is-valid");
    expect(inp.getAttribute("type")).toEqual("text");
    expect(inp.getAttribute("id")).toEqual("field-tname");
    expect(asFragment()).toMatchSnapshot();
  });

  test("text input with error", () => {
    error.value = "input has an error";
    const { getBySelector } = renderWithProviders(
      <TextInput
        name="tname"
        onInput={onInput}
        error={error}
      />
    );
    const inp = getBySelector(".form-control");
    expect(inp.className.trim()).toEqual("form-control is-invalid");
  });
});
