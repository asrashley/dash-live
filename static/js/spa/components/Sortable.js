import { html } from 'htm/preact';
import { Component } from "preact";

export class Sortable extends Component {
  constructor() {
    super();
    this.state = {
      draggingItem: undefined,
      draggingTarget: undefined,
      nearestItem: undefined,
      lastY: 0,
    };
  }

  findItem(id) {
    const { items, dataKey } = this.props;
    return items.value.find(i => `${i[dataKey]}` === id);
  }

  onDragStart = (e /* DragEvent */) => {
    const el = e.target.closest('[data-item-id]');
    el?.setAttribute('dragging', '');
    const item = this.findItem(el?.getAttribute('data-item-id'));
    this.setState({draggingItem: item});
  };

  onDrag = (e /* DragEvent*/) => {
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

  onDragEnd = (e /* DragEvent */) => {
    const el = e.target.closest('[data-item-id]');
    el?.removeAttribute('dragging');
    this.setState({
      nearestItem: undefined,
      draggingItem: undefined,
      draggingTarget: undefined,
    });
  };

  onDragEnter = (e /* DragEvent */) => {
    const nearestItem = e.target?.closest(`[data-item-id]`);
    this.setState({nearestItem});
    e.preventDefault();
  };

  onDragOver = (e /* DragEvent*/) => {
    this.setState({lastY: e.y});
    e.preventDefault();
  };

  onDrop = (e /* DragEvent */) => {
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

  itemProps(item) {
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
    const { Component, RenderItem, items } = this.props;
    return html`<${Component} onDragEnter=${this.onDragEnter} onDragOver=${this.onDragOver} onDrop=${this.onDrop}>
      ${items.value.map((item, index) => {
        const props = this.itemProps(item);
        return html`<${RenderItem} item=${item} key=${props.key} index=${index} ...${props} />`;
      })}
    <//>`;
  }
}
