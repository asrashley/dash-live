import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { DataListInput } from "./DataListInput";

describe("DataListInput", () => {
  const options = [
    {
      value: "1",
      title: "option one",
      selected: true,
    },
    {
      value: "2",
      title: "option two",
      selected: false,
    },
  ];

  test.each(["text", "number"])("should display %s data list", (type) => {
    const { asFragment, getBySelector, getAllBySelector } = renderWithProviders(
      <DataListInput type={type} name="dltest" options={options} />
    );
    expect(getBySelector('input[name="dltest"]').getAttribute('type')).toEqual(type);
    getBySelector("#list-dltest");
    expect(getAllBySelector("#list-dltest option").length).toEqual(options.length);
    expect(asFragment()).toMatchSnapshot();
  });
});
