from typing import Any, NamedTuple, NotRequired, TypedDict

class FieldOption(NamedTuple):
    title: str
    value: str | int
    selected: bool

class ColumnClassNames(NamedTuple):
    left: str
    middle: str
    right: str

class FormInputContext(TypedDict):
    columns: NotRequired[ColumnClassNames]
    className: NotRequired[str]
    datalist_type: NotRequired[str]
    disabled: NotRequired[bool]
    error: NotRequired[str]
    featured: NotRequired[bool]
    href: NotRequired[str]
    link_title: NotRequired[str]
    max: NotRequired[int]
    min: NotRequired[int]
    maxlength: NotRequired[int]
    minlength: NotRequired[int]
    multiple: NotRequired[bool]
    name: str
    options: NotRequired[list[FieldOption]]
    pattern: NotRequired[str]
    placeholder: NotRequired[str]
    prefix: NotRequired[str]
    required: NotRequired[bool]
    rowClass: NotRequired[str]
    spellcheck: NotRequired[bool]
    step: NotRequired[int]
    title: NotRequired[str]
    text: NotRequired[str]
    type: str  # 'checkbox', 'datalist', 'number', 'select', 'radio', 'link', 'hidden'
    value: Any
