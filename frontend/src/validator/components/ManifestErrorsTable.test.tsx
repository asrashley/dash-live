import { signal } from "@preact/signals";
import { describe, expect, test } from "vitest";
import { ErrorEntry } from "../types/ErrorEntry";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ManifestErrorsTable } from "./ManifestErrorsTable";

describe("ManifestErrorsTable component", () => {
  const errors = signal<ErrorEntry[]>([]);

  test("matches snapshot", () => {
    errors.value = [
      {
        assertion: {
          filename: "period.py",
          line: 345,
        },
        location: [20, 30],
        clause: "1.2.3",
        msg: "validator assertion message",
      },
      {
        assertion: {
          filename: "representation.py",
          line: 123,
        },
        location: [120, 130],
        clause: "3.4.5",
        msg: "representation has an error",
      },
    ];
    const { asFragment, getByText, getBySelector } = renderWithProviders(
      <ManifestErrorsTable errors={errors} />
    );
    expect(getBySelector("table").classList.contains("d-none")).toEqual(false);
    errors.value.forEach(({ assertion, msg }) => {
      getByText(`${assertion.filename}:${assertion.line}`);
      getByText(msg);
    });
    expect(asFragment()).toMatchSnapshot();
  });

  test("table is hidden when there are no errors", () => {
    errors.value = [];
    const { getBySelector } = renderWithProviders(
      <ManifestErrorsTable errors={errors} />
    );
    expect(getBySelector("table").classList.contains("d-none")).toEqual(true);
  });
});
