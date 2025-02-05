import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../test/renderWithProviders";

import { createNavItems, NavBar } from "./NavBar";
import { adminUser, mediaUser, normalUser } from "../test/MockServer";
import { UserState } from "../types/UserState";

describe("NavBar component", () => {
  const user = signal<UserState>();

  beforeEach(() => {
    user.value = {
      isAuthenticated: false,
      lastLogin: null,
      mustChange: false,
      groups: [],
      permissions: {
        admin: false,
        media: false,
        user: false
      },
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot when not logged in", () => {
    const { asFragment, findByText } = renderWithProviders(
      <NavBar />
    );
    const navbar = createNavItems(user);
    navbar.forEach((bar) => {
      findByText(bar.title);
    });
    findByText("Log In");
    expect(asFragment()).toMatchSnapshot();
  });

  test.each<boolean>([true, false])("matches snapshot when logged in when admin=%s", (isAdmin: boolean) => {
    const usr = isAdmin ? adminUser: normalUser;
    user.value = {
      ...usr,
      isAuthenticated: true,
      permissions: {
        admin: isAdmin,
        media: isAdmin,
        user: true,
      },
    };
    const { asFragment, findByText } = renderWithProviders(
      <NavBar />,
      { userInfo: mediaUser }
    );
    const navbar = createNavItems(user);
    expect(navbar.some(item => item.title === "Users"));
    navbar.forEach((bar) => {
      findByText(bar.title);
    });
    findByText("Log Out");
    expect(asFragment()).toMatchSnapshot();
  });

  test("can toggle expanded menu", () => {
    const { getBySelector } = renderWithProviders(<NavBar />);
    const btn = getBySelector(".navbar-toggler") as HTMLButtonElement;
    const list = getBySelector("#navbarSupportedContent") as HTMLElement;
    expect(btn.className.trim()).toEqual("navbar-toggler collapsed");
    expect(list.classList.contains("show")).toEqual(false);
    fireEvent.click(btn);
    expect(btn.className.trim()).toEqual("navbar-toggler");
    expect(list.classList.contains("show")).toEqual(true);
  });
});
