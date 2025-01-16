import { useContext } from "preact/hooks";
import { useComputed, type ReadonlySignal } from "@preact/signals";

import { MultiPeriodModelContext } from "../../hooks/useMultiPeriodStream";
import { AppStateContext } from "../../appState";
import { FormRow } from "../../components/FormRow";
import { PrettyJson } from "../../components/PrettyJson";

export interface OptionsRowProps {
  name: string;
  canModify: ReadonlySignal<boolean>;
}

export function OptionsRow({ name, canModify }: OptionsRowProps) {
  const { model } = useContext(MultiPeriodModelContext);
  const { dialog } = useContext(AppStateContext);
  const options = useComputed(() => model.value.options ?? {});

  const openDialog = () => {
    dialog.value = {
      mpsOptions: {
        options: options.value,
        lastModified: model.value.lastModified,
        name,
      },
      backdrop: true,
    };
  };

  return (
    <FormRow name="options" label="Stream Options">
      <div className="d-flex flex-row">
        <PrettyJson className="flex-fill me-1" data={options.value} />
        {canModify.value ? (
          <button className="btn btn-primary" onClick={openDialog}>
            Options
          </button>
        ) : null}
      </div>
    </FormRow>
  );
}
