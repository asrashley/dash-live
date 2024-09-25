/* globals bootstrap */
/* jshint esversion: 11 */

export function enableTooltips() {
    const tooltipTriggerList = [
        ...document.querySelectorAll('[data-bs-toggle="tooltip"]'),
    ];
    tooltipTriggerList.forEach(
        tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}
