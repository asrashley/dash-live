import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { Icon } from "./Icon";

describe("Icon", () => {
  test("should display an icon", () => {
    const { getByRole } = renderWithProviders(
      <Icon name="snow3" />
    );
    const span = getByRole('img') as HTMLElement;
    expect(span.className.trim()).toEqual('bi icon bi-snow3');
  });
});
