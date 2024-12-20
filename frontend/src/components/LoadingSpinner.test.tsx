import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { LoadingSpinner } from "./LoadingSpinner";

describe("LoadingSpinner", () => {
  test("should display spinner", () => {
    const { asFragment, getBySelector, getAllBySelector } = renderWithProviders(
      <LoadingSpinner  />
    );
    getBySelector('.lds-ring');
    expect(getAllBySelector('.lds-ring > .lds-seg').length).toEqual(4);
    expect(asFragment()).toMatchSnapshot();
  });
});
