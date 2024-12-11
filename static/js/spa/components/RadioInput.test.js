import { afterEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";
import { html } from "htm/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { RadioInput } from "./RadioInput.js";

describe("RadioInput", () => {
  const setValue = vi.fn();
  const name = "rtest";
  const options = [
    {
      name,
      selected: true,
      title: "option one",
      value: "one",
      disabled: false,
      setValue,
    },
    {
      name,
      selected: false,
      title: "option two",
      value: "two",
      disabled: false,
      setValue,
    },
  ];

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should display radio inputs", () => {
    const { asFragment, getBySelector, getByText } = renderWithProviders(
      html`<${RadioInput} options=${options} />`
    );
    getByText(options[0].title);
    getByText(options[1].title);
    const inp = getBySelector(`#radio-${name}-${options[0].value}`);
    expect(inp.checked).toEqual(true);
    expect(asFragment()).toMatchSnapshot();
  });

  test("can set value", () => {
    const { getBySelector } = renderWithProviders(
      html`<${RadioInput} options=${options} />`
    );
    const inp = getBySelector(`#radio-${name}-${options[1].value}`);
    expect(inp.disabled).toEqual(false);
    fireEvent.click(inp);
    expect(setValue).toHaveBeenCalledTimes(1);
    expect(setValue).toHaveBeenCalledWith(name, options[1].value);
  });

  test("can disable option", () => {
    const opts = [ options[0], {
        ...options[1],
        disabled: true,
    }];
    const { getBySelector } = renderWithProviders(
      html`<${RadioInput} options=${opts} />`
    );
    const inp = getBySelector(`#radio-${name}-${options[1].value}`);
    expect(inp.disabled).toEqual(true);
  });
});
