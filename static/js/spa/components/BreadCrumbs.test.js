import { describe, expect, test } from "vitest";
import { html } from "htm/preact";
import { Route } from "wouter-preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { BreadCrumbs } from "./BreadCrumbs.js";

describe("BreadCrumbs", () => {
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
