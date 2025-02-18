import { useContext } from "preact/hooks";
import { StreamOptionsContext } from "../types/StreamOptionsHook";
import { useFieldGroups } from "../hooks/useFieldGroups";
import { AccordionFormGroup } from "../../form/components/AccordionFormGroup";

const formLayout = [2, 5, 5];

export function StreamOptionsForm() {
  const { data, disabledFields, setValue } = useContext(StreamOptionsContext);
  const { homeFieldGroups } = useFieldGroups();

  return <form name="mpsOptions">
    <AccordionFormGroup
      groups={homeFieldGroups.value}
      data={data}
      disabledFields={disabledFields}
      expand="general"
      mode="cgi"
      setValue={setValue}
      layout={formLayout}
    />
  </form>;
}

