import { describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";
import { fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { Icon, IconButton } from "./Icon.js";

describe("Icon", () => {
  test("should display an icon", () => {
    const { getByRole } = renderWithProviders(
      html`<${Icon} name="snow3" />`
    );
    const span = getByRole('icon');
    expect(span.className.trim()).toEqual('bi icon bi-snow3');
  });
});

describe('IconButton', () => {
  test('renders an enabled icon button', () => {
    const onClick = vi.fn();
    const { getBySelector } = renderWithProviders(
      html`<${IconButton} name="snow3" onClick=${onClick} />`
    );
    fireEvent.click(getBySelector('a'));
    expect(onClick).toHaveBeenCalled();
  });

  test('renders a disabled icon button', () => {
    const onClick = vi.fn();
    const { getBySelector } = renderWithProviders(
      html`<${IconButton} name="snow3" onClick=${onClick} disabled />`
    );
    expect(getBySelector('a').classList.contains('disabled')).toEqual(true);
    fireEvent.click(getBySelector('a'));
    expect(onClick).not.toHaveBeenCalled();
  });
});