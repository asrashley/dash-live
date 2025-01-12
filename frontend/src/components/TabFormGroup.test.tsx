import { signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import {
  defaultCgiOptions,
  defaultFullOptions,
  defaultShortOptions,
  fieldGroups,
} from "../test/fixtures/options.js";

import { TabFormGroup } from "./TabFormGroup";
import { FormRowMode } from "../types/FormRowMode";
import { InputFormData } from "../types/InputFormData";

describe("TabFormGroup", () => {
  const data = signal<InputFormData>();
  const disabledFields = signal<Record<string, boolean>>({});
  const setValue = vi.fn();
  const formLayout = [3, 4, 5];
  const cgiData = {
    start: "month",
    timeline: "1",
    manifest: "hand_made.mpd",
    mode: "vod",
  };
  const fullData = {
    segmentTimeline: false,
    utcMethod: "iso",
  };
  const shortData = {
    ab: "1",
    patch: "1",
    utc: null,
  };

  beforeEach(() => {
    disabledFields.value  = {};
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test.each<FormRowMode>(["cgi", "shortName", "fullName"])(
    "matches snapshot when using mode %s",
    (mode: FormRowMode) => {
      switch (mode) {
        case "cgi":
          data.value = {
            ...defaultCgiOptions,
            ...cgiData,
          };
          break;
        case "shortName":
          data.value = {
            ...defaultShortOptions,
            ...shortData,
          };
          break;
        case "fullName":
          data.value = {
            ...defaultFullOptions,
            ...fullData,
          };
          break;
      }

      const { asFragment, getBySelector } = renderWithProviders(
        <TabFormGroup
          groups={fieldGroups}
          data={data}
          disabledFields={disabledFields}
          expand="general"
          mode={mode}
          setValue={setValue}
          layout={formLayout}
        />
      );
      for (const grp of fieldGroups) {
        for (const field of grp.fields) {
          let name =
            mode === "cgi"
              ? field.name
              : mode === "shortName"
              ? field.shortName
              : field.fullName;
          expect(name).toBeDefined();
          if (mode === 'fullName' && field.prefix) {
            name = `${field.prefix}__${name}`;
          }
          getBySelector(`input[name="${name}"], select[name="${name}"]`);
        }
      }
      expect(asFragment()).toMatchSnapshot();
    }
  );
});
