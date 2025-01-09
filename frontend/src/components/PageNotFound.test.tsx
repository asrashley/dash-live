import { describe, expect, test } from "vitest"
import { renderWithProviders } from "../test/renderWithProviders"
import { PageNotFound } from "./PageNotFound";

describe('PageNotFound component', () => {
    test('matches snapshot', () => {
        const { asFragment } = renderWithProviders(<PageNotFound />);
        expect(asFragment()).toMatchSnapshot();
    });
});