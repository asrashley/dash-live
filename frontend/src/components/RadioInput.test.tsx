import { afterEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../test/renderWithProviders";
import { RadioInput } from "./RadioInput";
import { SelectOptionType } from "../types/SelectOptionType";

describe("RadioInput", () => {
  const setValue = vi.fn();
  const name = "rtest";
  const options: SelectOptionType[] = [
    {
      name,
      selected: true,
      title: "option one",
      value: "one",
      disabled: false,
    },
    {
      name,
      selected: false,
      title: "option two",
      value: "two",
      disabled: false,
    },
  ];

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should display radio inputs", () => {
    const { asFragment, getBySelector, getByText } = renderWithProviders(
      <RadioInput options={options} setValue={setValue} />
    );
    getByText(options[0].title);
    getByText(options[1].title);
    const inp = getBySelector(`#radio-${name}-${options[0].value}`) as HTMLInputElement;
    expect(inp.checked).toEqual(true);
    expect(asFragment()).toMatchSnapshot();
  });

  test("can set value", () => {
    const { getBySelector } = renderWithProviders(
      <RadioInput options={options} setValue={setValue} />
    );
    const inp = getBySelector(`#radio-${name}-${options[1].value}`) as HTMLInputElement;
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
      <RadioInput options={opts} setValue={setValue} />
    );
    const inp = getBySelector(`#radio-${name}-${options[1].value}`) as HTMLInputElement;
    expect(inp.disabled).toEqual(true);
  });
});
