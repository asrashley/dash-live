import type { JSX } from "preact";
import { type ReadonlySignal } from "@preact/signals";

export interface RoleSelectProps {
  name: string;
  roles: ReadonlySignal<string[]>;
  value: string | number;
  onChange: (ev: JSX.TargetedEvent<HTMLSelectElement>) => void;
  className: string;
  disabled?: boolean;
}

export function RoleSelect({
  name, roles, value, onChange, className, disabled,
}: RoleSelectProps) {
  return (
    <select
      className={className}
      name={name}
      value={value}
      onChange={onChange}
      disabled={disabled}
    >
      {roles.value.map((role) => (
        <option key={role} value={role}>
          {role}
        </option>
      ))}
    </select>
  );
}
