import { afterEach, describe, expect, test, vi } from "vitest";
import { fireEvent } from "@testing-library/preact";

import { navbar } from "@dashlive/routemap";
import { renderWithProviders } from "../test/renderWithProviders";

import { NavBar } from "./NavBar";
import { mediaUser } from "../test/MockServer";

describe("NavBar component", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot when not logged in", () => {
    const { asFragment, findByText } = renderWithProviders(
      <NavBar items={navbar} />
    );
    navbar.forEach((bar) => {
      findByText(bar.title);
    });
    findByText("Log In");
    expect(asFragment()).toMatchSnapshot();
  });

  test("matches snapshot when logged in", () => {
    const { asFragment, findByText } = renderWithProviders(
      <NavBar items={navbar} />,
      { userInfo: mediaUser }
    );
    navbar.forEach((bar) => {
      findByText(bar.title);
    });
    findByText("Log Out");
    expect(asFragment()).toMatchSnapshot();
  });

  test("can toggle expanded menu", () => {
    const { getBySelector } = renderWithProviders(<NavBar items={navbar} />);
    const btn = getBySelector(".navbar-toggler") as HTMLButtonElement;
    const list = getBySelector("#navbarSupportedContent") as HTMLElement;
    expect(btn.className.trim()).toEqual("navbar-toggler collapsed");
    expect(list.classList.contains("show")).toEqual(false);
    fireEvent.click(btn);
    expect(btn.className.trim()).toEqual("navbar-toggler");
    expect(list.classList.contains("show")).toEqual(true);
  });
});
