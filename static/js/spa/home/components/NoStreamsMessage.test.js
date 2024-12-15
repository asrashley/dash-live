import { describe, expect, test } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../../test/renderWithProviders.js";
import { NoStreamsMessage } from "./NoStreamsMessage.js";

describe("NoStreamsMessage", () => {
  test("should display message", () => {
    const { asFragment, getByText } = renderWithProviders(
      html`<${NoStreamsMessage} />`
    );
    getByText('Please add some media files');
    expect(asFragment()).toMatchSnapshot();
  });
});
