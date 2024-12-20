import { Component, type JSX } from "preact";
import { type Signal } from "@preact/signals";

export type RenderItemProps = {
  item: object;
  index: number;
  key: string;
  draggable: boolean;
  className: string;
  'data-item-id': string;
  onDragStart: (e: DragEvent) => void;
  onDrag: (e: DragEvent) => void;
  onDragEnd: (e: DragEvent) => void;
};

export interface SortableListProps {
  RenderItem: (props: RenderItemProps) => JSX.Element;
  dataKey: string;
  items: Signal<object[]>;
  setItems: (items: object[]) => void;
}

interface SortableListState {
  draggingItem: object | undefined,
  draggingTarget: object | string | undefined,
  nearestItem: Element | undefined,
  lastY: number;
}

export class SortableList extends Component<SortableListProps, SortableListState> {
  constructor() {
    super();
    this.state = {
      draggingItem: undefined,
      draggingTarget: undefined,
      nearestItem: undefined,
      lastY: 0,
    };
  }

  findItem(id: string): object | undefined {
    const { items, dataKey } = this.props;
    return items.value.find(i => `${i[dataKey]}` === id);
  }

  onDragStart = (e: DragEvent) => {
    const target = e.target as HTMLElement;
    const el = target.closest('[data-item-id]');
    el?.setAttribute('dragging', '');
    const item = this.findItem(el?.getAttribute('data-item-id'));
    this.setState({draggingItem: item});
  };

  onDrag = (e: DragEvent) => {
    const { draggingItem, nearestItem, lastY } = this.state;
    e.preventDefault();
    if (!draggingItem) return;
    if (nearestItem) {
      const {top, height} = nearestItem.getBoundingClientRect();
      const isAfter = lastY > (top + height / 2);
      const after = isAfter ? nearestItem.nextElementSibling : nearestItem;
      const draggingTarget = this.findItem(after?.getAttribute('data-item-id')) || 'end';
      this.setState({draggingTarget});
    } else {
      this.setState({draggingTarget: undefined});
    }
  };

  onDragEnd = (e: DragEvent) => {
    const el = (e.target as HTMLElement).closest('[data-item-id]');
    el?.removeAttribute('dragging');
    this.setState({
      nearestItem: undefined,
      draggingItem: undefined,
      draggingTarget: undefined,
    });
  };

  onDragEnter = (ev: DragEvent) => {
    ev.preventDefault();
    if (!ev.target) {
      return;
    }
    const nearestItem = (ev.target as HTMLElement).closest(`[data-item-id]`);
    this.setState({nearestItem});
  };

  onDragOver = (e: DragEvent) => {
    this.setState({lastY: e.y});
    e.preventDefault();
  };

  onDrop = (e: DragEvent) => {
    const { draggingItem, draggingTarget } = this.state;
    const { items, setItems } = this.props;

    e.preventDefault();
    if (!draggingItem) {
      return;
    }

    let ref = items.value.findIndex((item) => item === draggingTarget);
    const newItems = items.value.filter(t => t !== draggingItem);
    if (ref === -1) {
      newItems.splice(items.value.length, 0, draggingItem);
    } else {
      if (items.value.indexOf(draggingItem) < ref) {
        ref--;
      }
      newItems.splice(ref, 0, draggingItem);
    }
    setItems(newItems);
  };

  private itemProps(item: object, index: number): RenderItemProps {
    const { dataKey, items } = this.props;
    const { draggingTarget } = this.state;

    const id = item[dataKey];
    const lastItem = items.value[items.value.length - 1];
    let className = '';

    if (draggingTarget === item) {
      className = 'dragging-target-start';
    } else if(draggingTarget === 'end' && item === lastItem) {
      className = 'dragging-target-end';
    }

    return {
      item,
      index,
      key: `${id}`,
      draggable: true,
      className,
      'data-item-id': id,
      onDragStart: this.onDragStart,
      onDrag: this.onDrag,
      onDragEnd: this.onDragEnd,
    };
  }

  render() {
    const { RenderItem, items } = this.props;
    return <ul onDragEnter={this.onDragEnter} onDragOver={this.onDragOver} onDrop={this.onDrop}>
      {items.value.map((item, index) => {
        const props = this.itemProps(item, index);
        // eslint-disable-next-line react/jsx-key
        return <RenderItem {...props} />;
      })}
    </ul>;
  }
}
