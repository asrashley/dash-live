export interface IconProps {
  name: string;
  className?: string;
}

export function Icon({name, className=""}: IconProps) {
  const cname = `bi icon bi-${name} ${className}`;
  return <span className={cname} role="img" aria-label={`${name} icon`} />;
}
