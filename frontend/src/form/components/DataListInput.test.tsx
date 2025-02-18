import { signal } from "@preact/signals";
import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import { DataListInput } from "./DataListInput";
import { SelectOptionType } from "../types/SelectOptionType";

describe("DataListInput", () => {
  const options: SelectOptionType[] = [
    {
      value: "1",
      title: "option one",
    },
    {
      value: "2",
      title: "option two",
    },
  ];
  const value = signal<string>("1");

  test.each(["text", "number"])("should display %s data list", (type) => {
    const { asFragment, getBySelector, getAllBySelector } = renderWithProviders(
      <DataListInput type={type} name="dltest" value={value} options={options} />
    );
    expect(getBySelector('input[name="dltest"]').getAttribute('type')).toEqual(type);
    getBySelector("#list-dltest");
    expect(getAllBySelector("#list-dltest option").length).toEqual(options.length);
    expect(asFragment()).toMatchSnapshot();
  });
});
