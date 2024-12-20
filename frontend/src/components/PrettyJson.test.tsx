import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { PrettyJson } from "./PrettyJson";

describe("PrettyJson", () => {
  const data = {
    hello: "world",
    number: 32,
    aBool: true,
    anArray: [
      "apple",
      "pear",
      {
        strawberry: "jam",
      },
    ],
    anObject: {
        james: 'bond',
    },
  };

  test("should match snapshot", () => {
    const { asFragment } = renderWithProviders(
      <PrettyJson className="pretty" data={data} />
    );
    expect(asFragment()).toMatchSnapshot();
  });
});
