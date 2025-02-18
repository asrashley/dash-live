import { afterEach, describe, expect, test, vi } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import { TimeDeltaInput } from "./TimeDeltaInput";

describe("TimeDeltaInput", () => {
  const onChange = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", () => {
    const { getBySelector, asFragment } = renderWithProviders(
      <TimeDeltaInput name="tdi" value="PT5M12S" onChange={onChange} />
    );
    const inp = getBySelector('input[type="time"]') as HTMLInputElement;
    expect(inp.value).toEqual("00:05:12");
    expect(inp.className.trim()).toEqual("form-control is-valid");
    expect(asFragment()).toMatchSnapshot();
  });

  test("empty duration", () => {
    const { getBySelector } = renderWithProviders(
      <TimeDeltaInput name="tdi" value="" onChange={onChange} />
    );
    const inp = getBySelector('input[type="time"]') as HTMLInputElement;
    expect(inp.value).toEqual("00:00:00");
  });

  test.each<[string, string]>([
    ["00:01", "PT1S"],
    ["02:03", "PT2M3S"],
    ["01:02:03", "PT1H2M3S"]
  ])("changing time input to %s sets value to %s", (inpValue: string, isoValue: string) => {
    const { getBySelector } = renderWithProviders(
      <TimeDeltaInput name="tdi" value="PT5M12S" onChange={onChange} />
    );
    const inp = getBySelector('input[type="time"]') as HTMLInputElement;
    inp.value = inpValue;
    inp.dispatchEvent(new Event("input", { bubbles: true }));
    expect(onChange).toHaveBeenCalledWith("tdi", isoValue);
  });
});
