import { beforeEach, describe, expect, test } from "vitest";
import { signal } from "@preact/signals";
import { act } from "@testing-library/preact";

import { HorizontalScroller } from "./HorizontalScroller";
import { renderWithProviders } from "../../test/renderWithProviders";

describe("HorizontalScroller component", () => {
  const height = signal<string>("100px");
  const left = signal<number>(0);

  beforeEach(() => {
    height.value = "100px";
    left.value = 0;
  });

  test("renders children and applies initial styles", () => {
    const { getByText, getByTestId } = renderWithProviders(
      <HorizontalScroller height={height} width="500px" left={left}>
        <div>content</div>
      </HorizontalScroller>
    );

    const childrenContent = getByTestId("horizontal-scroll-children") as HTMLDivElement;
    getByText("content");
    expect(childrenContent.style.width).toBe("500px");
    expect(childrenContent.style.left).toBe("0px");
  });

  test.each<string>(["top", "bottom"])("scrolling %s bar updates children left and other bar", async (barName: string) => {
    const { findByTestId, getAllByTestId } = renderWithProviders(
      <HorizontalScroller height={height} width="500px" left={left} >
        <div>content</div>
      </HorizontalScroller>
    );

    const scrollBars = getAllByTestId("horizontal-scroll-bar") as HTMLDivElement[];
    expect(scrollBars.length).toBe(2);
    const bar = scrollBars[barName === "top" ? 0 : 1] as HTMLDivElement;

    await act(async () => {
      bar.scrollLeft = 30;
      const ev = new Event("scroll");
      Object.defineProperty(ev, "target", { value: bar, writable: false });
      bar.dispatchEvent(ev);
    });

    const childrenContent = await findByTestId("horizontal-scroll-children") as HTMLDivElement;
    expect(childrenContent.style.left).toBe("-30px");
    expect(left.value).toBe(30);
  });
});
