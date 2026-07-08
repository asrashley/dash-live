import { useSignal, useSignalEffect, type Signal } from "@preact/signals";
import { scrollBarContainer, scrollBar } from "./HorizontalScrollBar.module.css";

export interface HorizontalScrollBarProps {
    left: Signal<number>;
    width: string;
    onScroll: (left: number) => void;
}

export function HorizontalScrollBar({ left, width, onScroll }: HorizontalScrollBarProps) {
    const outerDiv = useSignal<HTMLDivElement|null>(null);
    const setRef = (div: HTMLDivElement|null) => {
        outerDiv.value = div;
    };
    const onScrollHandler = (ev: Event) => {
        const div = ev.target as HTMLDivElement;
        onScroll(div.scrollLeft);
    };

    // update scrollLeft when left signal changes
    useSignalEffect(() => {
        const div = outerDiv.value;
        if (div) {
            div.scrollLeft = left.value;
        }
    });

    return (
        <div
            className={scrollBarContainer}
            data-testid="horizontal-scroll-bar"
            onScroll={onScrollHandler}
            ref={setRef}
        >
            <div className={scrollBar} style={{ width }} />
        </div>);
}

