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
  className?: string;
  image?: CardImageProps;
}

export function Card({ className="", header, image, children, id }: CardProps) {
  const cardHeader = header ? <div className="card-header">{header}</div> : "";
  const clsName = `card ${className}`;
  return (
    <div className={clsName} id={id}>
      {image ? <CardImage {...image} /> : ""}
      {cardHeader}
      <div className="card-body">{children}</div>
    </div>
  );
}
