import { describe, expect, test } from "vitest";
import { Route } from "wouter-preact";

import { renderWithProviders } from "../test/renderWithProviders";
import { elementAsFragment } from '../test/asFragment';
import { BreadCrumbs } from "./BreadCrumbs";

describe("BreadCrumbs", () => {
  test("should display Breadcrumbs", () => {
    document.body.innerHTML = `<header>
          <div class="breadcrumbs">
            <ol class="breadcrumb" />
          </div>
        </header><div id="app" />`;
    const baseElement = document.getElementById("app");
    expect(baseElement).toBeDefined();
    expect(baseElement).not.toBeNull();
    renderWithProviders(
      <div>
        <BreadCrumbs />
        <Route path="/multi-period-streams/:stream">
          <div />
        </Route>
      </div>,
      {
        baseElement,
        path: "/multi-period-streams/.add",
      }
    );
    expect(document.querySelector("ol.breadcrumb")?.innerHTML).toBe(
      '<li id="crumb_0" class="breadcrumb-item "><a href="/" title="Home">Home</a></li>' +
        '<li id="crumb_1" class="breadcrumb-item "><a href="/multi-period-streams" ' +
        'title="multi-period-streams">multi-period-streams</a></li>' +
        '<li id="crumb_2" class="breadcrumb-item active">.add</li>'
    );
    expect(elementAsFragment(document.body)).toMatchSnapshot();
  });
});
