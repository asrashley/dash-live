import { useComputed } from "@preact/signals";
import { useContext, useCallback } from "preact/hooks";
import { useLocation } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";

import { FormRow } from "../../form/components/FormRow";
import { TextInputRow } from "../../form/components/TextInputRow";
import { useMessages } from "../../hooks/useMessages";
import { MultiPeriodModelContext } from "../../hooks/useMultiPeriodStream";
import { ButtonToolbar } from "./ButtonToolbar";
import { OptionsRow } from "./OptionsRow";
import { PeriodsTable } from "./PeriodsTable";
import { WhoAmIContext } from "../../user/hooks/useWhoAmI";
import { AppStateContext } from "../../appState";

export interface EditStreamFormProps {
  name: string;
  newStream: boolean;
}

export function EditStreamForm({ name, newStream }: EditStreamFormProps) {
  const setLocation = useLocation()[1];
  const { model, modified, errors, setFields, saveChanges } =
    useContext(MultiPeriodModelContext);
  const { dialog } = useContext(AppStateContext);
  const { user } = useContext(WhoAmIContext);
  const { appendMessage } = useMessages();
  const canModify = useComputed<boolean>(() => user.value.permissions.media);
  const validationClass = useComputed<string>(() => {
    if (!modified.value || !canModify.value) {
      return "";
    }
    return Object.keys(errors.value).length === 0
      ? "was-validated"
      : "has-validation";
  });
  const nameError = useComputed<string>(() => errors.value.name);
  const titleError = useComputed<string>(() => errors.value.title);

  const setName = useCallback(
    (ev: Event) => {
      setFields({ name: (ev.target as HTMLInputElement).value });
    },
    [setFields]
  );

  const setTitle = useCallback(
    (ev: Event) => {
      setFields({
        title: (ev.target as HTMLInputElement).value,
      });
    },
    [setFields]
  );

  const onSaveChanges = useCallback(async () => {
    const abortController = new AbortController();
    const { signal } = abortController;
    try {
      const success = await saveChanges({ signal });
      if (success && newStream) {
          const href = uiRouteMap.listMps.url();
          setLocation(href);
      }
    } catch(err) {
      appendMessage("warning", `Failed to save changes - ${err}`);
    }
  }, [appendMessage, newStream, saveChanges, setLocation]);

  const onDelete = useCallback(
    (ev: Event) => {
      ev.preventDefault();
      dialog.value = {
        backdrop: true,
        confirmDelete: {
          name,
          confirmed: false,
        },
      };
    },
    [dialog, name]
  );


  if (!model.value) {
    return <h3>Fetching data for stream "{name}"...</h3>;
  }

  const formRowClass = canModify.value ? "has-validation" : "";

  return (
    <div className={validationClass.value}>
      <TextInputRow
        name="name"
        label="Name"
        value={model.value.name}
        text="Unique name for this stream"
        onInput={setName}
        error={nameError}
        disabled={!canModify.value}
      />
      <TextInputRow
        name="title"
        label="Title"
        value={model.value.title}
        text="Title for this stream"
        onInput={setTitle}
        error={titleError}
        disabled={!canModify.value}
      />
      <OptionsRow name={name} canModify={canModify} />
      <FormRow className={formRowClass} name="periods" label="Periods">
        <PeriodsTable />
      </FormRow>
      <ButtonToolbar
        errors={errors}
        model={model}
        newStream={newStream}
        onSaveChanges={onSaveChanges}
        deleteStream={onDelete}
      />
    </div>
  );
}
