import { useComputed, type ReadonlySignal } from "@preact/signals";
import { ContentRolesMap } from "../../types/ContentRolesMap";
import { RoleSelect } from "./RoleSelect";
import { MpsTrack } from "../../types/MpsTrack";
import { DecoratedMpsTrack } from "../../types/DecoratedMpsTrack";

function allowedTrackRoles(
    track: MpsTrack,
    contentRoles: ReadonlySignal<ContentRolesMap>
  ): string[] {
    const roles: string[] = [];
    for (const [name, usage] of Object.entries(contentRoles.value)) {
      if (usage.includes(track.content_type)) {
        roles.push(name);
      }
    }
    return roles;
  }

  export interface TrackSelectRowProps {
    contentRoles: ReadonlySignal<ContentRolesMap>;
    track: DecoratedMpsTrack;
    onChange: (track: DecoratedMpsTrack) => void;
    guest?: boolean;
  }

  export function TrackSelectRow({
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
    const inputId: string = `id_enable_${track_id}`;

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
            id={inputId}
            name={`enable_${track_id}`}
            checked={enabled}
            onClick={onToggleEnabled}
            disabled={guest}
          />
        </div>
        <label className="form-check-label col-6" for={inputId}>
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

