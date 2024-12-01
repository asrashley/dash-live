import { html } from "htm/preact";
import { useCallback } from "preact/hooks";

import { SelectOption } from "./SelectOption.js";

function RadioOption({name, selected, title, value, disabled, setValue}) {
    const onClick = useCallback(() => {
        setValue(name, value);
    }, [name, setValue, value]);
    return html`<div class="form-check">
      <input class="form-check-input" type="radio" name="${ name }"
             id="radio-${ name }-${ value }" onClick=${onClick}
             value="${ value }" checked=${selected} disabled=${disabled} />
      <label class="form-check-label"
             for="radio-${ name }-${ value }" >${ title }</label>
    </div>`;
}

function RadioInput({options, ...props}) {
    return html`<div>${options.map(opt => html`<${RadioOption} key=${opt.value} ...${props} ...${opt} />`)}</div>`;
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

export function Input({className='', type, name, value, setValue, error, validation, title, options,
     datalist=false}) {
    const inputClass = type === 'checkbox' ? 'form-check-input' : type === 'select' ? 'form-select' :'form-control';
    const validationClass = error ? ' is-invalid' : validation === 'was-validated' ? ' is-valid': '';
    const inpProps = {
        name,
        type,
        className: `${ inputClass }${ validationClass } ${ className }`,
        title,
        id: `model-${ name }`,
        value: value.value,
        "aria-describedby": `field-${ name }`,
        onInput: (ev) => {
            const { target } = ev;
            setValue(name, type === 'checkbox' ? target.checked : target.value);
        },
    };
    if (type === 'checkbox') {
        inpProps.checked = value.value === true || value.value === "1";
    }
    if (type === 'radio' || type === 'select' || datalist) {
        inpProps.options = options;
    }
    if (type === 'radio') {
        return html`<${RadioInput} setValue=${setValue} ...${inpProps} />`;
    }
    if (type === 'select') {
        return html`<${SelectInput} ...${inpProps} />`;
    }
    if (datalist) {
        return html`<${DataListInput} ...${inpProps} />`;
    }
    return html`<input ...${inpProps} />`;
}