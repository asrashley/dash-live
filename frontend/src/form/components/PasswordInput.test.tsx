import { signal } from "@preact/signals";
import { describe, expect, test, vi } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import { PasswordInput } from "./PasswordInput";
import { fireEvent } from "@testing-library/preact";

describe("PasswordInput component", () => {
  const value = signal<string>("abc123");
  const disabled = signal<boolean>(false);
  const onInput = vi.fn();

  test('hides reveal button if now allowed', () => {
    const { getBySelector } = renderWithProviders(
        <PasswordInput
          name="test"
          id="model-test"
          type="password"
          title="password test"
          className=""
          aria-describedby="tst"
          disabled={disabled}
          value={value}
          onInput={onInput}
        />
      );
      expect((getBySelector('input[name="test"]') as HTMLInputElement).type).toEqual("password");
      const btn = getBySelector('button') as HTMLElement;
      expect(btn.className).toEqual('d-none');
  });

  test("can reveal password", () => {
    const { getByText, getBySelector } = renderWithProviders(
      <PasswordInput
        name="test"
        id="model-test"
        type="password"
        title="password test"
        className=""
        aria-describedby="tst"
        disabled={disabled}
        allowReveal={true}
        value={value}
        onInput={onInput}
      />
    );
    expect((getBySelector('input[name="test"]') as HTMLInputElement).type).toEqual("password");
    expect((getBySelector('input[name="test"]') as HTMLInputElement).value).toEqual(value.value);
    let btn = getByText("Reveal") as HTMLButtonElement;
    fireEvent.click(btn);
    expect((getBySelector('input[name="test"]') as HTMLInputElement).type).toEqual("text");
    expect((getBySelector('input[name="test"]') as HTMLInputElement).value).toEqual(value.value);
    btn = getByText("Hide") as HTMLButtonElement;
    fireEvent.click(btn);
    expect((getBySelector('input[name="test"]') as HTMLInputElement).type).toEqual("password");
    expect((getBySelector('input[name="test"]') as HTMLInputElement).value).toEqual(value.value);
  });
});
