import { afterEach, describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { TextInputRow } from "./TextInputRow.js";

describe("TextInputRow", () => {
  const name = "tirtest";
  const onInput = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should match snapshot", () => {
    const label = "the input label";
    const text = "description of the input";
    const { asFragment, getByText } = renderWithProviders(
      html`<${TextInputRow}
        name=${name}
        onInput=${onInput}
        placeholder="search..."
        required=${true}
        label=${label}
         text=${text}
      />`
    );
    getByText(label, { exact: false });
    getByText(text);
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows error", () => {
    const label = "the input label";
    const text = "description of the input";
    const error = "there is a problem with this value";
    const { getByText } = renderWithProviders(
      html`<${TextInputRow}
        name=${name}
        onInput=${onInput}
        placeholder="search..."
        required=${true}
        label=${label}
         text=${text}
         error=${error}
      />`
    );
    getByText(label, { exact: false });
    getByText(text);
    getByText(error);
  });
});
