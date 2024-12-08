import { describe, expect, test } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { FormRow } from "./FormRow";

describe("FormRow", () => {
  test("form row with text", () => {
    const label = "form label";
    const text = "input description";
    const { asFragment, queryBySelector, getByText } = renderWithProviders(
      html`<${FormRow} name="test" label=${label} text=${text}><input type="text" /></${FormRow}>`
    );
    getByText(`${label}:`);
    getByText(text);
    expect(queryBySelector(".invalid-feedback")).toBeNull();
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows an error", () => {
    const label = "form label";
    const text = "input description";
    const error = "inout validation error";
    const { asFragment, getBySelector, getByText } = renderWithProviders(
      html`<${FormRow} label=${label} text=${text} name="test" error=${error}><input name="test" type="text" /></${FormRow}>`
    );
    getByText(`${label}:`);
    getByText(text);
    getBySelector(".invalid-feedback");
    getByText(error)
    expect(asFragment()).toMatchSnapshot();
  });

  test("can set column layout", () => {
    const label = "form label";
    const text = "input description";
    const layout = [3, 4, 5];
    const { asFragment, getBySelector } = renderWithProviders(
      html`<${FormRow} name="test" label=${label} text=${text} layout=${layout}><input type="text" /></${FormRow}>`
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
      html`<${FormRow} name="test" label=${label} layout=${layout}><input type="text" /></${FormRow}>`
    );
    getBySelector(".col-3");
    getBySelector("div.col-9");
    expect(asFragment()).toMatchSnapshot();
  });
});
