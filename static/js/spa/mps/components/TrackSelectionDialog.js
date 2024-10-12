import { html } from 'htm/preact';
import { useCallback, useContext, useMemo } from 'preact/hooks';
import { useComputed } from "@preact/signals";
import { ContentRoles } from '/libs/content_roles.js';

import { CheckBox } from '../../components/CheckBox.js';
import { ModalDialog } from '../../components/ModalDialog.js';
import { AppStateContext } from '../../appState.js';
import { PageStateContext, modifyModel } from '../state.js';

function RoleSelect({roles, value, onChange}) {
  return html`
<select class="form-select col-4" value=${ value } onChange=${onChange} >
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

function TrackCheckBox({track, onChange}) {
  const roles = useMemo(() => allowedTrackRoles(track), [track]);
  const bitrates = track.bitrates > 1 ? `, ${track.bitrates} bitrates` : '';
  const label = `${track.content_type} track ${track.track_id} (${track.codec_fourcc}${bitrates})`;

  const onToggle = () => {
    onChange({
      ...track,
      enabled: !track.enabled,
    });
  };

  const onRoleChange = (ev) => {
    onChange({
      ...track,
      role: ev.target.value,
    });
  };

  return html`
<div class="input-group mb-3 row border p-1">
    <${CheckBox} checked=${track.enabled} name="track_${track.track_id}"
       label="${label}" onClick=${onToggle} />
    <${RoleSelect} roles=${roles} value=${track.role}
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
  const { model, streamsMap, modified } = useContext(PageStateContext);
  const { dialog } = useContext(AppStateContext);
  const trackPicker = useComputed(() => dialog.value?.trackPicker);
  const mediaTracks = useComputed(() => generateMediaTracks(
    trackPicker, model, streamsMap));
  const allSelected = useComputed(() => {
    return !mediaTracks.value.some(trk => !trk.enabled);
  });
  const title = useComputed(
    () => `Choose tracks for Period "${ trackPicker.value?.pid }"`);

  const onClose = useCallback(() => {
    dialog.value = null;
  }, [dialog]);

  const updateTrack = useCallback((track) => {
    if (!trackPicker.value) {
      return;
    }
    model.value = modifyModel({
      model: model.value,
      periodPk: trackPicker.value.pk,
      track,
    });
    modified.value = true;
  }, [trackPicker, model, modified]);

  const selectAllTracks = useCallback(() => {
    mediaTracks.value.forEach(trk => {
      updateTrack({
        ...trk,
        enabled: !allSelected.value,
      });
    });
    modified.value = true;
  }, [allSelected, mediaTracks, modified, updateTrack]);

  if (!trackPicker.value) {
    return null;
  }

  return html`
<${ModalDialog} onClose=${onClose} title="${title.value}" size='lg'>
  <div class="row fw-bold">
    <input class="form-check-input col-2" type="checkbox"
      name="all_tracks" checked=${allSelected.value} onClick=${selectAllTracks} />
    <div class="col-6 text-center">Track</div>
    <div class="col-4 text-center">Role</div>
  </div>
  ${mediaTracks.value.map(trk => html`
    <${TrackCheckBox} track=${trk} onChange=${updateTrack}/>`)}
</${ModalDialog}>`;
}
