import { html } from 'htm/preact';

function CardImage({src, alt}) {
  return html`<img src=${ src } class="card-img-top" alt=${alt} />`
}

export function Card({header, image, children, id}) {

  const cardHeader = header ? html`<div class="card-header">${ header }</div>` : '';
  return html`
    <div class="card" id=${id}>
      ${image && html`<${CardImage} ...${image} />`}
      ${ cardHeader }
      <div class="card-body">
        ${ children }
      </div>
    </div>
`;
}

