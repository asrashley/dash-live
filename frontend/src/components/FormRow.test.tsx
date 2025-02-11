import { beforeEach, describe, expect, test } from "vitest";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../test/renderWithProviders";
import { FormRow } from "./FormRow";

describe("FormRow", () => {
  const error = signal<string|undefined>();

  beforeEach(() => {
    error.value = undefined;
  });

  test("form row with text", () => {
    const label = "form label";
    const text = "input description";
    const { asFragment, getBySelector, getByText } = renderWithProviders(
      <FormRow name="test" label={label} error={error} text={text}><input type="text" /></FormRow>
    );
    getByText(`${label}:`);
    getByText(text);
    const elt = getBySelector(".invalid-feedback") as HTMLElement;
    expect(elt.classList.contains("d-none")).toEqual(true);
    expect(elt.classList.contains("d-block")).toEqual(false);
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows an error", () => {
    const label = "form label";
    const text = "input description";
    error.value = "input validation error";
    const { asFragment, getBySelector, getByText } = renderWithProviders(
      <FormRow label={label} text={text} name="test" error={error}><input name="test" type="text" /></FormRow>
    );
    getByText(`${label}:`);
    getByText(text);
    const elt = getBySelector(".invalid-feedback");
    expect(elt.classList.contains("d-none")).toEqual(false);
    expect(elt.classList.contains("d-block")).toEqual(true);
    getByText(error)
    expect(asFragment()).toMatchSnapshot();
  });

  test("can set column layout", () => {
    const label = "form label";
    const text = "input description";
    const layout = [3, 4, 5];
    const { asFragment, getBySelector } = renderWithProviders(
      <FormRow name="test" label={label} text={text} error={error} layout={layout}><input type="text" /></FormRow>
    );
    getBySelector(".col-3");
    getBySelector("div.col-4");
    getBySelector("div.col-5");
    expect(asFragment()).toMatchSnapshot();
  });

  test("can set column layout for row without text", () => {
    const label = "form label";
    const layout = [3, 4, 5];
    const { asFragment, getBySelector } = renderWithProviders(
      <FormRow name="test" error={error} label={label} layout={layout}><input type="text" /></FormRow>
    );
    getBySelector(".col-3");
    getBySelector("div.col-9");
    expect(asFragment()).toMatchSnapshot();
  });
});
