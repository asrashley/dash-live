import { describe, expect, test } from "vitest";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ProgressBar } from "./ProgressBar";
import { ProgressState } from "../types/ProgressState";

describe("ProgressBar component", () => {
  const progress = signal<ProgressState>();

  test.each([
    [undefined, undefined],
    [0, undefined],
    [10, "started"],
    [25, "getting busy"],
    [50, "half way there"],
    [75, "not long now"],
    [100, "all done"],
  ])("matches snapshot for %s%%", (pct: number | undefined, txt: string | undefined) => {
    progress.value = {
      text: txt,
      currentValue: pct,
      minValue: 0,
      maxValue: 100,
      finished: pct === 100,
    };
    const { asFragment, getBySelector, getByText } = renderWithProviders(
      <ProgressBar progress={progress} />
    );
    if (txt) {
        getByText(txt);
    }
    const bar = getBySelector(".progress-bar") as HTMLElement;
    if (pct !== undefined) {
        expect(bar.style.width).toEqual(`${pct}%`);
    }
    expect(bar.classList.contains("bg-success")).toEqual(pct === 100);
    expect(bar.classList.contains('bg-warning')).toEqual(false);
    expect(bar.classList.contains("progress-bar-animated")).toEqual(pct !== undefined && pct !== 100);
    expect(bar.classList.contains("visually-hidden")).toEqual(pct === undefined);
    expect(asFragment()).toMatchSnapshot();
  });

  test('finished with an error', () => {
    progress.value = {
      text: '',
      currentValue: 34.5,
      minValue: 0,
      maxValue: 100,
      finished: true,
      error: true,
    };
    const { getBySelector } = renderWithProviders(
      <ProgressBar progress={progress} />
    );
    const bar = getBySelector(".progress-bar") as HTMLElement;
    expect(bar.classList.contains('bg-warning')).toEqual(true);
    expect(bar.classList.contains('bg-success')).toEqual(false);
  });
});
