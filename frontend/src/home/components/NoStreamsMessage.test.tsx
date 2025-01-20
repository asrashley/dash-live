import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import { NoStreamsMessage } from "./NoStreamsMessage";
import { normalUser } from "../../test/MockServer";

describe("NoStreamsMessage", () => {
  test("should display message with a login link", () => {
    const { asFragment, getByText, getByTestId } = renderWithProviders(
      <NoStreamsMessage />
    );
    getByTestId('needs-login');
    getByText('to add some media files', { exact: false});
    expect(asFragment()).toMatchSnapshot();
  });

  test("should display message for a user who is already logged in", () => {
    const { asFragment, queryByTestId, getByText } = renderWithProviders(
      <NoStreamsMessage />, { userInfo: normalUser }
    );
    expect(queryByTestId('needs-login')).toBeNull();
    getByText('to add some media files', { exact: false});
    expect(asFragment()).toMatchSnapshot();
  });
});
