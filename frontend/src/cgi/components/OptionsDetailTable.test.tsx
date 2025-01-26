import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { signal } from "@preact/signals";
import { fireEvent } from "@testing-library/preact";

import { fieldGroups } from "@dashlive/options";

import { renderWithProviders } from "../../test/renderWithProviders";
import {
  type UseOptionsDetailsHook,
  useOptionsDetails,
} from "../hooks/useOptionsDetails";
import { InputOptionName } from "../types/InputOptionName";
import { OptionsDetailTable } from "./OptionsDetailTable";

vi.mock("../hooks/useOptionsDetails");

function createOptionNames(): InputOptionName[] {
  const names: InputOptionName[] = [];
  fieldGroups.forEach((grp) => {
    grp.fields.forEach(({ name, fullName, shortName }) => {
      names.push({
        cgiName: name,
        fullName,
        shortName,
      });
    });
  });
  return names;
}

describe("OptionsDetailTable component", () => {
  const allOptions = signal<InputOptionName[]>([]);
  const useOptionsHook: UseOptionsDetailsHook = {
    allOptions,
  };
  const useOptionsDetailsMock = vi.mocked(useOptionsDetails);

  beforeEach(() => {
    useOptionsDetailsMock.mockReturnValue(useOptionsHook);
    allOptions.value = createOptionNames();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", () => {
    const { asFragment, getBySelector } = renderWithProviders(
      <OptionsDetailTable />
    );
    fieldGroups.forEach((grp) => {
      grp.fields.forEach((field) => {
        const row = getBySelector(`#opt_${field.shortName}`) as HTMLElement;
        const full = row.querySelector(".fullName") as HTMLElement | null;
        expect(full).not.toBeNull();
        expect(full.innerHTML.trim()).toEqual(field.fullName);
        const sn = row.querySelector(".shortName") as HTMLElement | null;
        expect(sn).not.toBeNull();
        expect(sn.innerHTML.trim()).toEqual(field.shortName);
        const cgi = row.querySelector(".cgiName") as HTMLElement | null;
        expect(cgi).not.toBeNull();
        expect(cgi.innerHTML.trim()).toEqual(field.name);
      });
    });
    expect(asFragment()).toMatchSnapshot();
  });

  test.each([
    ["fullName"],
    ["shortName"],
    ["cgiName"],
  ])("can sort by %s", (field: keyof InputOptionName) => {
    const { getBySelector, getAllBySelector } = renderWithProviders(<OptionsDetailTable />);
    const heading = getBySelector(`th.${field} > a`) as HTMLElement;
    fireEvent.click(heading);
    const items = [...allOptions.value];
    items.sort((a, b) => {
      const aVal = a[field].toLowerCase();
      const bVal = b[field].toLowerCase();
      if (field === "shortName"){
        return bVal.localeCompare(aVal);
      }
      return aVal.localeCompare(bVal);
    });
    const cols = [...getAllBySelector(`td.${field}`)];
    cols.forEach((elt, idx) => {
      expect(elt.innerHTML.trim()).toEqual(items[idx][field]);
    });
  });
});
