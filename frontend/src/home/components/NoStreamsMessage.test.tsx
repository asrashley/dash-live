import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import { NoStreamsMessage } from "./NoStreamsMessage";
import { InitialUserState } from "../../types/UserState";

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
    const userInfo: InitialUserState = {
      pk: 123,
      username: 'test',
      email: 'test@unit.local',
      isAuthenticated: true,
      groups: ['USER']
    }
    const { asFragment, queryByTestId, getByText } = renderWithProviders(
      <NoStreamsMessage />, { userInfo }
    );
    expect(queryByTestId('needs-login')).toBeNull();
    getByText('to add some media files', { exact: false});
    expect(asFragment()).toMatchSnapshot();
  });
});
