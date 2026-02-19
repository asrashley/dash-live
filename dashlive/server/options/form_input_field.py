from dataclasses import dataclass
from typing import AbstractSet, Any, NamedTuple, NotRequired, TypedDict

class FieldOptionJson(TypedDict):
    title: str
    value: str | int
    selected: NotRequired[bool]

@dataclass(slots=True)
class FieldOption:
    title: str
    value: str | int
    selected: bool

    def toJSON(self, pure: bool = False, exclude: AbstractSet[str] | None = None) -> FieldOptionJson:
        return {
            'title': self.title,
            'value': self.value,
            'selected': self.selected
        }

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
    fullName: str
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
    shortName: str
    spellcheck: NotRequired[bool]
    step: NotRequired[int]
    title: NotRequired[str]
    text: NotRequired[str]
    type: str  # 'checkbox', 'datalist', 'number', 'select', 'radio', 'link', 'hidden'
    value: Any
