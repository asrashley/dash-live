import { signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../test/renderWithProviders";
import { Input, InputProps } from "./Input";
import { FormInputItem } from "../types/FormInputItem";
import { SelectOptionType } from "../types/SelectOptionType";

import allManifests from '../test/fixtures/manifests.json';
import { InputFormData } from "../types/InputFormData";

describe("Input component", () => {
  const data = signal<InputFormData>({});
  const disabledFields = signal<Record<string, boolean>>({});
  const setValue = vi.fn();

  beforeEach(() => {
    disabledFields.value = {};
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

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
        },
      ],
    };
    const props: InputProps = {
      ...playbackMode,
      data,
      disabledFields,
      mode: 'cgi',
      setValue,
    };
    data.value = {
        mode: "vod",
    };
    disabledFields['mode__odvod'] = true;
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

  test('renders a Select input', async () => {
    const user = userEvent.setup();
    const names = [...Object.keys(allManifests)];
    names.sort();
    const selectManifest: FormInputItem = {
        name: "manifest",
        shortName: "manifest",
        fullName: "manifest",
        title: "Manifest",
        text: "Manifest template to use",
        type: "select",
        options: names.map((name) => {
          const msft = allManifests[name];
          return {
            title: msft.title,
            value: name,
          };
        }),
      };
      const props: InputProps = {
        ...selectManifest,
        mode: 'cgi',
        data,
        disabledFields,
        setValue,
      };
      data.value = {
        manifest: names[0],
      };
      const { getAllBySelector, getBySelector, asFragment } = renderWithProviders(
        <Input {...props} />
      );
      const elts = getAllBySelector('#model-manifest option');
      expect(elts.length).toEqual(selectManifest.options.length);
      selectManifest.options.forEach((opt: SelectOptionType, idx: number) => {
        const elt = elts[idx] as HTMLInputElement;
        expect(elt.value).toEqual(opt.value);
        expect(elt.innerHTML).toEqual(opt.title);
      });
      const input = getBySelector('#model-manifest');
      await user.selectOptions(input, [names[2]]);
      expect(setValue).toHaveBeenCalledTimes(1);
      expect(setValue).toHaveBeenCalledWith('manifest', names[2]);
      expect(asFragment()).toMatchSnapshot();
    });

    test('renders a MultiSelectInput', async () => {
        const user = userEvent.setup();
        const drmSystems = ['marlin', 'playready', 'clearkey'];
        const selectDrmSystem: FormInputItem = {
            name: "drms",
            shortName: "drms",
            fullName: "drms",
            title: "DRM systems",
            text: "DRM systems to enable for encrypted AdaptationSets",
            type: "multiselect",
            options: drmSystems.map(name => ({
                name,
                title: name,
                value: name,
            })),
        };
        const props: InputProps = {
            ...selectDrmSystem,
            mode: 'cgi',
            data,
            disabledFields,
            setValue,
        };
        data.value = {
            marlin: false,
            playready: true,
            clearkey: false,
        };
        const { getAllBySelector, getBySelector, getByTestId, asFragment } = renderWithProviders(<Input {...props} />);
        getByTestId('msi-drms');
        const elts = getAllBySelector('.form-check-input');
        expect(elts.length).toEqual(drmSystems.length);
        selectDrmSystem.options.forEach((opt: SelectOptionType, idx: number) => {
            const elt = elts[idx] as HTMLInputElement;
            expect(elt.name).toEqual(opt.name);
            expect(elt.checked).toEqual(data.value[opt.name]);
            const label = getBySelector(`label[for="${elt.getAttribute('id')}"]`);
            expect(label.innerHTML).toEqual(opt.title);
        });
        await user.click(elts[0]);
        expect(setValue).toHaveBeenCalledTimes(1);
        expect(setValue).toHaveBeenLastCalledWith(drmSystems[0], true);
        await user.click(elts[2]);
        expect(setValue).toHaveBeenCalledTimes(2);
        expect(setValue).toHaveBeenLastCalledWith(drmSystems[2], true);
        expect(asFragment()).toMatchSnapshot();
    });
});
