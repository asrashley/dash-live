import { signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/renderWithProviders";
import { Input } from "./Input";
import { StaticInputProps } from "../types/StaticInputProps";
import { SelectOptionType } from "../types/SelectOptionType";
import { InputFormData } from "../types/InputFormData";
import { InputProps } from "../types/InputProps";

import allManifests from '../../test/fixtures/manifests.json';

describe("Input component", () => {
  const data = signal<InputFormData>({});
  const disabledFields = signal<Record<string, boolean>>({});
  const error = signal<string|undefined>();
  const setValue = vi.fn();

  beforeEach(() => {
    disabledFields.value = {};
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders a Radio button", () => {
    const playbackMode: StaticInputProps = {
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
      error,
      mode: 'cgi',
      setValue,
    };
    data.value = {
        mode: "vod",
    };
    disabledFields.value = {
      mode__odvod: true,
    };
    const { getAllBySelector, getBySelector, getByLabelText, asFragment } = renderWithProviders(
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
    const opt = getByLabelText(playbackMode.options[2].title) as HTMLInputElement;
    expect(opt.value).toEqual('odvod');
    expect(opt.disabled).toEqual(true);
    expect(asFragment()).toMatchSnapshot();
  });

  test.each([true, false])('renders a Select input disabled=%s', async (disabled: boolean) => {
    const user = userEvent.setup();
    const names = [...Object.keys(allManifests)];
    names.sort();
    const selectManifest: StaticInputProps = {
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
        error,
        setValue,
      };
      data.value = {
        manifest: names[0],
      };
      disabledFields.value = {
        manifest: disabled,
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
      const input = getBySelector('#model-manifest') as HTMLSelectElement;
      expect(input.disabled).toEqual(disabled);
      await user.selectOptions(input, [names[2]]);
      if (disabled) {
        expect(setValue).not.toHaveBeenCalled();
      } else {
        expect(setValue).toHaveBeenCalledTimes(1);
        expect(setValue).toHaveBeenCalledWith('manifest', names[2]);
      }
      expect(asFragment()).toMatchSnapshot();
    });

    test('renders a MultiSelectInput', async () => {
        const user = userEvent.setup();
        const drmSystems = ['marlin', 'playready', 'clearkey'];
        const selectDrmSystem: StaticInputProps = {
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
            error,
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

    test.each(['text', 'email', 'password'])('renders a %s input', async (type: StaticInputProps["type"]) => {
      const user = userEvent.setup();
      const inp: StaticInputProps = {
        name: "test",
        shortName: "tst",
        fullName: "inputTest",
        text: `test of input type ${type}`,
        title: "Input title",
        placeholder: 'placeholder text',
        type,
      };
      const props: InputProps = {
        ...inp,
        mode: 'cgi',
        data,
        disabledFields,
        error,
        setValue,
      };
      data.value = {
        test: 'input-value',
      };
      const { getBySelector } = renderWithProviders(<Input {...props} />);
      const elt = getBySelector(`input[type="${type}"]`) as HTMLInputElement;
      expect(elt.getAttribute('placeholder')).toEqual(inp.placeholder);
      expect(elt.value).toEqual(data.value.test);
      await user.clear(elt);
      await user.type(elt, 'new.value');
      expect(setValue).toHaveBeenCalledWith('test', 'new.value');
    });
});
