import { computed, signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { uiRouteMap } from "@dashlive/routemap";

import {
  UserValidationErrors,
} from "../../hooks/useAllUsers";
import { renderWithProviders } from "../../test/renderWithProviders";
import { EditUserCard } from "./EditUserCard";
import { mediaUser } from "../../test/MockServer";
import { FlattenedUserState } from "../../types/FlattenedUserState";

describe("EditUserCard component", () => {
  const backUrl = uiRouteMap.listUsers.url();
  const user = signal<FlattenedUserState | undefined>();
  const errors = signal<UserValidationErrors>({});
  const allUsersError = signal<string | null>(null);
  const disabledFields = signal<Record<string, boolean>>({});
  const header = computed<string>(() => `Editing user ${user.value?.username ?? ""}`);
  const setValue = vi.fn();
  const onSave = vi.fn();
  const onDelete = vi.fn();

  beforeEach(() => {
    const { pk, username, email, lastLogin, mustChange } = mediaUser;
    user.value = {
      pk,
      username,
      email,
      lastLogin,
      mustChange,
      adminGroup: true,
      mediaGroup: true,
      userGroup: true,
    };
    errors.value = {};
    allUsersError.value = null;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", async () => {
    const { getByText, findBySelector } = renderWithProviders(
      <EditUserCard
        backUrl={backUrl}
        header={header}
        user={user}
        networkError={allUsersError}
        validationErrors={errors}
        disabledFields={disabledFields}
        setValue={setValue}
        onSave={onSave}
        onDelete={onDelete}
      />
    );
    getByText("Save Changes");
    getByText("Delete User");
    const userInp = (await findBySelector(
      'input[name="username"]'
    )) as HTMLInputElement;
    expect(userInp.value).toEqual(user.value.username);
    const emailInp = (await findBySelector(
      'input[name="email"]'
    )) as HTMLInputElement;
    expect(emailInp.value).toEqual(user.value.email);
    const pwdInp = (await findBySelector(
      'input[name="password"]'
    )) as HTMLInputElement;
    expect(pwdInp.value).toEqual("");
    expect(pwdInp.placeholder).toEqual("***");
    expect(onSave).not.toHaveBeenCalled();
  });

  test('shows loading spinner', () => {
    user.value = undefined;
    const { getBySelector } = renderWithProviders(
        <EditUserCard
          backUrl={backUrl}
          header={header}
          user={user}
          networkError={allUsersError}
          validationErrors={errors}
          disabledFields={disabledFields}
          setValue={setValue}
          onSave={onSave}
          onDelete={onDelete}
        />
      );
      getBySelector(".lds-ring");
  });

  test("shows error fetching users list", async () => {
    allUsersError.value = "server error";
    const { findByText } = renderWithProviders(
      <EditUserCard
        backUrl={backUrl}
        header={header}
        user={user}
        networkError={allUsersError}
        validationErrors={errors}
        disabledFields={disabledFields}
        setValue={setValue}
        onSave={onSave}
        onDelete={onDelete}
      />
    );
    await findByText("server error", { exact: false });
  });

  test("can click save", async () => {
    const evUser = userEvent.setup();
    const { getByText } = renderWithProviders(
      <EditUserCard
        backUrl={backUrl}
        header={header}
        user={user}
        networkError={allUsersError}
        validationErrors={errors}
        disabledFields={disabledFields}
        setValue={setValue}
        onSave={onSave}
        onDelete={onDelete}
      />
    );
    const saveBtn = getByText("Save Changes") as HTMLButtonElement;
    await evUser.click(saveBtn);
    expect(onSave).toHaveBeenCalled();
    expect(onDelete).not.toHaveBeenCalled();
    expect(setValue).not.toHaveBeenCalled();
  });

  test("can click delete", async () => {
    const evUser = userEvent.setup();
    const { getByText } = renderWithProviders(
      <EditUserCard
        backUrl={backUrl}
        header={header}
        user={user}
        networkError={allUsersError}
        validationErrors={errors}
        disabledFields={disabledFields}
        setValue={setValue}
        onSave={onSave}
        onDelete={onDelete}
      />
    );
    const delBtn = getByText("Delete User") as HTMLButtonElement;
    await evUser.click(delBtn);
    expect(onSave).not.toHaveBeenCalled();
    expect(onDelete).toHaveBeenCalled();
    expect(setValue).not.toHaveBeenCalled();
  });

  test("can modify user", async () => {
    const evUser = userEvent.setup();
    const { findBySelector } = renderWithProviders(
      <EditUserCard
        backUrl={backUrl}
        header={header}
        user={user}
        networkError={allUsersError}
        validationErrors={errors}
        disabledFields={disabledFields}
        setValue={setValue}
        onSave={onSave}
        onDelete={onDelete}
      />
    );
    const userInp = (await findBySelector(
      'input[name="username"]'
    )) as HTMLInputElement;
    expect(userInp.value).toEqual(user.value.username);
    await evUser.clear(userInp);
    await evUser.type(userInp, 'new.username');
    expect(setValue).toHaveBeenLastCalledWith('username', 'new.username');
    const emailInp = (await findBySelector(
      'input[name="email"]'
    )) as HTMLInputElement;
    await evUser.clear(emailInp);
    await evUser.type(emailInp, 'media@email.local');
    expect(setValue).toHaveBeenLastCalledWith('email', 'media@email.local');
  });
});
