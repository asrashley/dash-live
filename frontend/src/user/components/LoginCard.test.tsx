import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { act } from "preact/test-utils";
import { signal } from "@preact/signals";

import { LoginCard } from "./LoginCard";
import { renderWithProviders } from "../../test/renderWithProviders";

describe("LoginCard component", () => {
  const error = signal<string | undefined>();
  const submitting = signal<boolean>(false);
  const onLogin = vi.fn();

  beforeEach(() => {
    error.value = undefined;
    submitting.value = false;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", () => {
    const { asFragment, getByRole } = renderWithProviders(
      <LoginCard error={error} submitting={submitting} onLogin={onLogin} />
    );
    expect((getByRole("alert") as HTMLElement).className).toEqual("d-none");
    expect(asFragment()).toMatchSnapshot();
  });

  test("displays error message", () => {
    error.value = "this is a login error";
    const { getByText, getByRole } = renderWithProviders(
      <LoginCard error={error} submitting={submitting} onLogin={onLogin} />
    );
    getByText(error.value);
    expect((getByRole("alert") as HTMLElement).className).toEqual(
      "alert alert-danger"
    );
  });

  test("can submit login details", async () => {
    const user = userEvent.setup();
    const { getBySelector, getByLabelText } = renderWithProviders(
      <LoginCard error={error} submitting={submitting} onLogin={onLogin} />
    );
    expect((getBySelector("#login-form") as HTMLElement).className).toEqual("");
    const userInp = getByLabelText("Username", {
      exact: false,
    }) as HTMLInputElement;
    const pwdInp = getByLabelText("Password", {
      exact: false,
    }) as HTMLInputElement;
    await user.type(userInp, "test");
    await user.type(pwdInp, "secret");
    const submit = getBySelector('button[type="submit"]') as HTMLButtonElement;
    expect(submit.disabled).toEqual(false);
    await user.click(submit);
    expect(onLogin).toHaveBeenCalledTimes(1);
    expect(onLogin).toHaveBeenCalledWith({
      username: "test",
      password: "secret",
      rememberme: false,
    });
    act(() => {
      submitting.value = true;
    });
    expect((getBySelector("#login-form") as HTMLElement).className).toEqual(
      "opacity-25"
    );
    expect(
      (getBySelector('button[type="submit"]') as HTMLButtonElement).disabled
    ).toEqual(true);
  });
});
