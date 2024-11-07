import { html } from 'htm/preact';
import { useCallback, useContext, useMemo } from 'preact/hooks';
import { useComputed } from "@preact/signals";
import { ContentRoles } from '/libs/content_roles.js';

import { CheckBox, ModalDialog } from '@dashlive/ui';
import { AllStreamsContext, MultiPeriodModelContext } from '@dashlive/hooks';
import { AppStateContext } from '../../appState.js';

function RoleSelect({roles, value, onChange, disabled}) {
  return html`
<select class="form-select col-4" value=${ value } onChange=${onChange}
  disabled=${disabled} >
  ${ roles.map(role => html`<option value="${role}">${role}</option>`) }
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

function TrackCheckBox({track, onChange, guest}) {
  const roles = useMemo(() => allowedTrackRoles(track), [track]);
  const bitrates = track.bitrates > 1 ? `, ${track.bitrates} bitrates` : '';
  const label = `${track.content_type} track ${track.track_id} (${track.codec_fourcc}${bitrates})`;

  const onToggle = () => {
    if (guest) {
      return;
    }
    onChange({
      ...track,
      enabled: !track.enabled,
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

  return html`
<div class="input-group mb-3 row border p-1">
    <${CheckBox} checked=${track.enabled} name="track_${track.track_id}"
       label="${label}" onClick=${onToggle} disabled=${guest} />
    <${RoleSelect} roles=${roles} value=${track.role} disabled=${guest}
      name="role_${track.track_id}" onChange=${onRoleChange} />
</div>`;
}

function generateMediaTracks(trackPicker, model, streamsMap) {
  if (!trackPicker.value || !model.value || !streamsMap.value) {
    return [];
  }
  const { pk } = trackPicker.value;
  const { periods=[] } = model.value;
  const prd = periods.find(p => p.pk === pk);
  if (!prd) {
    return [];
  }

  const stream = streamsMap.value.get(prd.stream);
  if (stream === undefined) {
    return [];
  }

  const tracks = Object.fromEntries(
    stream.tracks.map(s => ([s.track_id, {
      ...s,
      role: 'main',
      enabled: false,
    }])));

  for (const [tid, role] of Object.entries(prd.tracks)) {
    tracks[tid] = {
      ...tracks[tid],
      role,
      enabled: true,
    };
  }
  const trackIds = [...Object.keys(tracks)];
  trackIds.sort();
  return trackIds.map(id => tracks[id]);
}

export function TrackSelectionDialog() {
  const { model, modifyPeriod } = useContext(MultiPeriodModelContext);
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
  const trackPicker = useComputed(() => dialog.value?.trackPicker);
  const mediaTracks = useComputed(() => generateMediaTracks(
    trackPicker, model, streamsMap));
  const allSelected = useComputed(() => {
    return !mediaTracks.value.some(trk => !trk.enabled);
  });
  const title = useComputed(
    () => `${trackPicker.value?.guest ? '' : 'Choose '}tracks for Period "${ trackPicker.value?.pid }"`);

  const onClose = useCallback(() => {
    dialog.value = null;
  }, [dialog]);

  const updateTrack = useCallback((track) => {
    if (!trackPicker.value) {
      return;
    }
    modifyPeriod({
      periodPk: trackPicker.value.pk,
      track,
    });
  }, [trackPicker.value, modifyPeriod]);

  const selectAllTracks = useCallback(() => {
    mediaTracks.value.forEach(trk => {
      updateTrack({
        ...trk,
        enabled: !allSelected.value,
      });
    });
  }, [allSelected, mediaTracks, updateTrack]);

  if (!trackPicker.value) {
    return null;
  }

  const {guest=false} = trackPicker.value;

  return html`
<${ModalDialog} onClose=${onClose} title="${title.value}" size='lg'>
  <div class="row fw-bold">
    <input class="form-check-input col-2" type="checkbox" disabled=${guest}
      name="all_tracks" checked=${allSelected.value} onClick=${selectAllTracks} />
    <div class="col-6 text-center">Track</div>
    <div class="col-4 text-center">Role</div>
  </div>
  ${mediaTracks.value.map(trk => html`
    <${TrackCheckBox} track=${trk} guest=${guest} onChange=${updateTrack}/>`)}
</${ModalDialog}>`;
}
