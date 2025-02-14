import { type ReadonlySignal, useComputed } from "@preact/signals";
import { useCallback, useContext } from "preact/hooks";

import { StaticInputProps } from "../../types/StaticInputProps";
import { WhoAmIContext } from "../../hooks/useWhoAmI";
import { InputFieldRow } from "../../components/InputFieldRow";
import { ValidatorSettings } from "../types/ValidatorSettings";
import { SetValueFunc } from "../../types/SetValueFunc";
import { ValidatorState, UseValidatorWebsocketHook } from "../hooks/useValidatorWebsocket";
import { useAllStreams } from "../../hooks/useAllStreams";
import { checkValidatorSettings } from "../utils/checkValidatorSettings";
import { ValidatorSettingsErrors } from "../types/ValidatorSettingsErrors";

const validatorForm: StaticInputProps[] = [
  {
    name: "manifest",
    title: "Manifest to check",
    type: "url",
    required: true,
    placeholder: "... manifest URL ...",
  },
  {
    name: "duration",
    title: "Maximum duration",
    type: "number",
    text: "seconds",
    min: 1,
    max: 3600,
  },
  {
    name: "prefix",
    title: "Destination directory",
    type: "text",
    pattern: "[A-Za-z0-9]{3,31}",
    text: "3 to 31 characters without any special characters",
    minlength: 3,
    maxlength: 31,
  },
  {
    name: "title",
    title: "Stream title",
    type: "text",
    minlength: 3,
    maxlength: 119,
  },
  {
    name: "row1",
    title: "",
    type: "multiselect",
    options: [
      {
        name: "encrypted",
        value: "encrypted",
        title: "Stream is encrypted?",
      },
      {
        name: "media",
        value: "media",
        title: "Check media segments",
      },
      {
        name: "verbose",
        value: "verbose",
        title: "Verbose output",
      },
    ],
  },
  {
    name: "row2",
    title: "",
    type: "multiselect",
    options: [
      {
        name: "pretty",
        value: "pretty",
        title: "Pretty print XML before validation",
      },
      {
        name: "save",
        value: "save",
        title: "Add stream to this server?",
      },
    ],
  },
];

export interface ValidatorFormProps {
  data: ReadonlySignal<ValidatorSettings>;
  setValue: SetValueFunc;
  state: UseValidatorWebsocketHook["state"];
  start: UseValidatorWebsocketHook["start"];
  cancel: () => void;
}

export function ValidatorForm({ state, data, setValue, start, cancel }: ValidatorFormProps) {
  const { user } = useContext(WhoAmIContext);
  const { allStreams } = useAllStreams();
  const disabledFields = useComputed(() => {
    const rv = {};
    if (!user.value.permissions.media) {
      rv["prefix"] = true;
      rv["save"] = true;
      rv["title"] = true;
    } else if (!data.value.save) {
      rv["prefix"] = true;
      rv["title"] = true;
    }
    return rv;
  });
  const errors = useComputed<ValidatorSettingsErrors>(() => checkValidatorSettings(data.value, allStreams.value));
  const disableSubmit = useComputed<boolean>(() => state.value === ValidatorState.ACTIVE || Object.keys(errors.value).length > 0);
  const disableCancel = useComputed<boolean>(() => state.value !== ValidatorState.ACTIVE);
  const cancelClassName = useComputed<string>(() => state.value === ValidatorState.ACTIVE ? "btn btn-danger": "btn btn-secondary");

  const onStart = useCallback((ev: Event) => {
    ev.preventDefault();
    start(data.value);
  }, [data.value, start]);

  const onCancel = useCallback((ev: Event) => {
    ev.preventDefault();
    cancel();
  }, [cancel]);

  return (
    <form id="manifest-form" name="manifest" class="card">
      {validatorForm.map((field) => (
        <InputFieldRow
          key={field.name}
          data={data}
          errors={errors}
          setValue={setValue}
          disabledFields={disabledFields}
          {...field}
        />
      ))}
      <div className="form-actions mt-2">
        <button className="btn btn-primary" onClick={onStart} disabled={disableSubmit}>
          Validate DASH stream
        </button>
        <button id="btn-cancel" className={cancelClassName} onClick={onCancel} disabled={disableCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
