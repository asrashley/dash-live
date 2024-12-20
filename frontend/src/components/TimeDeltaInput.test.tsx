import { describe, expect, test, vi } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { TimeDeltaInput } from "./TimeDeltaInput";

describe("TimeDeltaInput", () => {
  test("matches snapshot", () => {
    const onChange = vi.fn();
    const { getBySelector, asFragment } = renderWithProviders(
      <TimeDeltaInput name="tdi" value="PT5M12S" onChange={onChange} />
    );
    const inp = getBySelector('input[type="time"]') as HTMLInputElement;
    expect(inp.value).toEqual("00:05:12");
    expect(inp.className.trim()).toEqual("form-control is-valid");
    expect(asFragment()).toMatchSnapshot();
  });
});
