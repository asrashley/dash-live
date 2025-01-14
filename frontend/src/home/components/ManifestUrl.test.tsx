import { signal } from "@preact/signals";
import { afterEach, describe, expect, test, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/renderWithProviders";

import { ManifestUrl } from "./ManifestUrl";

describe("ManifestUrl component", () => {
  const manifestUrl = signal<URL>();
  const editable = signal<boolean>(false);
  const setValue = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("shows manifest link", () => {
    manifestUrl.value = new URL(
      "/dash/live/netflix/manifest_e.mpd",
      document.location.href
    );
    editable.value = false;
    const { asFragment, getBySelector } = renderWithProviders(
      <ManifestUrl
        manifestUrl={manifestUrl}
        editable={editable}
        setValue={setValue}
      />
    );
    const inputElt = getBySelector('#id_mpd_url') as HTMLInputElement;
    const anchorElt = getBySelector('#dashurl');
    expect(inputElt.classList.contains('d-none')).toEqual(true);
    expect(anchorElt.classList.contains('d-none')).toEqual(false);
    expect(asFragment()).toMatchSnapshot();
  });

  test("allows manifest to be edited", async () => {
    const user = userEvent.setup();
    manifestUrl.value = new URL(
      "/dash/live/netflix/manifest_e.mpd",
      document.location.href
    );
    editable.value = true;
    const { asFragment, getBySelector } = renderWithProviders(
      <ManifestUrl
        manifestUrl={manifestUrl}
        editable={editable}
        setValue={setValue}
      />
    );
    const inputElt = getBySelector('#id_mpd_url') as HTMLInputElement;
    const anchorElt = getBySelector('#dashurl');
    expect(inputElt.classList.contains('d-none')).toEqual(false);
    expect(anchorElt.classList.contains('d-none')).toEqual(true);
    expect(inputElt.value).toEqual(manifestUrl.value.href);
    await user.click(inputElt);
    await user.type(inputElt, "?abr=0{enter}");
    expect(inputElt.value).toEqual(`${manifestUrl.value.href}?abr=0`);
    expect(setValue).toHaveBeenCalledTimes(1);
    expect(setValue).toHaveBeenCalledWith(inputElt.value);
    expect(asFragment()).toMatchSnapshot();
  });
});
