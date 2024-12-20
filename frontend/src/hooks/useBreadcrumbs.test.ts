import { afterAll, describe, expect, test, vi } from "vitest";
import { renderHook, act } from "@testing-library/preact";
import * as WouterPreact from 'wouter-preact';

import { useBreadcrumbs } from "./useBreadcrumbs";

vi.mock('wouter-preact');

describe("useBreadCrumbs hook", () => {
  const useLocationSpy = vi.spyOn(WouterPreact, 'useLocation');
  const setLocation = vi.fn();

  afterAll(() => {
    vi.restoreAllMocks();
  });

  test("useBreadcrumbs() hook", () => {
    useLocationSpy.mockReturnValue(['/', setLocation]);

    const { result, rerender } = renderHook(() => useBreadcrumbs());

    expect(result.current.breadcrumbs).toEqual([
      {
        active: true,
        href: "/",
        id: "crumb_0",
        title: "Home",
      },
    ]);

    act(() => {
      useLocationSpy.mockReturnValue(["/multi-period-streams/demo", setLocation]);
      rerender();
    });

    expect(result.current.breadcrumbs).toEqual([
      {
        title: "Home",
        active: false,
        href: "/",
        id: "crumb_0",
      },
      {
        title: "multi-period-streams",
        active: false,
        href: "/multi-period-streams",
        id: "crumb_1",
      },
      {
        title: "demo",
        active: true,
        href: "/multi-period-streams/demo",
        id: "crumb_2",
      },
    ]);
  });
});
