import { type JSX } from "preact";

export interface IconProps {
  name: string;
  className?: string;
}

export function Icon({name, className=""}: IconProps) {
  const cname = `bi icon bi-${name} ${className}`;
  return <span className={cname} role="img" aria-label={`${name} icon`} />;
}

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
    return <a onClick={doNothing} class="disabled ${className}"><Icon name={name} /></a>;
  }
  return <a onClick={onClick} class={className} href="#"><Icon name={name} /></a>;
}
