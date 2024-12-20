import { describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";
import { fireEvent } from '@testing-library/preact'

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { ModalDialog } from './ModalDialog';

describe('ModalDialog component', () => {
	test('calls onCancel() when close button is clicked', () => {
		const onCancel = vi.fn();
		const {getByRole, getByText, getBySelector} = renderWithProviders(
			html`<${ModalDialog} title="ModalDialog Test" onClose=${onCancel} />`);
        getByText("ModalDialog Test");
		expect(getByRole('dialog').getAttribute('id')).toEqual('dialog-box');
		fireEvent.click(getBySelector('button[aria-label="Close"]'));
		expect(onCancel).toHaveBeenCalled();
	});

	test('the id can be modified', () => {
		const onCancel = vi.fn();
		const {getByText, getByRole} = renderWithProviders(
			html`<${ModalDialog} title="ModalDialog Test" id="testid" onClose=${onCancel} />`);
		getByText("ModalDialog Test");
		expect(getByRole('dialog').getAttribute('id')).toEqual('testid');
	});

	test('children rendered', () => {
		const onCancel = vi.fn();
		const result = renderWithProviders(
			html`<${ModalDialog} title="ModalDialog Test" onClose=${onCancel}>
				<div><p>This is the dialog body</p></div>
			<//>`);
		result.getByText("This is the dialog body");
	});

	test('footer is rendered', () => {
		const onCancel = vi.fn();
		const footer = html`<div><p>This is a footer</p></div>`;
		const {getByText} = renderWithProviders(
			html`<${ModalDialog} title="ModalDialog Test" footer=${footer} onClose=${onCancel} />`);
		getByText("This is a footer");
	});

	test('matches snapshot', () => {
		const onCancel = vi.fn();
		const footer = html`<div><p>This is the dialog footer</p></div>`;
		const { asFragment } = renderWithProviders(
			html`<${ModalDialog} title="ModalDialog Test" onClose=${onCancel} footer=${footer}>
				<div><p>This is the dialog body</p></div>
			</ModalDialog>`);
		expect(asFragment()).toMatchSnapshot();
	});
});