import { useCallback, useState } from "preact/hooks";
import { type ReadonlySignal } from "@preact/signals";

import { BaseInputProps } from "../types/BaseInputProps";

export interface PasswordInputProps extends BaseInputProps {
  allowReveal?: boolean;
  value: ReadonlySignal<string>;
}

export function PasswordInput({
  allowReveal = false,
  className = "",
  type,
  ...props
}: PasswordInputProps) {
  const btnClass = allowReveal ? "btn btn-outline-secondary" : "d-none";
  const [show, setShow] = useState<boolean>(false);
  const onClick = useCallback(() => {
    setShow(!show && allowReveal);
  }, [allowReveal, show]);

  return (
    <div className="input-group">
      <input className={className} type={show ? "text" : type} {...props} />
      <button
        className={btnClass}
        type="button"
        onClick={onClick}
      >
        {show ? "Hide": "Reveal"}
      </button>
    </div>
  );
}
