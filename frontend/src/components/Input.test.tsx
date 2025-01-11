import { signal } from "@preact/signals";
import { describe, expect, test, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";

import { Input, InputProps } from "./Input";
import { FormInputItem } from "../types/FormInputItem";
import { SelectOptionType } from "../types/SelectOptionType";

describe("Input component", () => {
  const value = signal<number | string | boolean>("");
  const setValue = vi.fn();

  test("renders a Radio button", () => {
    const playbackMode: FormInputItem = {
      name: "mode",
      shortName: "mode",
      fullName: "playbackMode",
      title: "Playback Mode",
      type: "radio",
      options: [
        {
          title: "Video On Demand (using live profile)",
          value: "vod",
        },
        {
          title: "Live stream (using live profile)",
          value: "live",
        },
        {
          title: "Video On Demand (using on-demand profile)",
          value: "odvod",
          disabled: true,
        },
      ],
    };

    const props: InputProps = {
      ...playbackMode,
      value,
      setValue,
    };
    value.value = "vod";
    const { getAllBySelector, getBySelector, asFragment } = renderWithProviders(
      <Input {...props} />
    );
    const elts = getAllBySelector('input[type="radio"]');
    expect(elts.length).toEqual(playbackMode.options.length);
    playbackMode.options.forEach((opt: SelectOptionType, idx: number) => {
      const elt = elts[idx] as HTMLInputElement;
      expect(elt.value).toEqual(opt.value);
      expect(elt.name).toEqual(playbackMode.name);
      expect(elt.getAttribute("id")).toEqual(`radio-mode-${opt.value}`);
      const label = getBySelector(`label[for="radio-mode-${opt.value}"]`);
      expect(label.innerHTML).toEqual(opt.title);
    });
    expect(asFragment()).toMatchSnapshot();
  });
});
