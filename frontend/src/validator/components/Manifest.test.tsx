import { signal } from "@preact/signals";
import { beforeEach, describe, expect, test } from "vitest";

import { ManifestLine } from "../types/ManifestLine";
import { renderWithProviders } from "../../test/renderWithProviders";
import { Manifest } from "./Manifest";
import { FakeEndpoint } from "../../test/FakeEndpoint";

describe('Manifest component', () => {
    const manifest = signal<ManifestLine[]>([]);
    let endpoint: FakeEndpoint;

    beforeEach(() => {
        endpoint = new FakeEndpoint('http://test.local');
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
