import { signal } from "@preact/signals";
import { beforeEach, describe, expect, test } from "vitest";
import { CodecInformation } from "../types/CodecInformation";
import { renderWithProviders } from "../../test/renderWithProviders";
import { CodecsTable } from "./CodecsTable";
import { exampleCodecs } from "../../test/fixtures/exampleCodecs";

describe("CodecsTable component", () => {
  const codecs = signal<CodecInformation[]>([]);

  beforeEach(() => {
    codecs.value = structuredClone(exampleCodecs);
  });

  test('matches snapshot', () => {
    const { asFragment, getByText, getBySelector } = renderWithProviders(<CodecsTable codecs={codecs} />);
    codecs.value.forEach(item => {
        getByText(item.codec);
        item.details.forEach(det => {
            det.details.forEach(line => getByText(line));
        });
    });
    expect(getBySelector('table').classList.contains('d-none')).toEqual(false);
    expect(asFragment()).toMatchSnapshot();
  });

  test('displays error', () => {
    codecs.value[0].details[0].error = 'an error message';
    const { getByText } = renderWithProviders(<CodecsTable codecs={codecs} />);
    getByText('an error message');
  });

  test('hides table when there are no codecs', () => {
    codecs.value = [];
    const { getBySelector } = renderWithProviders(<CodecsTable codecs={codecs} />);
    expect(getBySelector('table').classList.contains('d-none')).toEqual(true);
  });
});
