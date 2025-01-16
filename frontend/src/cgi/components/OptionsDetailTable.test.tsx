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
  const sortField = signal<string>("fullName");
  const sortAscending = signal<boolean>(true);
  const setSortField = vi.fn();
  const useOptionsHook: UseOptionsDetailsHook = {
    allOptions,
    sortField,
    sortAscending,
    setSortField,
  };
  const useOptionsDetailsMock = vi.mocked(useOptionsDetails);

  beforeEach(() => {
    useOptionsDetailsMock.mockReturnValue(useOptionsHook);
    allOptions.value = createOptionNames();
    sortField.value = "fullName";
    sortAscending.value = true;
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
        const full = row.querySelector(".full-name") as HTMLElement | null;
        expect(full).not.toBeNull();
        expect(full.innerHTML.trim()).toEqual(field.fullName);
        const sn = row.querySelector(".short-name") as HTMLElement | null;
        expect(sn).not.toBeNull();
        expect(sn.innerHTML.trim()).toEqual(field.shortName);
        const cgi = row.querySelector(".cgi-param") as HTMLElement | null;
        expect(cgi).not.toBeNull();
        expect(cgi.innerHTML.trim()).toEqual(field.name);
      });
    });
    expect(asFragment()).toMatchSnapshot();
  });

  test.each([
    ["full-name", "fullName"],
    ["short-name", "shortName"],
    ["cgi-param", "cgiName"],
  ])("can sort by %s", (field: string, name: string) => {
    const { getBySelector } = renderWithProviders(<OptionsDetailTable />);
    const heading = getBySelector(`th.${field} > a`) as HTMLElement;
    fireEvent.click(heading);
    expect(setSortField).toHaveBeenCalledTimes(1);
    expect(setSortField).toHaveBeenCalledWith(name, name !== sortField.value);
  });
});
