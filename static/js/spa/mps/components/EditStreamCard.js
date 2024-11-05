import { html } from "htm/preact";
import { useCallback, useContext, useEffect } from "preact/hooks";
import { useSignal, useComputed } from "@preact/signals";
import { Link } from "wouter-preact";
import { navigate } from "wouter-preact/use-browser-location";

import { Card, FormRow, TextInputRow } from "@dashlive/ui";
import { ConfirmDeleteDialog } from './ConfirmDeleteDialog.js';
import { PeriodsTable } from "./PeriodsTable.js";
import { TrackSelectionDialog } from './TrackSelectionDialog.js';
import { AppStateContext } from "../../appState.js";
import { routeMap } from "/libs/routemap.js";

import { useAllStreams, AllStreamsContext } from '../../hooks/useAllStreams.js';
import { useMultiPeriodStream, MultiPeriodModelContext } from '../../hooks/useMultiPeriodStream.js';

function ButtonToolbar({errors, onSaveChanges, deleteStream, model, newStream}) {
  const { user } = useContext(AppStateContext);
  const cancelUrl = routeMap.listMps.url();
  const disableSave = useComputed(() => {
    if (Object.keys(errors.value).length > 0) {
      return true;
    }
    return model.value.modified !== true;
  });

  if (!user.value.permissions.media) {
    return html`<div class="btn-toolbar">
      <${Link} class="btn btn-primary m-2" to=${cancelUrl}>Back</${Link}></div>`;
  }

  if (newStream) {
    return html`<div class="btn-toolbar">
    <button class="btn btn-success m-2" disabled=${disableSave.value}
      onClick=${onSaveChanges} >Save new stream</button>
    <${Link} class="btn btn-danger m-2" to=${cancelUrl}>Cancel</${Link}>
  </div>`;
  }

  const linkClass = `btn m-2 ${model.value.modified ? 'btn-warning': 'btn-primary'}`;

  return html`<div class="btn-toolbar">
    <button class="btn btn-success m-2" disabled=${disableSave.value}
      onClick=${onSaveChanges} >Save Changes</button>
    <button class="btn btn-danger m-2" onClick=${deleteStream}>Delete Stream</button>
    <${Link} class="${linkClass}" to=${cancelUrl}>
      ${model.value.modified ? "Discard Changes" : "Back"}
    </${Link}>
  </div>`;
}

function EditStreamForm({ name, newStream }) {
  const { model, modified, errors, setFields, saveChanges, deleteStream } = useContext(MultiPeriodModelContext)
  const { allStreams } = useContext(AllStreamsContext);
  const { dialog, user } = useContext(AppStateContext);
  const abortController = useSignal(new AbortController());
  const deleteConfirmed = useComputed(
    () => dialog.value?.confirmDelete?.confirmed === true
  );
  const canModify = useComputed(() => user.value.permissions.media);
  const validationClass = useComputed(() => {
    if(!modified.value || !canModify.value) {
      return '';
    }
    return Object.keys(errors.value) === 0 ? 'was-validated' : 'has-validation';
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

  const onSaveChanges = useCallback(async () => {
    const { signal } = abortController.value;
    const success = await saveChanges({signal});
    if (success && newStream) {
      const href = routeMap.listMps.url();
      navigate(href, { replace: true });
    }
  }, [abortController.value, newStream, saveChanges]);

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
        allStreams.value = null;
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
    return html`<h3>Fetching data for stream "${name}"...</h3>`;
  }

  return html`<div class="${ validationClass.value }">
  <${TextInputRow} name="name" label="Name" value=${model.value.name}
     text="Unique name for this stream" onInput=${setName}
     error=${errors.value.name} disabled=${!canModify.value} />
  <${TextInputRow} name="title" label="Title" value=${model.value.title}
    text="Title for this stream" onInput=${setTitle}
    error=${errors.value.title} disabled=${!canModify.value} />
  <${FormRow} className="${ canModify.value ? 'has-validation' : ''}"
    name="periods" label="Periods">
    <${PeriodsTable} errors=${errors} />
  </${FormRow}>
  <${ButtonToolbar} errors=${errors} model=${model} modified=${modified} newStream=${newStream}
    onSaveChanges=${onSaveChanges} deleteStream=${onDelete} />
</div>`;
}

function Header({newStream, name}) {
  const { user } = useContext(AppStateContext);
  if (newStream) {
    return html`<h2>Add new Multi-Period stream</h2>`;
  }
  const {media} = user.value.permissions;
  return html`<h2>${media ? 'Editing' : ''} Multi-Period stream "${name}"</h2>`;
}

export function EditStreamCard({ name, newStream }) {
  const modelContext = useMultiPeriodStream({name, newStream});
  const streamsContext = useAllStreams();
  const header = html`<${Header} name=${name} newStream=${newStream} />`;

  return html`<${AllStreamsContext.Provider} value=${streamsContext}>
  <${MultiPeriodModelContext.Provider} value=${modelContext}>
    <${Card} header=${header} id="edit_mps_form">
      <${EditStreamForm} name=${name} newStream=${newStream} />
    </${Card}>
    <${TrackSelectionDialog} />
    <${ConfirmDeleteDialog} />
  </${MultiPeriodModelContext.Provider}></${AllStreamsContext.Provider}>`;
}
