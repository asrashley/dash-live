import { afterEach, describe, expect, test, vi } from "vitest";
import { renderWithProviders } from "../../test/renderWithProviders";
import { PeriodOrder } from "./PeriodOrder";
import { fireEvent } from "@testing-library/preact";

describe("PeriodOrder component", () => {
  const addPeriod = vi.fn();
  const deletePeriod = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", () => {
    const { asFragment } = renderWithProviders(
      <PeriodOrder addPeriod={addPeriod} deletePeriod={deletePeriod} />
    );
    expect(asFragment()).toMatchSnapshot();
  });

  test('add a period', () => {
    const { getByText } = renderWithProviders(
        <PeriodOrder addPeriod={addPeriod} deletePeriod={deletePeriod} />
      );
      const elt = getByText('Add another Period') as HTMLElement;
      fireEvent.click(elt);
      expect(addPeriod).toHaveBeenCalledTimes(1);
      expect(deletePeriod).not.toHaveBeenCalled();
  });

  test('delete a period', () => {
    const { getByText } = renderWithProviders(
        <PeriodOrder addPeriod={addPeriod} deletePeriod={deletePeriod} />
      );
      const elt = getByText('Delete Period') as HTMLElement;
      fireEvent.click(elt);
      expect(addPeriod).not.toHaveBeenCalled();
      expect(deletePeriod).toHaveBeenCalledTimes(1);
  });
});
