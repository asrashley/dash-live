import { buildQueries } from '@testing-library/preact';

const queryAllBySelector = (container, selector) => {
    return Array.from(container.querySelectorAll(selector));
};
const [queryBySelector, getAllBySelector, getBySelector, findAllBySelector, findBySelector] = buildQueries(
    queryAllBySelector,
    (container, selector) => `Found multiple elements from ${container} with selector: ${selector}`,
    (container, selector) => `Unable to find an element from ${container} with selector: ${selector}`,
);

export const bySelectorQueries = {
    queryBySelector,
    getAllBySelector,
    getBySelector,
    findAllBySelector,
    findBySelector
};
