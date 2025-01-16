import { beforeEach, describe, expect, test, vi } from "vitest";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { useCgiOptions, type UseCgiOptionsHook } from "../../hooks/useCgiOptions";
import { CgiOptionDescription } from "../../types/CgiOptionDescription";
import allCgiOptions from '../../test/fixtures/cgiOptions.json';

import { GenericParametersTable } from "./GenericParametersTable";

vi.mock("../../hooks/useCgiOptions");

describe('GenericParametersTable component', () => {
    const useCgiOptionsMock = vi.mocked(useCgiOptions);
    const allOptions = signal<CgiOptionDescription[]>([]);
    const useCgiOptionsHook: UseCgiOptionsHook = {
        allOptions,
        loaded: signal<boolean>(false),
        error: signal<string | null>(null),
      };

    beforeEach(() => {
        useCgiOptionsMock.mockReturnValue(useCgiOptionsHook);
        allOptions.value = structuredClone(allCgiOptions as CgiOptionDescription[]);
    });

    test('matches snapshot', () => {
        const { asFragment, getByText } = renderWithProviders(<GenericParametersTable />);
        allCgiOptions.forEach(({name, syntax}) => getByText(`${name}=${syntax}`));
        expect(asFragment()).toMatchSnapshot();
    });
});