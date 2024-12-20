import { type JSX } from "preact";
import { useCallback, useContext } from "preact/hooks";
import { Signal, useComputed } from "@preact/signals";

import { ModalDialog } from "../../components/ModalDialog";
import { MultiPeriodModelContext } from "../../hooks/useMultiPeriodStream";
import { AppStateContext } from "../../appState";
import { MpsTrack } from "../../types/MpsTrack";
import { TrackPickerDialogState } from "../../types/DialogState";
import { MultiPeriodStream } from "../../types/MultiPeriodStream";
import { ContentRolesMap } from "../../types/ContentRolesMap";
import { DecoratedMpsTrack } from "../../types/DecoratedMpsTrack";
import { useContentRoles } from "../../hooks/useContentRoles";
import { StreamTrack } from "../../types/StreamTrack";

interface RoleSelectProps {
  name: string;
  roles: Signal<string[]>;
  value: string | number;
  onChange: (ev: JSX.TargetedEvent<HTMLSelectElement>) => void;
  className: string;
  disabled?: boolean;
}

function RoleSelect({
  name,
  roles,
  value,
  onChange,
  className,
  disabled,
}: RoleSelectProps) {
  return (
    <select
      className={className}
      name={name}
      value={value}
      onChange={onChange}
      disabled={disabled}
    >
      {roles.value.map((role) => (
        <option key={role} value={role}>
          {role}
        </option>
      ))}
    </select>
  );
}

function allowedTrackRoles(
  track: MpsTrack,
  contentRoles: Signal<ContentRolesMap>
): string[] {
  const roles: string[] = [];
  for (const [name, usage] of Object.entries(contentRoles.value)) {
    if (usage.includes(track.content_type)) {
      roles.push(name);
    }
  }
  return roles;
}

interface TrackSelectRowProps {
  contentRoles: Signal<ContentRolesMap>;
  track: DecoratedMpsTrack;
  onChange: (track: DecoratedMpsTrack) => void;
  guest?: boolean;
}

function TrackSelectRow({
  contentRoles,
  track,
  onChange,
  guest,
}: TrackSelectRowProps) {
  const roles = useComputed(() => allowedTrackRoles(track, contentRoles));
  const { track_id, enabled, encrypted, clearBitrates, encryptedBitrates } =
    track;
  const bitrates = encrypted ? encryptedBitrates : clearBitrates;
  const bitratesText = bitrates > 1 ? `, ${bitrates} bitrates` : "";
  const label = `${track.content_type} track ${track_id} (${track.codec_fourcc}${bitratesText})`;

  const onToggleEnabled = () => {
    if (guest) {
      return;
    }
    onChange({
      ...track,
      enabled: !enabled,
    });
  };

  const onToggleEncrypted = () => {
    if (guest) {
      return;
    }
    onChange({
      ...track,
      encrypted: !encrypted,
    });
  };

  const onRoleChange = (ev: Event) => {
    if (guest) {
      return;
    }
    onChange({
      ...track,
      role: (ev.target as HTMLInputElement).value,
    });
  };

  return (
    <div className="input-group mb-3 row border p-1">
      <div className="col-1">
        <input
          type="checkbox"
          class="form-check-input"
          id={`id_enable_${track_id}`}
          name={`enable_${track_id}`}
          checked={enabled}
          onClick={onToggleEnabled}
          disabled={guest}
        />
      </div>
      <label className="form-check-label col-6" for={`id_enable_${track_id}`}>
        {label}
      </label>
      <RoleSelect
        roles={roles}
        value={track.role}
        className="form-select col-3"
        disabled={guest}
        name={`role_${track_id}`}
        onChange={onRoleChange}
      />
      <div className="col-1">
        <input
          className="form-check-input"
          type="checkbox"
          checked={encrypted}
          name={`enc_${track_id}`}
          onClick={onToggleEncrypted}
          disabled={guest || encryptedBitrates === 0}
        />
      </div>
    </div>
  );
}

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
      $
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
