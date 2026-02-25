import { afterEach, describe, expect, test, vi } from "vitest";
import { mock, mockReset } from "vitest-mock-extended";
import userEvent from "@testing-library/user-event";

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
  const excludeFields: Set<string> = new Set([
    'acodec', 'ad_audio', 'main_audio', 'main_text',
    'player', 'tcodec', 'tlang'
  ]);


  afterEach(() => {
    vi.clearAllMocks();
    mockReset(useMpsHookMock);
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

  test("renders nothing when dialog is not active", () => {
    const state: AppStateType = createAppState();
    state.dialog.value = { backdrop: true };

    const { container } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={useMpsHookMock}>
        <OptionsDialog onClose={onClose} />
      </MultiPeriodModelContext.Provider>,
      { appState: state }
    );

    expect(container.firstChild).toBeNull();
  });

  test("calls onClose when Discard Changes is clicked", async () => {
    const user = userEvent.setup();

    const state: AppStateType = createAppState();
    state.dialog.value = {
      backdrop: true,
      mpsOptions,
    };

    const { getByText } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={useMpsHookMock}>
        <OptionsDialog onClose={onClose} />
      </MultiPeriodModelContext.Provider>,
      { appState: state }
    );

    const btn = getByText("Discard Changes") as HTMLButtonElement;
    await user.click(btn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("saves empty options when current values match defaults", async () => {
    const user = userEvent.setup();

    const state: AppStateType = createAppState();
    state.dialog.value = {
      backdrop: true,
      mpsOptions: {
        options: {},
        lastModified: 456,
        name: "OptionsDialog",
      },
    };

    const { getByText } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={useMpsHookMock}>
        <OptionsDialog onClose={onClose} />
      </MultiPeriodModelContext.Provider>,
      { appState: state }
    );

    await user.click(getByText("Save Changes") as HTMLButtonElement);

    expect(useMpsHookMock.setFields).toHaveBeenCalledTimes(1);
    expect(useMpsHookMock.setFields).toHaveBeenCalledWith({ options: {} });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("prevents default form submit and does not save/close", () => {
    const state: AppStateType = createAppState();
    state.dialog.value = {
      backdrop: true,
      mpsOptions: {
        options: {},
        lastModified: 900,
        name: "OptionsDialog",
      },
    };

    const { getBySelector } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={useMpsHookMock}>
        <OptionsDialog onClose={onClose} />
      </MultiPeriodModelContext.Provider>,
      { appState: state }
    );

    const form = getBySelector(`form[name="mpsOptions"]`) as HTMLFormElement;
    const submitEvent = new Event("submit", { bubbles: true, cancelable: true });
    const dispatchResult = form.dispatchEvent(submitEvent);

    expect(dispatchResult).toBe(false);
    expect(submitEvent.defaultPrevented).toBe(true);
    expect(useMpsHookMock.setFields).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  test("submitting the form after edits still does not persist until Save Changes is clicked", async () => {
    const user = userEvent.setup();
    const state: AppStateType = createAppState();
    state.dialog.value = {
      backdrop: true,
      mpsOptions: {
        options: {},
        lastModified: 901,
        name: "OptionsDialog",
      },
    };

    const { getBySelector, getByText, getByLabelText } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={useMpsHookMock}>
        <OptionsDialog onClose={onClose} />
      </MultiPeriodModelContext.Provider>,
      { appState: state }
    );

    const abControl = getByLabelText("Adaptive bitrate:") as HTMLInputElement | HTMLSelectElement;
    await user.click(abControl);

    const astControl = getByLabelText("Availability start time:") as HTMLInputElement | HTMLSelectElement;
    await user.clear(astControl);
    await user.type(astControl, "month");

    const form = getBySelector(`form[name="mpsOptions"]`) as HTMLFormElement;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    expect(useMpsHookMock.setFields).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();

    const saveBtn = getByText("Save Changes") as HTMLButtonElement;
    await user.click(saveBtn);

    expect(useMpsHookMock.setFields).toHaveBeenCalledTimes(1);
    expect(useMpsHookMock.setFields).toHaveBeenCalledWith({
      options: expect.objectContaining({
         ab: false,
         ast: "month",
      }),
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
