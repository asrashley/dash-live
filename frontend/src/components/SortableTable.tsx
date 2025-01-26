import { type JSX } from "preact";
import { type ReadonlySignal, useComputed } from "@preact/signals";

import { Icon } from "./Icon";
import { useSortAndFilter } from "../hooks/useSortAndFilter";

export interface SortableTableProps<
  T extends Record<string, string | number | boolean>
> {
  data: ReadonlySignal<T[]>;
}

export type SortableTableGenerator<
  T extends Record<string, string | number | boolean>
> = (props: SortableTableProps<T>) => JSX.Element;

export function createSortableTable<
  T extends Record<string, string | number | boolean>
>(
  headings: [keyof T, string][],
  primaryKey: keyof T,
  initialSortField: keyof T
): SortableTableGenerator<T> {
  const SortableHeading = ({
    name,
    setSort,
    sortField,
    sortOrder,
    title,
  }: {
    name: keyof T;
    title: string;
    sortOrder: ReadonlySignal<boolean>;
    sortField: ReadonlySignal<keyof T>;
    setSort: (field: keyof T, asc: boolean) => void;
  }) => {
    const linkClass = name === sortField.value ? " fs-6" : "";
    const iconName = sortOrder.value ? "sort-alpha-down" : "sort-alpha-up";
    const onClick = () => {
      setSort(name, name === sortField.value ? !sortOrder.value : true);
    };

    return (
      <a href="#" className={linkClass} onClick={onClick}>
        <span className="me-1 text-dark">{title}</span>
        {name === sortField.value ? <Icon name={iconName} /> : ""}
      </a>
    );
  };

  const RenderTable = ({ data }: SortableTableProps<T>) => {
    const { sortedData, sortField, sortOrder, setSort } = useSortAndFilter<T>(
      data,
      initialSortField
    );
    const sortNameClass = useComputed<string>(
      () => `sort_${String(sortField.value)}`
    );
    return (
      <table className="table table-striped table-bordered" style="width: auto">
        <thead>
          <tr className={sortNameClass}>
            {headings.map(([name, title]) => (
              <th key={name} className={String(name)}>
                <SortableHeading
                  name={name}
                  title={title}
                  setSort={setSort}
                  sortField={sortField}
                  sortOrder={sortOrder}
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.value.map((item) => {
            const pk = String(item[primaryKey]);
            const id = `opt_${pk}`;
            return (
              <tr key={pk} id={id}>
                {headings.map(([name]) => (
                  <td key={name} className={String(name)}>
                    {item[name]}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  };
  RenderTable.displayName = "SortableTable";
  return RenderTable;
}
