/* eslint-disable react/no-danger */
export function BooleanCell({ value }: { value: boolean; }) {
  if (value) {
    return (
      <span
        className="bool-yes"
        dangerouslySetInnerHTML={{ __html: "&check;" }} />
    );
  }
  return (
    <span className="bool-no" dangerouslySetInnerHTML={{ __html: "&cross;" }} />
  );
}
