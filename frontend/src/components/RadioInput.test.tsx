import { signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../test/renderWithProviders";
import { RadioInput } from "./RadioInput";
import { SelectOptionType } from "../types/SelectOptionType";

describe("RadioInput", () => {
  const currentValue = signal<string>("one");
  const disabledFields = signal<Record<string, boolean>>({});
  const setValue = vi.fn();
  const name = "rtest";
  const options: SelectOptionType[] = [
    {
      title: "option one",
      value: "one",
    },
    {
      title: "option two",
      value: "two",
    },
  ];

  beforeEach(() => {
    currentValue.value = "one";
    disabledFields.value = {};
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should display radio inputs", () => {
    const { asFragment, getBySelector, getByText } = renderWithProviders(
      <RadioInput options={options} name={name} value={currentValue} disabledFields={disabledFields} setValue={setValue} />
    );
    getByText(options[0].title);
    getByText(options[1].title);
    const inp = getBySelector(`#radio-${name}-${options[0].value}`) as HTMLInputElement;
    expect(inp.checked).toEqual(true);
    expect(asFragment()).toMatchSnapshot();
  });

  test("can set value", () => {
    const { getBySelector } = renderWithProviders(
      <RadioInput options={options} value={currentValue} name={name} disabledFields={disabledFields} setValue={setValue} />
    );
    const inp = getBySelector(`#radio-${name}-${options[1].value}`) as HTMLInputElement;
    expect(inp.disabled).toEqual(false);
    fireEvent.click(inp);
    expect(setValue).toHaveBeenCalledTimes(1);
    expect(setValue).toHaveBeenCalledWith(name, options[1].value);
  });

  test("can disable option", () => {
    disabledFields.value = {
      [`${name}__${options[1].value}`]: true,
    };
    console.dir(disabledFields.value);
    const { getBySelector } = renderWithProviders(
      <RadioInput options={options} name={name} value={currentValue} disabledFields={disabledFields} setValue={setValue} />
    );
    const inp = getBySelector(`#radio-${name}-${options[1].value}`) as HTMLInputElement;
    expect(inp.disabled).toEqual(true);
  });
});
