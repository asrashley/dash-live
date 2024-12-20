import { describe, expect, test } from "vitest";

import { renderWithProviders } from "../test/renderWithProviders";
import { Card } from "./Card";

describe("Card", () => {
  test("should display Card", () => {
    const { container, queryBySelector } = renderWithProviders(
      <Card id="cid"><p>Hello World</p></Card>
    );
    expect(container.textContent).toMatch("Hello World");
    const elt = document.getElementById("cid");
    expect(elt).not.toBeNull();
    expect(elt.className).toEqual("card");
    expect(queryBySelector("img")).toBeNull();
  });

  test("should display Card with a heading", () => {
    function Header() {
      return <h2 id="head">My Header</h2>;
    }
    const { container, queryBySelector } = renderWithProviders(
      <Card id="cid" header={<Header />}
        ><p>Hello World</p></Card>
    );
    expect(container.textContent).toMatch("Hello World");
    const elt = document.getElementById("head");
    expect(elt).not.toBeNull();
    expect(elt.textContent).toEqual("My Header");
    expect(queryBySelector("img")).toBeNull();
  });

  test("should display Card with an image", () => {
    const image = {
      src: "test.png",
      alt: "My Image",
    };
    const { container, queryBySelector } = renderWithProviders(
      <Card id="cid" image={image}><p>Hello World</p></Card>
    );
    expect(container.textContent).toMatch("Hello World");
    const elt = queryBySelector("img");
    expect(elt).not.toBeNull();
    expect(elt.className).toEqual("card-img-top");
    expect(elt.getAttribute("src")).toEqual(image.src);
    expect(elt.getAttribute("alt")).toEqual(image.alt);
  });
});
