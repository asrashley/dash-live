import { vi, describe, expect, test } from "vitest";
import { html } from "htm/preact";
import { fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { Alert } from "./Alert.js";

describe("Alert", () => {
  test("should display Alert", () => {
    const { container, queryBySelector } = renderWithProviders(
      html`<${Alert} id=${2} text="alert text" level="warning" />`
    );
    expect(container.textContent).toMatch("alert text");
    expect(queryBySelector("button")).toBeNull();
    const elt = document.getElementById('alert_2');
    expect(elt).not.toBeNull();
    expect(elt.className).toEqual('alert alert-warning show');
  });

  test("should display Alert with dismiss button", () => {
    const onDismiss = vi.fn();
    const { container, queryBySelector } = renderWithProviders(
      html`<${Alert}
        text="alert text"
        level="info"
        id="1"
        onDismiss=${onDismiss}
      />`
    );
    const elt = document.getElementById('alert_1');
    expect(elt).not.toBeNull();
    expect(elt.classList.toString()).toEqual('alert alert-info alert-dismissible fade show');
    expect(container.textContent).toMatch("alert text");
    const btn = queryBySelector("button");
    expect(btn).not.toBeNull();
    fireEvent.click(btn);
    expect(onDismiss).toHaveBeenCalled();
  });
});
