export interface SelectOptionType {
    value: string;
    selected?: boolean;
    title: string;
};

export interface RadioOptionType extends SelectOptionType {
    name: string;
    disabled?: boolean;
};

export interface MultiSelectOptionType {
    name: string;
    title: string;
    checked: boolean;
}