import { type ComponentChildren } from "preact"
import { useComputed, type Signal } from "@preact/signals";
import { useCallback } from "preact/hooks"

import * as styles from "./HorizontalScroller.module.css";
import { HorizontalScrollBar } from "./HorizontalScrollBar";

export interface HorizontalScrollerProps {
    children: ComponentChildren;
    left: Signal<number>;
    height: Signal<string>;
    width: string;
}

export function HorizontalScroller({ children, left, height, width }: HorizontalScrollerProps) {
    const childrenStyle = useComputed<string>(() => `left: -${left.value}px; width: ${width};`);
    const containerStyle = useComputed<string>(() => `height: ${height.value};`);

    const onScroll = useCallback((newLeft: number) => {
        left.value = newLeft;
    }, [left]);

    return (
        <div className={styles.horizontalScroller}>
            <HorizontalScrollBar left={left} width={width} onScroll={onScroll} />
            <div className={styles.childrenContainer} data-testid="horizontal-scroller-container"
                style={containerStyle}
            >
                <div className={styles.childrenContent} style={childrenStyle} data-testid="horizontal-scroll-children">
                    {children}
                </div>
            </div>
            <HorizontalScrollBar left={left} width={width} onScroll={onScroll} />
        </div>
    )
}