import { beforeEach, describe, expect, test } from "vitest";
import { mock } from "vitest-mock-extended";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { OptionsRow } from "./OptionsRow";
import {
  decorateMultiPeriodStream,
  MpsModelValidationErrors,
  MultiPeriodModelContext,
  UseMultiPeriodStreamHook,
} from "../../hooks/useMultiPeriodStream";
import { DecoratedMultiPeriodStream } from "../../types/DecoratedMultiPeriodStream";

import { model as mpsStream } from "../../test/fixtures/multi-period-streams/demo.json";
import { fireEvent } from "@testing-library/preact";

describe("OptionsRow component", () => {
  const canModify = signal<boolean>(false);
  const model = signal<DecoratedMultiPeriodStream>();
  const multiPeriodStreamHook = mock<UseMultiPeriodStreamHook>({
    loaded: signal<string | undefined>(),
    modified: signal<boolean>(false),
    errors: signal<MpsModelValidationErrors>({}),
    isValid: signal<boolean>(true),
    model,
  });

  beforeEach(() => {
    model.value = decorateMultiPeriodStream(mpsStream);
    canModify.value = true;
  });

  test("matches snapshot", () => {
    const { asFragment } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={multiPeriodStreamHook}>
        <OptionsRow name="rowtest" canModify={canModify} />
      </MultiPeriodModelContext.Provider>
    );
    expect(asFragment()).toMatchSnapshot();
  });

  test("does not show options button if modification not allowed", () => {
    canModify.value = false;
    const { queryByText } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={multiPeriodStreamHook}>
        <OptionsRow name="rowtest" canModify={canModify} />
      </MultiPeriodModelContext.Provider>
    );
    expect(queryByText("Options")).toBeNull();
  });

  test("can open options dialog", () => {
    const { getByText, state } = renderWithProviders(
      <MultiPeriodModelContext.Provider value={multiPeriodStreamHook}>
        <OptionsRow name="rowtest" canModify={canModify} />
      </MultiPeriodModelContext.Provider>
    );
    const btn = getByText("Options") as HTMLButtonElement;
    fireEvent.click(btn);
    expect(state.dialog.value).toEqual({
      backdrop: true,
      mpsOptions: {
        lastModified: 0,
        name: "rowtest",
        options: mpsStream.options,
      },
    });
  });
});
