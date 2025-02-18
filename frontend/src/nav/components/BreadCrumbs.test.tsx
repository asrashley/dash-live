import { afterEach, describe, expect, test, vi } from "vitest";
import { Route, Switch, useLocation } from "wouter-preact";

import { renderWithProviders } from "../../test/renderWithProviders";
import { BreadCrumbs } from "./BreadCrumbs";
import { fireEvent } from "@testing-library/preact";

vi.mock('wouter-preact', async (importOriginal) => {
  return {
    ...await importOriginal(),
    useLocation: vi.fn(),
  };
});

describe("BreadCrumbs", () => {
  const useLocationMock = vi.mocked(useLocation);
  const setLocation = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  test.each<string>(["/multi-period-streams/.add", "/multi-period-streams", "/"])(
    "should display Breadcrumbs for %s",
    (path: string) => {
      useLocationMock.mockReturnValue([path, setLocation]);
      const { asFragment, getBySelector } = renderWithProviders(
        <div>
          <BreadCrumbs />
          <Switch>
            <Route path="/multi-period-streams/:stream">
              <div>edit MPS</div>
            </Route>
            <Route path="/multi-period-streams">
              <div>list MPS</div>
            </Route>
            <Route path="/">
              <div>home page</div>
            </Route>
          </Switch>
        </div>,
        {
          path,
        }
      );
      expect(asFragment()).toMatchSnapshot();
      if (path != '/') {
        const elt = getBySelector('#crumb_0 > a');
        fireEvent.click(elt);
        expect(setLocation).toHaveBeenCalledTimes(1);
        expect(setLocation).toHaveBeenCalledWith('/');
      }
    }
  );
});
