import { type ComponentChildren } from "preact";
import { routeMap } from "@dashlive/routemap";
import { Card, type CardProps } from "./Card";

export interface ErrorCardProps {
  id: string;
  header: CardProps["header"];
  children: ComponentChildren
}

export function ErrorCard({id, header, children}: ErrorCardProps) {
  const imageSrc = routeMap.images.url({ filename: "sad-puppy-dog.svg" });
  return (
    <Card
      id={id}
      className="m-3"
      header={header}
    >
      <div className="d-flex flex-row mb-3">
        <div>
          <img
            src={imageSrc}
            alt="Vector image of a dog looking sad"
            className="not-found-img"
          />
          <a
            className="fs-6 link-opacity-50"
            href="https://www.wannapik.com/vectors/88"
          >
            Image designed by Wannapik
          </a>
        </div>
        <div>
          {children}
        </div>
      </div>
    </Card>
  );
}
