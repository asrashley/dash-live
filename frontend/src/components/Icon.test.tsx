import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { Icon } from "./Icon";
import { signal } from "@preact/signals-core";

describe("Icon", () => {
  test("should display an icon", () => {
    const { getByRole } = renderWithProviders(
      <Icon name="snow3" className="hello-world" />
    );
    const span = getByRole('img') as HTMLElement;
    expect(span.className.trim()).toEqual('bi icon bi-snow3 hello-world');
    expect(span.getAttribute('aria-label')).toEqual('snow3 icon');
  });

  test("can use a signal for name", () => {
    const name = signal("snow3");
    const { getByRole } = renderWithProviders(
      <Icon name={name} />
    );
    const span = getByRole('img') as HTMLElement;
    expect(span.className.trim()).toEqual('bi icon bi-snow3');
    expect(span.getAttribute('aria-label')).toEqual('snow3 icon');
  });

  test("can use a signal for classname", () => {
    const className = signal("my-class-name");
    const { getByRole } = renderWithProviders(
      <Icon name="step-forward" className={className} />
    );
    const span = getByRole('img') as HTMLElement;
    expect(span.className.trim()).toEqual('bi icon bi-step-forward my-class-name');
  });
});
