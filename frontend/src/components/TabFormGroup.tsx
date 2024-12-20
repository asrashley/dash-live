import { useCallback, useState } from 'preact/hooks';

import { InputFieldRow } from "./InputFieldRow";
import { FormGroupsProps } from "../types/FormGroupsProps";
import { InputFormGroup } from '../types/InputFormGroup';
import { SetValueFunc } from '../types/SetValueFunc';
import { FormRowMode } from '../types/FormRowMode';

interface TabLinkProps {
  activeTab: string;
  setActive: (name: string) => void;
  disabled?: boolean;
  name: string;
}
function TabLink({activeTab, setActive, disabled, name}: TabLinkProps) {
    const active = activeTab === name;
    const props = {
        className: `nav-link ${active ? "active" : ""}`,
        href: '#',
        id: `${name}-tab`,
    };
    const onClick = useCallback((ev) => {
        ev.preventDefault();
        setActive(name);
    }, [setActive, name]);

    if (active) {
        props['aria-current'] = 'page';
    }
    if (disabled) {
        props['aria-disabled'] = true;
        props.className += ' disabled';
    }
    return <li className="nav-item"><a onClick={onClick} {...props}>{name}</a></li>;
}

interface TabContentProps extends InputFormGroup {
  activeTab: string;
  data: FormGroupsProps['data'];
  mode: FormRowMode;
  setValue: SetValueFunc;
}

function TabContent({activeTab, name, fields, ...props}: TabContentProps) {
    const active = activeTab === name;
    const className = `tab-pane fade ${active ? "show active": ""}`;
    const labelledBy = `${name}-tab`
    return <div id={name} className={className} role="tabpanel" aria-labelledby={labelledBy}>
      {fields.map(
        (field) => <InputFieldRow key={field.name} {...props} {...field} />
      )}
    </div>;
}

export function TabFormGroup({ groups, ...props }: FormGroupsProps) {
  const [ activeTab, setActiveTab ] = useState<string>(groups[0].name);
  return <div>
  <ul className="nav nav-tabs mb-3">
    {groups.map((grp) => <TabLink key={grp.name} activeTab={activeTab} setActive={setActiveTab} {...props} {...grp} />)}
  </ul>
  <div className="tab-content">
    {groups.map((grp) => <TabContent key={grp.name} activeTab={activeTab} {...props} {...grp} />)}
  </div>
</div>;
}
