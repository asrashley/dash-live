import { SelectOptionType } from "./SelectOptionType";

/* StaticInputProps represents all the properties of an <input> or <select>
element that don't change during the life of the element */

export interface StaticInputProps {
    allowReveal?: boolean;
    columns?: string[];
    className?: string;
    datalist_type?: 'text' | 'number';
    featured?: boolean;
    fullName: string;
    href?: string;
    link_title?: string;
    max?: number;
    min?: number;
    maxlength?: number;
    minlength?: number;
    multiple?: boolean;
    name: string;
    options?: SelectOptionType[];
    pattern?: string;
    placeholder?: string;
    prefix?: string;
    required?: boolean;
    rowClass?: string;
    shortName: string;
    spellcheck?: boolean;
    step?: number;
    title: string;
    text?: string;
    type: 'checkbox' | 'datalist' | 'email' | 'hidden' | 'multiselect' | 'number' | 'password' | 'select' | 'radio' | 'link' | 'text';
}