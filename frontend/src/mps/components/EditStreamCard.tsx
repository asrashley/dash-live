import { useCallback, useContext } from "preact/hooks";
import { useLocation } from "wouter-preact";
import { useComputed } from "@preact/signals";

import { uiRouteMap } from "@dashlive/routemap";

import { Card } from "../../components/Card";
import { ConfirmDeleteDialog } from "./ConfirmDeleteDialog";
import { TrackSelectionDialog } from "./TrackSelectionDialog";
import { OptionsDialog } from "./OptionsDialog";
import { EditStreamForm } from "./EditStreamForm";

import { AppStateContext } from "../../appState";
import { AllStreamsContext, useAllStreams } from "../../hooks/useAllStreams";
import {
  useMultiPeriodStream,
  MultiPeriodModelContext,
} from "../../hooks/useMultiPeriodStream";
import { WhoAmIContext } from "../../user/hooks/useWhoAmI";
import { useMessages } from "../../hooks/useMessages";
import { LoadingSuspense } from "../../components/LoadingSuspense";

interface HeaderProps {
  newStream: boolean;
  name: string;
}

function Header({ newStream, name }: HeaderProps) {
  const { user } = useContext(WhoAmIContext);
  if (newStream) {
    return <h2>Add new Multi-Period stream</h2>;
  }
  const { media } = user.value.permissions;
  return (
    <h2>
      {media ? "Editing" : ""} Multi-Period stream "{name}"
    </h2>
  );
}

interface EditStreamCardProps {
  newStream?: boolean;
  name: string;
}

export function EditStreamCard({
  name,
  newStream = false,
}: EditStreamCardProps) {
  const [, setLocation] = useLocation();
  const { dialog } = useContext(AppStateContext);
  const { appendMessage } = useMessages();
  const modelContext = useMultiPeriodStream({ name, newStream });
  const streamsContext = useAllStreams();
  const header = <Header name={name} newStream={newStream} />;
  const loaded = useComputed<boolean>(() => (newStream || modelContext.loaded.value) && streamsContext.loaded.value);
  const error = useComputed<string | null>(() => {
    const errors: string[] = [];
    if (!newStream && modelContext.loaded.value) {
      for(const item of Object.values(modelContext.errors.value || {}) ) {
        if(typeof item === 'string') {
          errors.push(item);
        } else if(typeof item === 'object' && item !== null) {
          errors.push(...Object.values(item).filter(v => typeof v === 'string') as string[]);
        }
      }
    }
    if(streamsContext.error.value) {
      errors.push(streamsContext.error.value);
    }
    if (errors.length === 0) {
      return null;
    }
    return errors.join(', ');
  });

  const closeDialog = useCallback(() => {
    dialog.value = null;
  }, [dialog]);

  const confirmDeleteStream = useCallback(async () => {
    const abortController = new AbortController();
    const { signal } = abortController;
    try {
      const success = await modelContext.deleteStream({ signal });
      if (success) {
        setLocation(uiRouteMap.listMps.url());
      }
    } catch (err) {
      appendMessage("danger", `Failed to delete stream - ${err}`);
    } finally {
      dialog.value = null;
    }
  }, [appendMessage, dialog, modelContext, setLocation]);

  return (
    <AllStreamsContext.Provider value={streamsContext}>
      <MultiPeriodModelContext.Provider value={modelContext}>
        <LoadingSuspense action="fetching stream information" error={error} loaded={loaded}>
          <Card header={header} id="edit_mps_form">
            <EditStreamForm name={name} newStream={newStream} />
          </Card>
          <TrackSelectionDialog onClose={closeDialog} />
          <ConfirmDeleteDialog onClose={closeDialog} onConfirm={confirmDeleteStream} />
          <OptionsDialog onClose={closeDialog} />
        </LoadingSuspense>
      </MultiPeriodModelContext.Provider>
    </AllStreamsContext.Provider>
  );
}
