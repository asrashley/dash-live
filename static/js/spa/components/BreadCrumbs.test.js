import { describe, expect, test } from "vitest";
import { html } from "htm/preact";
import { Route } from "wouter-preact";
import { renderHook, act } from "@testing-library/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { BreadCrumbs, useBreadcrumbs } from "./BreadCrumbs.js";

describe("BreadCrumbs", () => {
  test("useBreadcrumbs() hook", () => {
    const { result } = renderHook(() => useBreadcrumbs());

    expect(result.current.breadcrumbs).toEqual([
      {
        active: true,
        href: "/",
        id: "crumb_0",
        title: "Home",
        useLink: false,
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
        useLink: false,
        id: "crumb_0",
      },
      {
        title: "multi-period-streams",
        active: false,
        href: "/multi-period-streams",
        useLink: true,
        id: "crumb_1",
      },
      {
        title: "demo",
        active: true,
        href: "/multi-period-streams/demo",
        useLink: true,
        id: "crumb_2",
      },
    ]);
  });

  test("should display Breadcrumbs", () => {
    const { container } = renderWithProviders(
      html`<header> <div class="breadcrumbs"> <ol class="breadcrumb"></ol></div></header>'
          <${BreadCrumbs} />
          <${Route} path="/multi-period-streams/:stream"><div /></${Route}>`,
      { path: "/multi-period-streams/.add" }
    );
    expect(container.querySelector("ol.breadcrumb")?.innerHTML).toBe(
      '<li id="crumb_0" class="breadcrumb-item "><a href="/" title="Home">Home</a></li>' +
        '<li id="crumb_1" class="breadcrumb-item "><a href="/multi-period-streams" ' +
        'title="multi-period-streams">multi-period-streams</a></li>' +
        '<li id="crumb_2" class="breadcrumb-item active">.add</li>'
    );
  });
});
