import { describe, expect, test } from "vitest";
import { computed, signal } from "@preact/signals";
import { act, render } from "@testing-library/preact";

import { AppStateContext, AppStateType } from "../appState";
import { DialogState } from "../types/DialogState";
import { ModalBackdrop } from "./ModalBackdrop";

describe("ModalBackdrop component", () => {
  const dialog = signal<DialogState>({ backdrop: false });
  const appState: AppStateType = {
    backdrop: computed<boolean>(() => dialog.value?.backdrop ?? false),
    dialog,
  };

  test("shows and hides backdrop", () => {
    const { getByTestId } = render(
      <AppStateContext.Provider value={appState}>
        <ModalBackdrop />
      </AppStateContext.Provider>
    );
    const elt = getByTestId("modal-backdrop") as HTMLDivElement;
    expect(elt.classList.contains("d-none")).toBe(true);
    expect(elt.classList.contains("show")).toBe(false);
    act(() => {
      dialog.value = { backdrop: true };
    });
    expect(elt.classList.contains("d-none")).toBe(false);
    expect(elt.classList.contains("show")).toBe(true);
  });
});
