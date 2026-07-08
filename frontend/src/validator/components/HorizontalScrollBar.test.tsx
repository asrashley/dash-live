import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { signal } from "@preact/signals";
import { renderWithProviders } from "../../test/renderWithProviders";

import { HorizontalScrollBar } from "./HorizontalScrollBar";
import { act } from "@testing-library/preact";

describe("HorizontalScrollBar component", () => {
    const left = signal(0);
    const onScroll = vi.fn();

    beforeEach(() => {
        left.value = 0;
    });

    afterEach(() => {
        vi.resetAllMocks();
    });

    test("renders inner bar with provided width", () => {
        const { getByTestId } = renderWithProviders(
            <HorizontalScrollBar left={left} width="600px" onScroll={onScroll} />
        );

        const outer = getByTestId("horizontal-scroll-bar") as HTMLDivElement;
        const inner = outer.firstElementChild as HTMLDivElement;
        expect(inner.style.width).toEqual("600px");
        expect(outer.scrollLeft).toEqual(0);
    });

    test("calls onScroll when the container is scrolled", () => {
        const { getByTestId } = renderWithProviders(
            <HorizontalScrollBar left={left} width="500px" onScroll={onScroll} />
        );

        const outer = getByTestId("horizontal-scroll-bar") as HTMLDivElement;
        act(() => {
            outer.scrollLeft = 10;
            const ev = new Event("scroll");
            Object.defineProperty(ev, "target", { value: outer, writable: false });
            outer.dispatchEvent(ev);
        });
        expect(onScroll).toHaveBeenCalledTimes(1);
        expect(onScroll).toHaveBeenCalledWith(10);
    });

    test("updates scrollLeft when left signal changes", () => {
        const { getByTestId } = renderWithProviders(
            <HorizontalScrollBar left={left} width="400px" onScroll={onScroll} />
        );

        const outer = getByTestId("horizontal-scroll-bar") as HTMLDivElement;
        expect(outer.scrollLeft).toEqual(0);

        act(() => {
            left.value = 25;
        });

        expect(outer.scrollLeft).toEqual(25);
        expect(onScroll).not.toHaveBeenCalled();
    });
});
