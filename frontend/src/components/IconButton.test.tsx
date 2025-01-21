import { fireEvent } from "@testing-library/preact";
import { describe, expect, test, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { IconButton } from "./IconButton";

describe('IconButton', () => {
    test('renders an enabled icon button', () => {
      const onClick = vi.fn();
      const { getBySelector } = renderWithProviders(
        <IconButton name="snow3" onClick={onClick} />
      );
      fireEvent.click(getBySelector('a'));
      expect(onClick).toHaveBeenCalled();
    });

    test('renders a disabled icon button', () => {
      const onClick = vi.fn();
      const { getBySelector } = renderWithProviders(
        <IconButton name="snow3" onClick={onClick} className="hello" disabled />
      );
      expect(getBySelector('a').className.trim()).equals('disabled hello');
      fireEvent.click(getBySelector('a'));
      expect(onClick).not.toHaveBeenCalled();
    });
  });