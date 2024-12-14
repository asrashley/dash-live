import { html } from "htm/preact";
import { useCallback, useContext, useMemo } from "preact/hooks";
import { useComputed } from "@preact/signals";
import { ContentRoles } from "/libs/content_roles.js";

import { ModalDialog } from "@dashlive/ui";
import { MultiPeriodModelContext } from "@dashlive/hooks";
import { AppStateContext } from "../../appState.js";

function RoleSelect({ name, roles, value, onChange, className, disabled }) {
  return html`<select
    className=${className}
    name=${name}
    value=${value}
    onChange=${onChange}
    disabled=${disabled}
  >
    ${roles.map((role) => html`<option value="${role}">${role}</option>`)}
  </select>`;
}

function allowedTrackRoles(track) {
  const roles = [];
  for (const [name, usage] of Object.entries(ContentRoles)) {
    if (usage.includes(track.content_type)) {
      roles.push(name);
    }
  }
  return roles;
}

function TrackSelectRow({ track, onChange, guest }) {
  const roles = useMemo(() => allowedTrackRoles(track), [track]);
  const { track_id, enabled, encrypted, clearBitrates, encryptedBitrates } = track;
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

  const onRoleChange = (ev) => {
    if (guest) {
      return;
    }
    onChange({
      ...track,
      role: ev.target.value,
    });
  };

  return html` <div class="input-group mb-3 row border p-1">
    <div class="col-1"><input
      type="checkbox"
      class="form-check-input"
      id="id_enable_${track_id}"
      name="enable_${track_id}"
      checked=${enabled}
      onClick=${onToggleEnabled}
      disabled=${guest}
    /></div>
    <label class="form-check-label col-6" for="id_enable_${track_id}">${label}</label>
    <${RoleSelect}
      roles=${roles}
      value=${track.role}
      className="form-select col-3"
      disabled=${guest}
      name="role_${track_id}"
      onChange=${onRoleChange}
    />
    <div class="col-1"><input
      class="form-check-input"
      type="checkbox"
      checked=${encrypted}
      name="enc_${track_id}"
      onClick=${onToggleEncrypted}
      disabled=${guest || encryptedBitrates === 0}
    /></div>
  </div>`;
}

function generateMediaTracks(trackPicker, model) {
  if (!trackPicker.value || !model.value) {
    return [];
  }
  const { pk, stream } = trackPicker.value;
  const { periods = [] } = model.value;
  const prd = periods.find((p) => p.pk === pk);
  return stream.tracks.map(stk => {
    const trk = prd?.tracks.find(t => t.track_id === stk.track_id);
    return {
      enabled: trk !== undefined,
      ...stk,
      ...trk,
    };
  });
}

export function TrackSelectionDialog({ onClose }) {
  const { model, modifyPeriod } = useContext(MultiPeriodModelContext);
  const { dialog } = useContext(AppStateContext);
  const trackPicker = useComputed(() => dialog.value?.trackPicker);
  const mediaTracks = useComputed(() =>
    generateMediaTracks(trackPicker, model)
  );
  const allSelected = useComputed(() => {
    return !mediaTracks.value.some((trk) => !trk.enabled);
  });
  const title = useComputed(
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
    const newTracks = mediaTracks.value.map(trk => ({
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

  return html`
<${ModalDialog} onClose=${onClose} title="${title.value}" size='lg'>
  <div class="row fw-bold">
    <div class="col-1">
      <input class="form-check-input" data-testid="select-all-tracks" type="checkbox" disabled=${guest}
        name="all_tracks" checked=${allSelected.value} onClick=${selectAllTracks} />
    </div>
    <div class="col-6 text-center">Track</div>
    <div class="col-3 text-center">Role</div>
    <div class="col-2 text-end">Encrypted</div>
  </div>
  ${mediaTracks.value.map(
    (trk) => html` <${TrackSelectRow}
      track=${trk}
      guest=${guest}
      onChange=${updateTrack}
    />`
  )}
</${ModalDialog}>`;
}
