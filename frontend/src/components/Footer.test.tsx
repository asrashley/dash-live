import { afterAll, beforeAll, describe, expect, test, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { Footer } from "./Footer";

describe('Footer component', () => {
    beforeAll(() => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date('2025-01-01T00:00:00Z'));
    });

    afterAll(() => {
        vi.restoreAllMocks();
        vi.useRealTimers();
    });

    test('matches snapshot', () => {
        const { asFragment, getByText } = renderWithProviders(<Footer />);
        getByText(new Date().getFullYear().toString(), { exact: false });
        getByText(window["_GIT_HASH_"]);
        expect(asFragment()).toMatchSnapshot();
    });
});