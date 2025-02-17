import { beforeEach, describe, expect, test } from "vitest";
import { signal } from "@preact/signals";

import { ValidatorState } from "../hooks/useValidatorWebsocket";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ProgressBarWithState } from "./ProgressBarWithState";
import { ProgressState } from "../types/ProgressState";

describe("ProgressBarWithState component", () => {
  const progress = signal<ProgressState>({
    minValue: 0,
    maxValue: 100,
    finished: false,
    error: false,
    text: "",
  });
  const state = signal<ValidatorState>(ValidatorState.DISCONNECTED);

  beforeEach(() => {
    state.value = ValidatorState.DISCONNECTED;
    progress.value = {
      minValue: 0,
      maxValue: 100,
      finished: false,
      error: false,
      text: "",
    };
  });

  test.each<ValidatorState>([
    ValidatorState.DISCONNECTED,
    ValidatorState.IDLE,
    ValidatorState.ACTIVE,
    ValidatorState.CANCELLING,
    ValidatorState.CANCELLED,
    ValidatorState.DONE,
  ])("renders when state=%s", (valState: ValidatorState) => {
    state.value = valState;
    progress.value.text = `renders when state=${valState}`;
    const { asFragment, getByTestId, getByText } = renderWithProviders(
      <ProgressBarWithState state={state} progress={progress} />
    );
    const badge = getByTestId("validator-state-badge") as HTMLElement;
    expect(badge.innerHTML).toEqual(valState);
    getByText(progress.value.text);
    expect(asFragment()).toMatchSnapshot();
  });
});
