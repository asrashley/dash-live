import { SelectOptionType } from "./SelectOptionType";

export interface FormInputItem {
    columns?: string[];
    className?: string;
    datalist_type?: 'text' | 'number';
    error?: string;
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
    type: 'checkbox' | 'datalist' | 'hidden' | 'multiselect' | 'number' | 'password' | 'select' | 'radio' | 'link' | 'text';
}