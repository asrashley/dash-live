import { signal } from "@preact/signals";
import { afterEach, describe, expect, test, vi } from "vitest";

import { AccordionFormGroup } from "./AccordionFormGroup";
import { FormRowMode } from "../types/FormRowMode";
import { renderWithProviders } from "../test/renderWithProviders";
import {
  defaultCgiOptions,
  defaultFullOptions,
  defaultShortOptions,
  fieldGroups,
} from "../test/fixtures/options.js";

describe("AccordionFormGroup", () => {
  const data = signal();
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
        <AccordionFormGroup
          groups={fieldGroups}
          data={data}
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
          if (name === undefined) {
            console.log(JSON.stringify(field));
          }
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
