import { signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { act } from "@testing-library/preact";

import { ManifestLine } from "../types/ManifestLine";
import { renderWithProviders } from "../../test/renderWithProviders";
import { Manifest } from "./Manifest";
import { FakeEndpoint } from "../../test/FakeEndpoint";

describe('Manifest component', () => {
    const manifest = signal<ManifestLine[]>([]);
    let endpoint: FakeEndpoint;

    beforeEach(() => {
        endpoint = new FakeEndpoint('http://test.local');
        manifest.value = [];
    });

    afterEach(() => {
        vi.resetAllMocks();
    });

    test('matches snapshot for manifest with no errors', async () => {
        manifest.value = await fetchManifest(endpoint);
        const { asFragment, getAllByText } = renderWithProviders(<Manifest manifest={manifest} />);
        getAllByText("Big Buck Bunny", { exact: false });
        expect(asFragment()).toMatchSnapshot();
    });

    test('matches snapshot for manifest with errors', async () => {
        const lines = await fetchManifest(endpoint);
        for (let i=20; i < 30; ++i ){
            lines[i + 1].hasError = true;
        }
        lines[21].errors = ['AdaptationSet has an error'];
        for (let i=34; i < 38; ++i ){
            lines[i + 1].hasError = true;
        }
        lines[35].errors = ['InbandEventStream missing something'];
        manifest.value = lines;
        const { asFragment, getBySelector, getByText, getAllByText } = renderWithProviders(<Manifest manifest={manifest} />);
        getAllByText("Big Buck Bunny", { exact: false });
        getByText('AdaptationSet has an error');
        getByText('InbandEventStream missing something');
        lines.forEach(({hasError, line}) => {
            const row = getBySelector(`#mpd-line-${line}`);
            expect(row.classList.contains('error')).toEqual(hasError);
        });
        expect(asFragment()).toMatchSnapshot();
    });

    test("passes minHeight and maxHeight props to scroller component", async () => {
        const { getByTestId } = renderWithProviders(<Manifest manifest={manifest} minHeight={4} maxHeight={45} />);
        const container = getByTestId("horizontal-scroller-container") as HTMLDivElement;
        expect(container.style.height).toBe("4em");
        await act(async () => {
            manifest.value = await fetchManifest(endpoint);
        });
        expect(container.style.height).toBe("45em");
    });
});

async function fetchManifest(endpoint: FakeEndpoint): Promise<ManifestLine[]> {
    const data = await endpoint.fetchFixtureText('dash/vod/bbb/hand_made.mpd');
    const lines: ManifestLine[] = [];
    data.split('\n').forEach((text, idx) => {
        lines.push({
            text,
            line: idx + 1,
            errors: [],
            hasError: false,
        });
    });
    return lines;
}
