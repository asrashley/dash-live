import { signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import {
  renderWithProviders,
  RenderWithProvidersProps,
  RenderWithProvidersResult,
} from "../../test/renderWithProviders";
import { ValidatorForm, ValidatorFormProps } from "./ValidatorForm";
import { ValidatorSettings } from "../types/ValidatorSettings";
import { blankSettings } from "./ValidatorPage";
import { act } from "@testing-library/preact";
import { ValidatorState } from "../hooks/useValidatorWebsocket";
import { mediaUser, normalUser } from "../../test/MockServer";
import { InitialUserState } from "../../types/UserState";

type ValidatorFormRenderResult = RenderWithProvidersResult & {
  manifestElt: HTMLInputElement;
  destinationElt: HTMLInputElement;
  durationElt: HTMLInputElement;
  encryptedElt: HTMLInputElement;
  saveElt: HTMLInputElement;
  titleElt: HTMLInputElement;
  startBtn: HTMLButtonElement;
  cancelBtn: HTMLButtonElement;
};

function renderForm(
  uiProps: ValidatorFormProps,
  renderProps: Partial<RenderWithProvidersProps> = {}
): ValidatorFormRenderResult {
  const renderRes = renderWithProviders(
    <ValidatorForm {...uiProps} />,
    renderProps
  );
  const { getByText, getByLabelText } = renderRes;

  return {
    ...renderRes,
    manifestElt: getByLabelText("Manifest to check:") as HTMLInputElement,
    durationElt: getByLabelText("Maximum duration:") as HTMLInputElement,
    encryptedElt: getByLabelText("Stream is encrypted?") as HTMLInputElement,
    destinationElt: getByLabelText(
      "Destination directory:"
    ) as HTMLInputElement,
    titleElt: getByLabelText("Stream title:") as HTMLInputElement,
    saveElt: getByLabelText("Add stream to this server?") as HTMLInputElement,
    startBtn: getByText("Validate DASH stream") as HTMLButtonElement,
    cancelBtn: getByText("Cancel") as HTMLButtonElement,
  } as unknown as ValidatorFormRenderResult;
}

describe("ValidatorForm component", () => {
  const data = signal<ValidatorSettings>(blankSettings);
  const state = signal<ValidatorState>(ValidatorState.IDLE);
  const setValue = vi.fn();
  const start = vi.fn();
  const cancel = vi.fn();
  const manifest = "http://localhost:8765/dash/vod/bbb/hand_made.mpd";
  const prefix = "prefix";
  const title = "demo stream title";

  beforeEach(() => {
    data.value = structuredClone(blankSettings);
    setValue.mockImplementation((field, value) => {
      data.value = {
        ...data.value,
        [field]: value,
      };
    });
    state.value = ValidatorState.IDLE;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders initial form", () => {
    const { getByText, startBtn, cancelBtn } = renderForm({
      data,
      state,
      setValue,
      start,
      cancel,
    });
    getByText("Manifest to check", { exact: false });
    getByText("manifest URL is required");
    expect(startBtn.disabled).toEqual(true);
    expect(cancelBtn.disabled).toEqual(true);
  });

  test("can cancel", async () => {
    const userEv = userEvent.setup();
    const { manifestElt, startBtn, cancelBtn } = renderForm({
      data,
      state,
      setValue,
      start,
      cancel,
    });
    await userEv.click(manifestElt);
    await userEv.clear(manifestElt);
    await userEv.type(manifestElt, manifest);
    expect(startBtn.disabled).toEqual(false);
    expect(cancelBtn.disabled).toEqual(true);
    await userEv.click(startBtn);
    act(() => {
      state.value = ValidatorState.ACTIVE;
    });
    expect(cancelBtn.disabled).toEqual(false);
    await userEv.click(cancelBtn);
    expect(start).toHaveBeenCalledTimes(1);
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  test.each([undefined, normalUser, mediaUser])(
    "can set values as user $username",
    async (user?: InitialUserState) => {
      const userEv = userEvent.setup();
      const {
        manifestElt,
        durationElt,
        saveElt,
        destinationElt,
        startBtn,
        titleElt,
        cancelBtn,
        getByText,
      } = renderForm(
        { data, state, setValue, start, cancel },
        { userInfo: user }
      );
      await userEv.click(manifestElt);
      await userEv.clear(manifestElt);
      await userEv.type(manifestElt, manifest);
      await userEv.click(durationElt);
      await userEv.clear(durationElt);
      await userEv.type(durationElt, "12");
      expect(startBtn.disabled).toEqual(false);
      expect(cancelBtn.disabled).toEqual(true);
      if (user?.groups.includes("MEDIA")) {
        await userEv.click(saveElt);
        expect(startBtn.disabled).toEqual(true);
        getByText("a directory name is required");
        await userEv.click(destinationElt);
        await userEv.clear(destinationElt);
        await userEv.type(destinationElt, prefix);
        getByText("a title is required");
        await userEv.click(titleElt);
        await userEv.clear(titleElt);
        await userEv.type(titleElt, title);
        expect(startBtn.disabled).toEqual(false);
      }
      await userEv.click(startBtn);
      expect(start).toHaveBeenCalledTimes(1);
      if (user?.groups.includes("MEDIA")) {
        expect(start).toHaveBeenCalledWith({
          ...blankSettings,
          manifest,
          prefix,
          title,
          duration: 12,
          save: true,
        });
      } else {
        expect(start).toHaveBeenCalledWith({
          ...blankSettings,
          manifest,
          duration: 12,
        });
      }
      act(() => {
        state.value = ValidatorState.ACTIVE;
      });
      expect(cancelBtn.disabled).toEqual(false);
    }
  );

  test.each(["0", "4200"])("duration limit %s", async (limit: string) => {
    const userEv = userEvent.setup();
    const { durationElt, getByText } = renderForm({
      data,
      state,
      setValue,
      start,
      cancel,
    });
    await userEv.click(durationElt);
    await userEv.clear(durationElt);
    await userEv.type(durationElt, limit);
    getByText("duration must be >= 1 second and <= 3600 seconds");
  });
});
