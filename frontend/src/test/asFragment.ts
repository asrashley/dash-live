
/*
 * Duplicates the @testing-library/preact asFragment(), for use in tests
 * that need to check snaphots of HTML text rather than the results of
 * calling render()
 */

export function elementAsFragment(container: HTMLElement): DocumentFragment {
    if (typeof document.createRange === 'function') {
        return document.createRange().createContextualFragment(container.innerHTML);
    }
    const template = document.createElement('template');
    template.innerHTML = container.innerHTML;
    return template.content;

}
