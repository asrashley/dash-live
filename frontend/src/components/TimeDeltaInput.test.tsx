import { describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { TimeDeltaInput } from "./TimeDeltaInput.js";

describe("TimeDeltaInput", () => {
  test("matches snapshot", () => {
    const onChange = vi.fn();
    const { getBySelector, asFragment } = renderWithProviders(
      html`<${TimeDeltaInput} value="PT5M12S" onChange=${onChange} />`
    );
    const inp = getBySelector('input[type="time"]');
    expect(inp.value).toEqual("00:05:12");
    expect(inp.className.trim()).toEqual("form-control is-valid");
    expect(asFragment()).toMatchSnapshot();
  });
});
