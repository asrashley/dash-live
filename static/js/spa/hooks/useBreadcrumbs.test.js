import { describe, expect, test } from "vitest";
import { renderHook, act } from "@testing-library/preact";

import { useBreadcrumbs } from "./useBreadcrumbs.js";

describe("useBreadCrumbs hook", () => {
  test("useBreadcrumbs() hook", () => {
    const { result } = renderHook(() => useBreadcrumbs());

    expect(result.current.breadcrumbs).toEqual([
      {
        active: true,
        href: "/",
        id: "crumb_0",
        title: "Home",
      },
    ]);

    act(() => {
      result.current.setLocation("/multi-period-streams/demo");
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
