import { buildQueries, FindAllBy, FindBy, GetAllBy, GetBy, QueryBy } from '@testing-library/preact';

const queryAllBySelector = (container: HTMLElement, selector: string): HTMLElement[] => {
    return Array.from(container.querySelectorAll(selector));
};

const [queryBySelector, getAllBySelector, getBySelector, findAllBySelector, findBySelector] = buildQueries(
    queryAllBySelector,
    (container, selector) => `Found multiple elements from ${container} with selector: ${selector}`,
    (container, selector) => `Unable to find an element from ${container} with selector: ${selector}`,
);

export interface BySelectorQueryFunctions {
    queryBySelector: QueryBy<[string]>,
    getAllBySelector: GetAllBy<[string]>,
    getBySelector: GetBy<[string]>,
    findAllBySelector: FindAllBy<[string]>,
    findBySelector:  FindBy<[string]>,
}

export const bySelectorQueries: BySelectorQueryFunctions = {
    queryBySelector,
    getAllBySelector,
    getBySelector,
    findAllBySelector,
    findBySelector
};
