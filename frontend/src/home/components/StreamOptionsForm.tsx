import { useContext } from "preact/hooks";
import { StreamOptionsContext } from "../types/StreamOptionsHook";
import { useFieldGroups } from "../hooks/useFieldGroups";
import { AccordionFormGroup } from "../../components/AccordionFormGroup";

function doNothing(ev: Event): boolean {
  ev.preventDefault();
  return false;
}

const formLayout = [2, 5, 5];

export function StreamOptionsForm() {
  const { data, disabledFields, setValue } = useContext(StreamOptionsContext);
  const { homeFieldGroups } = useFieldGroups();

  return <form name="mpsOptions" onSubmit={doNothing}>
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

