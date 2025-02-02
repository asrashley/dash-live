import { type ComponentChildren } from "preact";
import { mock } from "vitest-mock-extended";
import { renderHook } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { FlattenedUserState, useAllUsers } from "./useAllUsers";
import { ApiRequests, EndpointContext } from "../endpoints";

import users from "../test/fixtures/users.json";
import { mediaUser } from "../test/MockServer";
import { InitialUserState } from "../types/UserState";

describe("useAllUsers hook", () => {
  const apiRequests = mock<ApiRequests>();
  let allUsersProm: Promise<void>;

  const wrapper = ({ children }: { children: ComponentChildren }) => {
    return (
      <EndpointContext.Provider value={apiRequests}>
        {children}
      </EndpointContext.Provider>
    );
  };

  beforeEach(() => {
    allUsersProm = new Promise<void>((resolve) => {
      apiRequests.getAllUsers.mockImplementation(async () => {
        resolve();
        return users;
      });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("gets all users", async () => {
    const { result } = renderHook(() => useAllUsers(), { wrapper });
    await allUsersProm;
    const { allUsers } = result.current;
    expect(allUsers.value).toEqual(users);
    const flattened: FlattenedUserState[] = allUsers.value.map(({groups, ...user}) => ({
        ...user,
        adminGroup: groups.includes('ADMIN'),
        mediaGroup: groups.includes('MEDIA'),
        userGroup: groups.includes('USER'),
    }));
    expect(result.current.flattenedUsers.value).toEqual(flattened);
  });

  test("add a new user", async () => {
    const { result } = renderHook(() => useAllUsers(), { wrapper });
    await allUsersProm;
    const { addUser } = result.current;
    expect(
      addUser({
        mustChange: true,
        groups: [],
      })
    ).toEqual(false);
    expect(
      addUser({
        username: mediaUser.username,
        mustChange: true,
        groups: [],
      })
    ).toEqual(false);
    const user: Omit<InitialUserState, "lastLogin"> = {
      username: "new.name",
      email: "some.email@local",
      mustChange: true,
      groups: ["USER"],
    };
    expect(addUser(user)).toEqual(true);
    expect(result.current.allUsers.value).toEqual([
      ...users,
      {
        lastLogin: null,
        ...user,
      },
    ]);
  });

  test("modifies a user", async () => {
    const { result } = renderHook(() => useAllUsers(), { wrapper });
    await allUsersProm;
    const { updateUser } = result.current;
    const user: InitialUserState = {
      username: "new.name",
      email: "some.email@local",
      mustChange: true,
      groups: ["USER"],
      lastLogin: null,
    };
    expect(updateUser(user)).toEqual(false);
    user.pk = users[1].pk;
    expect(updateUser(user)).toEqual(true);
    expect(result.current.allUsers.value).toEqual(
      users.map((usr) => (usr.pk === user.pk ? user : usr))
    );
  });
});
