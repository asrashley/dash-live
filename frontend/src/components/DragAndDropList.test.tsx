import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { createEvent, fireEvent } from "@testing-library/preact";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../test/renderWithProviders";
import { RenderItemProps, DragAndDropList } from "./DragAndDropList";

type ItemType = {
  pk: number;
  title: string;
};

function RenderItem({ item, index, ...props }: RenderItemProps) {
  const row = item as ItemType;
  return (
    <li {...props}>
      {index}: {row.title}
    </li>
  );
}

function createDragOver(elt: HTMLElement, y: number): DragEvent {
    const dragOver = createEvent.dragOver(elt, {
    y,
    target: { y },
    });
    dragOver['y'] = y;
    return dragOver as DragEvent;
}

describe("DragAndDropList component", () => {
  const items = signal<ItemType[]>([]);
  const setItems = vi.fn();

  beforeEach(() => {
    items.value = [
      {
        pk: 1,
        title: "Item One",
      },
      {
        pk: 2,
        title: "Item Two",
      },
      {
        pk: 3,
        title: "Item Three",
      },
      {
        pk: 4,
        title: "Item Four",
      },
    ];
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("matches snapshot", () => {
    const { asFragment } = renderWithProviders(
      <DragAndDropList
        items={items}
        RenderItem={RenderItem}
        dataKey="pk"
        setItems={setItems}
      />
    );
    expect(asFragment()).toMatchSnapshot();
  });

  test("can drag and drop an item", () => {
    const { getAllBySelector } = renderWithProviders(
      <DragAndDropList
        items={items}
        RenderItem={RenderItem}
        dataKey="pk"
        setItems={setItems}
      />
    );
    const [one, two, three, four] = items.value;
    const listItems = getAllBySelector("li");
    const boxes = listItems.map((elt) => elt.getBoundingClientRect());

    fireEvent.dragStart(listItems[0]);
    fireEvent.dragEnter(listItems[1]);
    fireEvent.drag(listItems[0]);
    let dragOver = createDragOver(listItems[1], boxes[1].top + 2);
    expect(dragOver.y).toBeDefined();
    fireEvent(listItems[1], dragOver);
    fireEvent.drag(listItems[0]);
    fireEvent.dragEnter(listItems[2]);
    fireEvent.drag(listItems[0]);
    dragOver = createDragOver(listItems[2], boxes[2].top + 2);
    fireEvent(listItems[2], dragOver);
    fireEvent.drag(listItems[0]);
    expect(setItems).not.toHaveBeenCalled();
    fireEvent.drop(listItems[2]);
    fireEvent.dragEnd(listItems[0]);
    expect(setItems).toHaveBeenCalledTimes(1);
    expect(setItems).toHaveBeenCalledWith([two, three, one, four]);
  });
});
