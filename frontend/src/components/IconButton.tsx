import { type JSX } from "preact";
import { Icon, IconProps } from "./Icon";

function doNothing(ev) {
    ev.preventDefault();
    return false;
  }

  export interface IconButtonProps extends IconProps {
    onClick: (ev: JSX.TargetedEvent<HTMLAnchorElement>) => void;
    disabled?: boolean;
  }

  export function IconButton({name, onClick, disabled, className=""}: IconButtonProps) {
    if (disabled) {
      return <a onClick={doNothing} className={`disabled ${className}`}><Icon name={name} /></a>;
    }
    return <a onClick={onClick} className={className}><Icon name={name} /></a>;
  }
