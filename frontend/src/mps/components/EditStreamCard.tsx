import { useCallback, useContext, useEffect } from "preact/hooks";
import { useSignal, useComputed, type Signal } from "@preact/signals";
import { navigate } from "wouter-preact/use-browser-location";

import { Card } from "../../components/Card";
import { FormRow } from "../../components/FormRow";
import { PrettyJson } from "../../components/PrettyJson";
import { TextInputRow } from "../../components/TextInputRow";
import { ConfirmDeleteDialog } from './ConfirmDeleteDialog';
import { PeriodsTable } from "./PeriodsTable";
import { TrackSelectionDialog } from './TrackSelectionDialog';
import { OptionsDialog } from './OptionsDialog';
import { AppStateContext } from "../../appState";
import { routeMap } from "@dashlive/routemap";

import { AllStreamsContext, useAllStreams  } from "../../hooks/useAllStreams";
import { useMultiPeriodStream, MultiPeriodModelContext } from "../../hooks/useMultiPeriodStream";
import { useMessages } from "../../hooks/useMessages";
import { ButtonToolbar } from "./ButtonToolbar";

interface OptionsRowProps {
  name: string;
  canModify: Signal<boolean>;
}
function OptionsRow({ name, canModify }: OptionsRowProps) {
  const { model } = useContext(MultiPeriodModelContext)
  const { dialog } = useContext(AppStateContext);
  const options = useComputed(() => model.value.options ?? {});

  const openDialog = () => {
    dialog.value = {
      mpsOptions: {
        options: options.value,
        lastModified: model.lastModified,
        name,
      },
      backdrop: true,
    };
  };

  return <FormRow name="options" label="Stream Options" type="json">
  <div className="d-flex flex-row">
<PrettyJson className="flex-fill me-1" data={options.value} />
{ canModify.value ? <button className="btn btn-primary" onClick={openDialog}>Options</button>: null }
  </div></FormRow>;
}

interface EditStreamFormProps {
  name: string;
  newStream: boolean;
}

function EditStreamForm({ name, newStream }: EditStreamFormProps) {
  const { model, modified, errors, setFields, saveChanges, deleteStream } = useContext(MultiPeriodModelContext)
  const { allStreams } = useContext(AllStreamsContext);
  const { dialog, user } = useContext(AppStateContext);
  const { appendMessage } = useMessages();
  const abortController = useSignal(new AbortController());
  const deleteConfirmed = useComputed(
    () => dialog.value?.confirmDelete?.confirmed === true
  );
  const canModify = useComputed(() => user.value.permissions.media);
  const validationClass = useComputed<string>(() => {
    if(!modified.value || !canModify.value) {
      return '';
    }
    return Object.keys(errors.value).length === 0 ? 'was-validated' : 'has-validation';
  });

  const setName = useCallback(
    (ev) => {
      setFields({name: ev.target.value});
    },
    [setFields]
  );

  const setTitle = useCallback(
    (ev) => {
      setFields({
        title: ev.target.value,
      });
    },
    [setFields]
  );

  const onSaveChanges = useCallback(() => {
    const { signal } = abortController.value;
    saveChanges({signal}).then(success => {
      if (success && newStream) {
        const href = routeMap.listMps.url();
        navigate(href, { replace: true });
      }
    }).catch(err => appendMessage(`${err}`, "warning"));
  }, [abortController.value, appendMessage, newStream, saveChanges]);

  const onDelete = useCallback(
    (ev) => {
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

  useEffect(() => {
    const { signal } = abortController.value;
    const deleteStreamIfConfirmed = async () => {
      if (!deleteConfirmed.value) {
        return;
      }
      const success = await deleteStream({signal});
      if (success){
        navigate(routeMap.listMps.url(), { replace: true });
      }
      dialog.value = null;
    };
    deleteStreamIfConfirmed();
  }, [abortController.value, allStreams, deleteConfirmed.value, deleteStream, dialog]);

  useEffect(() => {
    return () => {
      abortController.value.abort();
    }
  }, [abortController]);

  if (!model.value) {
    return <h3>Fetching data for stream "{name}"...</h3>;
  }

  const formRowClass = canModify.value ? 'has-validation' : '';

  return <div className={ validationClass.value }>
  <TextInputRow name="name" label="Name" value={model.value.name}
     text="Unique name for this stream" onInput={setName}
     error={errors.value.name} disabled={!canModify.value} />
  <TextInputRow name="title" label="Title" value={model.value.title}
    text="Title for this stream" onInput={setTitle}
    error={errors.value.title} disabled={!canModify.value} />
  <OptionsRow name={name} canModify={canModify} />
  <FormRow className={formRowClass} name="periods" label="Periods">
    <PeriodsTable />
  </FormRow>
  <ButtonToolbar errors={errors} model={model} newStream={newStream}
    onSaveChanges={onSaveChanges} deleteStream={onDelete} />
</div>;
}

interface HeaderProps {
  newStream: boolean;
  name: string;
}

function Header({newStream, name}: HeaderProps) {
  const { user } = useContext(AppStateContext);
  if (newStream) {
    return <h2>Add new Multi-Period stream</h2>;
  }
  const {media} = user.value.permissions;
  return <h2>{media ? 'Editing' : ''} Multi-Period stream "{name}"</h2>;
}

interface EditStreamCardProps {
  newStream?: boolean;
  name: string;
}

export function EditStreamCard({ name, newStream=false }: EditStreamCardProps) {
  const { dialog } = useContext(AppStateContext);
  const modelContext = useMultiPeriodStream({name, newStream});
  const streamsContext = useAllStreams();
  const header = <Header name={name} newStream={newStream} />;

  const closeDialog = useCallback(() => {
    dialog.value = null;
  }, [dialog]);

  return <AllStreamsContext.Provider value={streamsContext}>
  <MultiPeriodModelContext.Provider value={modelContext}>
    <Card header={header} id="edit_mps_form">
      <EditStreamForm name={name} newStream={newStream} />
    </Card>
    <TrackSelectionDialog onClose={closeDialog} />
    <ConfirmDeleteDialog onClose={closeDialog} />
    <OptionsDialog onClose={closeDialog} />
  </MultiPeriodModelContext.Provider>
  </AllStreamsContext.Provider>;
}
