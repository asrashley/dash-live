import { useCallback, useContext } from "preact/hooks";

import { Card } from "../../components/Card";
import { ConfirmDeleteDialog } from './ConfirmDeleteDialog';
import { TrackSelectionDialog } from './TrackSelectionDialog';
import { OptionsDialog } from './OptionsDialog';

import { AppStateContext } from "../../appState";
import { AllStreamsContext, useAllStreams  } from "../../hooks/useAllStreams";
import { useMultiPeriodStream, MultiPeriodModelContext } from "../../hooks/useMultiPeriodStream";
import { EditStreamForm } from "./EditStreamForm";

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
