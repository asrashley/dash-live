import { afterEach, describe, expect, test, vi } from "vitest";
import { signal } from "@preact/signals-core";
import userEvent from "@testing-library/user-event";

import { ContentRolesMap } from "../../types/ContentRolesMap";
import { DecoratedMpsTrack } from "../../types/DecoratedMpsTrack";
import { renderWithProviders } from "../../test/renderWithProviders";
import { TrackSelectRow } from "./TrackSelectRow";

import rolesMap from "../../test/fixtures/content_roles.json";
import { fireEvent } from "@testing-library/preact";

describe("TrackSelectRow component", () => {
  const contentRoles = signal<ContentRolesMap>(rolesMap);
  const track: DecoratedMpsTrack = {
    codec_fourcc: "avc1",
    content_type: "video",
    lang: null,
    pk: 456,
    track_id: 1,
    role: "main",
    enabled: true,
    encrypted: false,
    clearBitrates: 3,
    encryptedBitrates: 2,
  };
  const onChange = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  test.each<[boolean, boolean]>([
    [false, false],
    [false, true],
    [true, false],
    [true, true],
  ])("renders row when guest=%s encrypted=%s", (guest: boolean, encrypted: boolean) => {
    const trk = {
        ...track,
        encrypted,
    };
    const { asFragment } = renderWithProviders(
      <TrackSelectRow
        contentRoles={contentRoles}
        track={trk}
        guest={guest}
        onChange={onChange}
      />
    );
    expect(asFragment()).toMatchSnapshot();
  });

  test.each([true, false])("toggle encryption, guest=%s", (guest: boolean) => {
    const { getBySelector } = renderWithProviders(
      <TrackSelectRow
        contentRoles={contentRoles}
        track={track}
        guest={guest}
        onChange={onChange}
      />
    );
    const inp = getBySelector('input[name="enc_1"]') as HTMLInputElement;
    fireEvent.click(inp);
    if (guest) {
      expect(onChange).not.toHaveBeenCalled();
    } else {
      expect(onChange).toHaveBeenCalledTimes(1);
      expect(onChange).toHaveBeenCalledWith({
        ...track,
        encrypted: true,
      });
    }
  });

  test.each([true, false])("toggle enabled, guest=%s", (guest: boolean) => {
    const { getBySelector } = renderWithProviders(
      <TrackSelectRow
        contentRoles={contentRoles}
        track={track}
        guest={guest}
        onChange={onChange}
      />
    );
    const inp = getBySelector('input[name="enable_1"]') as HTMLInputElement;
    fireEvent.click(inp);
    if (guest) {
      expect(onChange).not.toHaveBeenCalled();
    } else {
      expect(onChange).toHaveBeenCalledTimes(1);
      expect(onChange).toHaveBeenCalledWith({
        ...track,
        enabled: false,
      });
    }
  });

  test.each([true, false])("change role guest=%s", async (guest: boolean) => {
    const user = userEvent.setup();
    const { getBySelector } = renderWithProviders(
      <TrackSelectRow
        contentRoles={contentRoles}
        track={track}
        guest={guest}
        onChange={onChange}
      />
    );
    const inp = getBySelector('select[name="role_1"]') as HTMLSelectElement;
    await user.selectOptions(inp, ["alternate"]);
    if (guest) {
      expect(onChange).not.toHaveBeenCalled();
      expect(inp.disabled).toEqual(true);
    } else {
      expect(onChange).toHaveBeenCalledTimes(1);
      expect(onChange).toHaveBeenCalledWith({
        ...track,
        role: "alternate",
      });
    }
  });
});
