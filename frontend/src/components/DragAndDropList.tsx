import { Component, type JSX } from "preact";
import { type ReadonlySignal } from "@preact/signals";
import log from 'loglevel';

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
  items: ReadonlySignal<object[]>;
  setItems: (items: object[]) => void;
}

interface SortableListState {
  draggingItem: object | undefined,
  draggingTarget: object | string | undefined,
  nearestItem: Element | undefined,
  lastY: number;
}

export class DragAndDropList extends Component<SortableListProps, SortableListState> {
  constructor() {
    super();
    this.state = {
      draggingItem: undefined,
      draggingTarget: undefined,
      nearestItem: undefined,
      lastY: 0,
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

  private findItem(id: string): object | undefined {
    const { items, dataKey } = this.props;
    return items.value.find(i => `${i[dataKey]}` === id);
  }

  private onDragStart = (e: DragEvent) => {
    const target = e.target as HTMLElement;
    const el = target.closest('[data-item-id]');
    el?.setAttribute('dragging', '');
    const item = this.findItem(el?.getAttribute('data-item-id'));
    log.debug('start dragging', item);
    this.setState({draggingItem: item});
  };

  private onDrag = (e: DragEvent) => {
    const { draggingItem, nearestItem, lastY } = this.state;
    e.preventDefault();
    if (!draggingItem) return;
    if (nearestItem) {
      const {top, height} = nearestItem.getBoundingClientRect();
      const isAfter = lastY > (top + height / 2);
      const after = isAfter ? nearestItem.nextElementSibling : nearestItem;
      const draggingTarget = this.findItem(after?.getAttribute('data-item-id')) || 'end';
      log.debug('drag event', draggingTarget);
      this.setState({draggingTarget});
    } else {
      log.debug('drag event - discarding target');
      this.setState({draggingTarget: undefined});
    }
  };

  private onDragEnd = (e: DragEvent) => {
    const el = (e.target as HTMLElement).closest('[data-item-id]');
    log.debug(`drag end data-item-id=${el?.getAttribute('data-item-id')}`);
    el?.removeAttribute('dragging');
    this.setState({
      nearestItem: undefined,
      draggingItem: undefined,
      draggingTarget: undefined,
    });
  };

  private onDragEnter = (ev: DragEvent) => {
    ev.preventDefault();
    if (!ev.target) {
      log.debug('drag enter with no event target!');
      return;
    }
    const nearestItem = (ev.target as HTMLElement).closest(`[data-item-id]`);
    log.debug(`drag enter data-item-id=${nearestItem?.getAttribute('data-item-id')}`);
    this.setState({nearestItem});
  };

  private onDragOver = (e: DragEvent) => {
    e.preventDefault();
    this.setState({lastY: e.y});
    log.debug(`drag over ${e.y}`);
  };

  private onDrop = (e: DragEvent) => {
    const { draggingItem, draggingTarget } = this.state;
    const { items, setItems } = this.props;

    e.preventDefault();
    if (!draggingItem) {
      log.debug('drop - no item being dragged');
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
}
