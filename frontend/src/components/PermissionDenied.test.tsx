import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { act } from "@testing-library/preact";

import { uiRouteMap } from "@dashlive/routemap";

import { renderWithProviders } from "../test/renderWithProviders";
import { PermissionDenied } from "./PermissionDenied";
import { useLocation } from "wouter-preact";

vi.mock("wouter-preact", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useLocation: vi.fn(),
  };
});

describe("PermissionDenied", () => {
  const useLocationMock = vi.mocked(useLocation);
  const setLocation = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    useLocationMock.mockReturnValue(["/", setLocation]);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  test("renders message and login link", () => {

    const { asFragment, getByText, getBySelector } = renderWithProviders(
      <PermissionDenied />
    );

    expect(document.getElementById("permission-denied")).not.toBeNull();
    getByText("You need to log in to access this page");
    getByText("This page is only available for users who have logged in.");
    getByText("go to the login page");

    const link = getBySelector("a.link") as HTMLAnchorElement;
    expect(link.getAttribute("href")).toEqual(uiRouteMap.login.url());

    expect(asFragment()).toMatchSnapshot();
  });

  test("redirects to login page after 10 seconds", () => {

    renderWithProviders(<PermissionDenied />);

    act(() => {
      vi.advanceTimersByTime(9999);
    });
    expect(setLocation).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(setLocation).toHaveBeenCalledWith(uiRouteMap.login.url());
  });
});
