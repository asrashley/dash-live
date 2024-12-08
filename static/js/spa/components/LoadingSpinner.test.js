import { describe, expect, test } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { LoadingSpinner } from "./LoadingSpinner.js";

describe("LoadingSpinner", () => {
  test("should display spinner", () => {
    const { asFragment, getBySelector, getAllBySelector } = renderWithProviders(
      html`<${LoadingSpinner}  />`
    );
    getBySelector('.lds-ring');
    expect(getAllBySelector('.lds-ring > .lds-seg').length).toEqual(4);
    expect(asFragment()).toMatchSnapshot();
  });
});
