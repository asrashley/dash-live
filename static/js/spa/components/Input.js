import { html } from "htm/preact";

import { SelectOption } from "./SelectOption.js";

function RadioOption({name, selected, title, value}) {
    html`<div class="form-check">
      <input class="form-check-input" type="radio" name="${ name }"
             id="radio-${ name }-${ value }"
             value="${ value }" checked=${selected} />
      <label class="form-check-label"
             for="radio-${ name }-${ value }" >${ title }</label>
    </div>`;
}

function RadioInput({options}) {
    return options.map(opt => html`<${RadioOption} ...${opt} />`);
}

function SelectInput({className, options, value, ...props}) {
    return html`<select className="${className}" value=${value} ...${props}>
        ${options.map(opt => html`<${SelectOption} selected=${value === opt.value} ...${opt}/>`)}
    </select>`;
}

function DataListInput({className, name, options, ...props}) {
    return html`<input className="${className}" name="${name}" list="list-${ name }" ...${props} />
    <datalist id="list-${ name }">
    ${ options.map(opt => html`<option value="${opt.value}" selected=${opt.selected}>${opt.title}</option>`)}
    </datalist>`;
}

export function Input({className='', type, error, validation, value, title, options, prefix, datalist=false, name}) {
    const inputClass = type === 'checkbox' ? 'form-check-input' : type === 'select' ? 'form-select' :'form-control';
    const validationClass = error ? ' is-invalid' : validation === 'was-validated' ? ' is-valid': '';
    const inpProps = {
        name,
        type,
        className: `${ inputClass }${ validationClass } ${ className }`,
        title,
        id: `model-${ name }`,
        "aria-describedby": `field-${ name }`,
        "data-prefix": prefix,
    };
    if (type === 'checkbox') {
        inpProps.checked = value;
    } else {
        inpProps.value = value;
    }
    if (type === 'radio' || type === 'select' || datalist) {
        inpProps.options = options;
    }
    if (type === 'radio') {
        return html`<${RadioInput} ...${inpProps} />`;
    }
    if (type === 'select') {
        return html`<${SelectInput} ...${inpProps} />`;
    }
    if (datalist) {
        return html`<${DataListInput} ...${inpProps} />`;
    }
    return html`<input ...${inpProps} />`;
}