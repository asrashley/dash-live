import { describe, expect, test } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../test/renderWithProviders.js";
import { PrettyJson } from "./PrettyJson.js";

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
      html`<${PrettyJson} className="pretty" data=${data} />`
    );
    expect(asFragment()).toMatchSnapshot();
  });
});
