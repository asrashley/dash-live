import { type JSX } from 'preact';
import { useCallback, useState } from 'preact/hooks';

import { InputFieldRow } from "./InputFieldRow";
import { InputFormGroup } from '../types/InputFormGroup';
import { FormRowMode } from '../types/FormRowMode';
import { SetValueFunc } from '../types/SetValueFunc';
import { FormGroupsProps } from '../types/FormGroupsProps';

interface AccordionHeaderProps {
  expanded: boolean;
  index: number;
  title: string;
  onClick: (ev: JSX.TargetedEvent<HTMLButtonElement>) => void;
}

function AccordionHeader({ expanded, index, title, onClick }: AccordionHeaderProps) {
  const className = `accordion-button${ expanded ? '': ' collapsed'}`;

  return <div className="accordion-header">
    <button
      className={className}
      type="button"
      onClick={onClick}
      aria-expanded={expanded}
      aria-controls={`model-group-${index}`}
    >
      {title}
    </button>
  </div>;
}

interface AccordionCollapseProps extends Omit<InputFormGroup, 'value'> {
  index: number;
  expanded: boolean;
  mode: FormRowMode;
  data: FormGroupsProps['data'];
  layout?: FormGroupsProps['layout'];
  setValue: SetValueFunc;
}
function AccordionCollapse({ index, fields, expanded, ...props }: AccordionCollapseProps) {
  const className = `accordion-collapse collapse p-3${expanded ? " show" : ""}`;
  return <div className={className} id={`model-group-${index}`}>
    {fields.map(
      (field) => <InputFieldRow key={field.fullName} {...props} {...field} />
    )}
  </div>;
}

export interface AccordionItemProps {
  index: number;
  expand?: string;
  group: InputFormGroup;
  data: FormGroupsProps['data'];
  mode: FormRowMode;
  setValue: SetValueFunc;
}
export function AccordionItem({ group, index, expand, ...props }: AccordionItemProps) {
  const  { name } = group;
  const [expanded, setExpanded] = useState<boolean>(name === expand);

  const toggle = useCallback(() => {
    setExpanded(!expanded);
  },[expanded]);

  return <div
    className="accordion-item"
    id={`group-${name}`}
    data-name={name}
  >
    <AccordionHeader title={group.title} index={index} expanded={expanded} onClick={toggle} />
    <AccordionCollapse index={index} expanded={expanded} {...props} {...group} />
  </div>;
}

export function AccordionFormGroup({ groups, ...props }: FormGroupsProps) {
  return <div class="accordion mb-4">
    {groups.map(
      (grp, idx) =>
        <AccordionItem key={grp.name} group={grp} index={idx} {...props} />
    )}
  </div>;
}
