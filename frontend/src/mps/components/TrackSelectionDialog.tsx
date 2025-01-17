import { useCallback, useContext } from "preact/hooks";
import { Signal, useComputed } from "@preact/signals";

import { ModalDialog } from "../../components/ModalDialog";
import { MultiPeriodModelContext } from "../../hooks/useMultiPeriodStream";
import { AppStateContext } from "../../appState";
import { MpsTrack } from "../../types/MpsTrack";
import { TrackPickerDialogState } from "../../types/DialogState";
import { MultiPeriodStream } from "../../types/MultiPeriodStream";
import { DecoratedMpsTrack } from "../../types/DecoratedMpsTrack";
import { useContentRoles } from "../../hooks/useContentRoles";
import { StreamTrack } from "../../types/StreamTrack";
import { TrackSelectRow } from "./TrackSelectRow";

function generateMediaTracks(
  trackPicker: Signal<TrackPickerDialogState | undefined>,
  model: Signal<MultiPeriodStream>
): DecoratedMpsTrack[] {
  if (!trackPicker.value || !model.value) {
    return [];
  }
  const { pk, stream } = trackPicker.value;
  const { periods = [] } = model.value;
  const prd = periods.find((p) => p.pk === pk);
  return stream.tracks.map((stk: StreamTrack) => {
    const trk: MpsTrack | undefined = prd?.tracks.find((t: MpsTrack) => t.track_id === stk.track_id);
    return {
      enabled: trk !== undefined,
      ...stk,
      ...trk,
    };
  });
}

export interface TrackSelectionDialogProps {
  onClose: () => void;
}

export function TrackSelectionDialog({ onClose }: TrackSelectionDialogProps) {
  const { model, modifyPeriod } = useContext(MultiPeriodModelContext);
  const { dialog } = useContext(AppStateContext);
  const { contentRoles } = useContentRoles();
  const trackPicker = useComputed<TrackPickerDialogState | undefined>(
    () => dialog.value?.trackPicker
  );
  const mediaTracks = useComputed(() =>
    generateMediaTracks(trackPicker, model)
  );
  const allSelected = useComputed<boolean>(() => {
    return !mediaTracks.value.some((trk) => !trk.enabled);
  });
  const title = useComputed<string>(
    () =>
      `${trackPicker.value?.guest ? "" : "Choose "}tracks for Period "${
        trackPicker.value?.pid
      }"`
  );

  const updateTrack = useCallback(
    (track) => {
      if (!trackPicker.value) {
        return;
      }
      modifyPeriod({
        periodPk: trackPicker.value.pk,
        track,
      });
    },
    [trackPicker.value, modifyPeriod]
  );

  const selectAllTracks = useCallback(() => {
    const newTracks = mediaTracks.value.map((trk) => ({
      ...trk,
      enabled: !allSelected.value,
    }));
    newTracks.forEach((trk) => {
      modifyPeriod({
        periodPk: trackPicker.value.pk,
        track: trk,
      });
    });
  }, [allSelected, mediaTracks, modifyPeriod, trackPicker]);

  if (!trackPicker.value) {
    return null;
  }

  const { guest = false } = trackPicker.value;

  return (
    <ModalDialog onClose={onClose} title={title.value} size="lg">
      <div className="row fw-bold">
        <div className="col-1">
          <input
            className="form-check-input"
            data-testid="select-all-tracks"
            type="checkbox"
            disabled={guest}
            name="all_tracks"
            checked={allSelected.value}
            onClick={selectAllTracks}
          />
        </div>
        <div className="col-6 text-center">Track</div>
        <div className="col-3 text-center">Role</div>
        <div className="col-2 text-end">Encrypted</div>
      </div>
      {mediaTracks.value.map((trk) => (
        <TrackSelectRow
          key={trk.pk}
          track={trk}
          guest={guest}
          contentRoles={contentRoles}
          onChange={updateTrack}
        />
      ))}
    </ModalDialog>
  );
}
