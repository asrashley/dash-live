from typing import Any, NamedTuple, TypedDict

class FieldOption(NamedTuple):
    title: str
    value: str | int
    selected: bool

class FormInputContext(TypedDict):
    columns: tuple[str, str, str]
    className: str
    datalist: bool
    disabled: bool
    error: str
    href: str
    link_title: str
    max: int
    min: int
    maxlength: int
    minlength: int
    multiple: bool
    name: str
    options: list[FieldOption]
    pattern: str
    placeholder: str
    prefix: str
    required: bool
    rowClass: str
    spellcheck: bool
    step: int
    title: str
    text: str
    type: str  # 'checkbox', 'number', 'select', 'radio', 'link', 'hidden'
    value: Any
