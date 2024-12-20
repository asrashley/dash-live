import { vi, describe, expect, test } from "vitest";
import { fireEvent } from "@testing-library/preact";

import { renderWithProviders } from "../test/renderWithProviders";
import { DropDownMenu} from './DropDownMenu';

describe('DropDownMenu', () => {
    test("should display drop-down menu", () => {
        const menu = [{
            href: '#',
            onClick: vi.fn(),
            title: 'item one',
        },
        {
            href: '/two',
            onClick: vi.fn(),
            title: 'item two',
        }
        ];
        const { asFragment, getByTestId, queryBySelector } = renderWithProviders(
          <DropDownMenu menu={menu} />
        );
        expect((getByTestId('ddi_0') as HTMLElement).textContent).toEqual('item one');
        expect((getByTestId('ddi_1') as HTMLElement).textContent).toEqual('item two');

        const elt = queryBySelector('.dropdown > a');
        expect(elt).not.toBeNull();
        expect(elt.className).toEqual('btn btn-secondary dropdown-toggle');
        expect(asFragment()).toMatchSnapshot();

        fireEvent.click(elt);
        expect(elt.className).toEqual('btn btn-secondary dropdown-toggle show');
        fireEvent.click((getByTestId('ddi_0') as HTMLElement).querySelector('a'));
        expect(menu[0].onClick).toHaveBeenCalledTimes(1);
        expect(menu[1].onClick).not.toHaveBeenCalled();
        expect(elt.className).toEqual('btn btn-secondary dropdown-toggle');

        fireEvent.click(elt);
        fireEvent.click((getByTestId('ddi_1') as HTMLElement).querySelector('a'));
        expect(menu[0].onClick).toHaveBeenCalledTimes(1);
        expect(menu[1].onClick).toHaveBeenCalledTimes(1);
      });

});