import { describe, expect, test } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { CheckBox } from "./CheckBox.js";

describe("CheckBox", () => {
  test("should display CheckBox", () => {
    const { container, queryBySelector, asFragment } = renderWithProviders(
      html`<${CheckBox} name="test" label="Hello World" />`
    );
    expect(container.textContent).toMatch("Hello World");
    expect(queryBySelector('input[name="test"]')).not.toBeNull();
    expect(queryBySelector('label[for="check_test"]')).not.toBeNull();
    expect(asFragment()).toMatchSnapshot();
  });
});
