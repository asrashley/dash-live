import { html } from 'htm/preact';

export function Card({header, image, children, id}) {
  const topImg = image ? html`<img src=${ image.src } class="card-img-top" alt=${image.alt}>` : '';

  const cardHeader = header ? html`<div class="card-header">${ header }</div>` : '';
  return html`
    <div class="card" id=${id}>
      ${ topImg }
      ${ cardHeader }
      <div class="card-body">
        ${ children }
      </div>
    </div>
`;
}

