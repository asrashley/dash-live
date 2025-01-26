import { createSortableTable } from "../../components/SortableTable";
import {
  useOptionsDetails,
} from "../hooks/useOptionsDetails";
import { InputOptionName } from "../types/InputOptionName";


const OptionsDetailTableComponent = createSortableTable<InputOptionName>([
  ["shortName", "Short Name"],
  ["fullName", "Full Name"],
  ["cgiName", "CGI Name"],
], "shortName", "shortName");

export function OptionsDetailTable() {
  const { allOptions } = useOptionsDetails();
  return <OptionsDetailTableComponent data={allOptions} />;
}
