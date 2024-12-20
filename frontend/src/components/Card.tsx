import { type ComponentChildren } from "preact";

export interface CardImageProps {
  src: string;
  alt?: string;
}

function CardImage({ src, alt }: CardImageProps) {
  return <img src={src} className="card-img-top" alt={alt} />;
}

export interface CardProps {
  id: string;
  header?: string | ComponentChildren;
  children?: ComponentChildren;
  image?: CardImageProps;
}

export function Card({ header, image, children, id }: CardProps) {
  const cardHeader = header ? <div className="card-header">{header}</div> : "";
  return (
    <div className="card" id={id}>
      {image ? <CardImage {...image} /> : ""}
      {cardHeader}
      <div className="card-body">{children}</div>
    </div>
  );
}
