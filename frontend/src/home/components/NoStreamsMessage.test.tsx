import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import { NoStreamsMessage } from "./NoStreamsMessage";

describe("NoStreamsMessage", () => {
  test("should display message", () => {
    const { asFragment, getByText } = renderWithProviders(
      <NoStreamsMessage />
    );
    getByText('Please add some media files');
    expect(asFragment()).toMatchSnapshot();
  });
});
