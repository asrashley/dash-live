import { Fragment } from "preact";
import {
  createSortableTable,
  RenderCellProps,
} from "../../components/SortableTable";
import { useOptionsDetails } from "../hooks/useOptionsDetails";
import { InputOptionName } from "../types/InputOptionName";

function renderCell({ field, row }: RenderCellProps<InputOptionName>) {
  return <Fragment>{row[field]}</Fragment>;
}

const OptionsDetailTableComponent = createSortableTable<InputOptionName>({
  headings: [
    ["shortName", "Short Name"],
    ["fullName", "Full Name"],
    ["cgiName", "CGI Name"],
  ],
  initialSortField: "shortName",
  primaryKey: "shortName",
  renderCell,
});

export function OptionsDetailTable() {
  const { allOptions } = useOptionsDetails();
  return <OptionsDetailTableComponent data={allOptions} />;
}
