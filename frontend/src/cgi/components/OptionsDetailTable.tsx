import { Fragment } from "preact";
import { useComputed } from "@preact/signals";

import {
  useOptionsDetails,
  UseOptionsDetailsHook,
} from "../hooks/useOptionsDetails";
import { InputOptionName } from "../types/InputOptionName";
import { Icon } from "../../components/Icon";

function OptionsDetailRow({ shortName, fullName, cgiName }: InputOptionName) {
  return (
    <tr id={`opt_${shortName}`}>
      <td class="short-name">{shortName}</td>
      <td class="full-name">{fullName}</td>
      <td class="cgi-param">{cgiName}</td>
    </tr>
  );
}

interface SortableHeadingProps {
  name: string;
  setSortField: UseOptionsDetailsHook["setSortField"];
  sortAscending: UseOptionsDetailsHook["sortAscending"];
  sortField: UseOptionsDetailsHook["sortField"];
  title: string;
}

function SortableHeading({
  name,
  setSortField,
  sortField,
  sortAscending,
  title,
}: SortableHeadingProps) {
  const linkClass = `link${name === sortField.value ? " fw-bold" : ""}`;
  const iconClassName = name === sortField.value ? "opacity-100" : "opacity-50";
  const iconName = sortAscending.value ? "sort-alpha-down" : "sort-alpha-up";
  const onClick = () => {
    setSortField(name, name === sortField.value ? !sortAscending.value : true);
  };

  return (
    <a href="#" className={linkClass} onClick={onClick}>
      <span className="me-1">{title}</span>
      <Icon name={iconName} className={iconClassName} />
    </a>
  );
}

export function OptionsDetailTable() {
  const { allOptions, ...sortProps } = useOptionsDetails();
  const sortNameClass = useComputed<string>(
    () => `sort_${sortProps.sortField.value}`
  );

  return (
    <Fragment>
      <a id="json" />
      <table
        className="cgi-json-options table table-striped table-bordered"
        style="width: auto"
      >
        <thead>
          <tr className={sortNameClass}>
            <th className="short-name">
              <SortableHeading
                name="shortName"
                title="Short Name"
                {...sortProps}
              />
            </th>
            <th className="full-name">
              <SortableHeading
                name="fullName"
                title="Full Name"
                {...sortProps}
              />
            </th>
            <th className="cgi-param">
              <SortableHeading name="cgiName" title="CGI Name" {...sortProps} />
            </th>
          </tr>
        </thead>
        <tbody>
          {allOptions.value.map((opt) => (
            <OptionsDetailRow key={opt.shortName} {...opt} />
          ))}
        </tbody>
      </table>
    </Fragment>
  );
}
