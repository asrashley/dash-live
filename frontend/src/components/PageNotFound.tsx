import { routeMap, uiRouteMap } from "@dashlive/routemap";
import { Card } from "./Card";

export function PageNotFound() {
  const imageSrc = routeMap.images.url({ filename: "sad-puppy-dog.svg" });
  return (
    <Card
      id="page-not-found"
      className="m-3"
      header="Sorry I don't know about this page"
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
          <p className="fs-3">
            This page might have moved, or it might be a bug in this site.
          </p>
          <p className="fs-4">
            Probably a good idea to{" "}
            <a href={uiRouteMap.home.url()} className="link link-underline-light">
              return to the home page
            </a>
            .
          </p>
        </div>
      </div>
    </Card>
  );
}
