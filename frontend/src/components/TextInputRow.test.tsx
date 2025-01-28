import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { TextInputRow } from "./TextInputRow";
import { signal } from "@preact/signals";

describe("TextInputRow", () => {
  const name = "tirtest";
  const onInput = vi.fn();
  const error = signal<string|undefined>();

  beforeEach(() => {
    error.value = undefined;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should match snapshot", () => {
    const label = "the input label";
    const text = "description of the input";
    const { asFragment, getByText } = renderWithProviders(
      <TextInputRow
        name={name}
        onInput={onInput}
        placeholder="search..."
        required={true}
        label={label}
        text={text}
        error={error}
      />
    );
    getByText(label, { exact: false });
    getByText(text);
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows error", () => {
    const label = "the input label";
    const text = "description of the input";
    error.value = "there is a problem with this value";
    const { getByText } = renderWithProviders(
      <TextInputRow
        name={name}
        onInput={onInput}
        placeholder="search..."
        required={true}
        label={label}
        text={text}
        error={error}
      />
    );
    getByText(label, { exact: false });
    getByText(text);
    getByText(error);
  });
});
