import { afterEach, describe, expect, test, vi } from "vitest";
import { mock } from "vitest-mock-extended";

import { OptionsDialog } from "./OptionsDialog";
import { renderWithProviders } from "../../test/renderWithProviders";
import {
  MultiPeriodModelContext,
  type UseMultiPeriodStreamHook,
} from "../../hooks/useMultiPeriodStream";
import { AppStateType, createAppState } from "../../appState";
import { MpsOptionsDialogState } from "../../types/DialogState";
import { fieldGroups } from "../../test/fixtures/options.js";

describe("OptionsDialog component", () => {
  const onClose = vi.fn();
  const useMpsHookMock = mock<UseMultiPeriodStreamHook>();
  const shortData = {
    ab: "1",
    patch: "1",
    utc: null,
  };
  const mpsOptions: MpsOptionsDialogState = {
    options: {
      ...shortData,
    },
    lastModified: 123,
    name: "OptionsDialog",
  };
  const excludeFields = new Set([
    'acodec', 'ad_audio', 'main_audio', 'main_text',
    'player', 'tcodec', 'tlang'
  ]);


  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", () => {
    const state: AppStateType = createAppState();
    state.dialog.value = {
      backdrop: true,
      mpsOptions,
    };
    const { asFragment, getBySelector } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={useMpsHookMock}>
        <OptionsDialog onClose={onClose} />
      </MultiPeriodModelContext.Provider>,
      { appState: state }
    );
    for (const grp of fieldGroups) {
      for (const field of grp.fields) {
        if (excludeFields.has(field.name)) {
            continue;
        }
        expect(field.shortName).toBeDefined();
        getBySelector(
          `input[name="${field.shortName}"], select[name="${field.shortName}"]`
        );
      }
    }
    expect(asFragment()).toMatchSnapshot();
  });
});
