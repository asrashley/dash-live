import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import { CheckBox } from "./CheckBox";

describe("CheckBox", () => {
  test("should display CheckBox", () => {
    const { container, queryBySelector, asFragment } = renderWithProviders(
      <CheckBox name="test" label="Hello World" />
    );
    expect(container.textContent).toMatch("Hello World");
    expect(queryBySelector('input[name="test"]')).not.toBeNull();
    expect(queryBySelector('label[for="check_test"]')).not.toBeNull();
    expect(asFragment()).toMatchSnapshot();
  });
});
