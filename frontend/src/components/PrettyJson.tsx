import { Fragment } from "preact/jsx-runtime";

interface ValueProps {
    val: any;
}

function Value({ val }: ValueProps) {
  if (typeof val === "string") {
    return <span className="value">{`"${val}"`}</span>;
  }
  if (Array.isArray(val)) {
    return <Fragment>{`[`}{val.map((item) => <Value val={item} />)}{`]`}</Fragment>;
  }
  if (typeof val === "object") {
    return <PrettyJson data={val} />;
  }
  const sval = `${val}`;
  return <span className="value">{sval}</span>;
}

interface KeyValueProps {
    keyName: string;
    value: any;
    idx: number;
}
function KeyValue({ keyName, value, idx }: KeyValueProps) {
  return <Fragment>
    {idx > 0 ? ", " : ""}<span className="key">{keyName}</span>: <Value val={value} />
    </Fragment>;
}

export interface PrettyJsonProps {
  className?: string;
  data: object;
}

export function PrettyJson({ data = {}, className="" }: PrettyJsonProps) {
  const cn = `json bg-secondary-subtle border border-dark-subtle ${className}`;
  return (
    <div className={cn}>
      {Object.entries(data).map(([key, value], idx) => (
        <KeyValue key={key} idx={idx} keyName={key} value={value} />
      ))}
    </div>
  );
}
