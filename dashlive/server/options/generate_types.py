#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dataclasses import InitVar, dataclass, field
from operator import attrgetter
from pathlib import Path
import re
from typing import Any, ClassVar

from dashlive.drm.system import DrmSystem

from .all_options import ALL_OPTIONS
from .dash_option import DashOption

@dataclass
class DashOptionTypeHint:
    name: str
    short: str
    cgi: str
    py_type: str
    ts_type: str
    default: InitVar[Any] = None
    factory: InitVar[str | None] = None
    py_default: str = field(init=False)

    def __post_init__(self, default: Any, factory: str | None) -> None:
        py_default: str = ''
        if factory is not None:
            py_default = f' = field(default_factory={factory})'
        elif default is not None:
            if isinstance(default, list):
                if len(default) > 0:
                    py_default = f' = field(default_factory=lambda: {default} )'
                else:
                    py_default = ' = field(default_factory=list)'
            elif isinstance(default, str):
                py_default = f' = field(default="{default}")'
            else:
                py_default = f" = {default}"
        else:
            if self.py_type.startswith('list'):
                py_default = ' = field(default_factory=list)'
            elif 'None' in self.py_type:
                py_default = ' = None'
        self.py_default = py_default

    def to_python_hint(self, form: str) -> str:
        """
        Generates the parameter name, type hint and its default value.
        :form: one of "name", "short" or "cgi"
        """
        assert form in {"name", "short", "cgi"}
        name: str = getattr(self, form)
        if form != "name" and "OptionsType" in self.py_type:
            return f'{name}: {form.title()}{self.py_type}{self.py_default}'

        return f'{name}: {self.py_type}{self.py_default}'


class OptionsTypesGenerator:
    @staticmethod
    def python_type_from_value(value: Any) -> str:
        if value is None:
            return 'str | None'
        if isinstance(value, bool):
            return 'bool'
        if isinstance(value, int):
            return 'int'
        if isinstance(value, float):
            return 'float'
        if isinstance(value, list):
            if len(value) > 0:
                return f"list[{OptionsTypesGenerator.guess_python_type(value[0])}]"
            return 'list'
        return 'Any'

    @staticmethod
    def guess_python_type(opt: DashOption) -> str:
        hint = opt.python_type_hint()
        if hint is not None:
            return hint
        value: Any = ''
        if opt.cgi_choices:
            value = opt.cgi_choices[0]
            if isinstance(value, tuple):
                items: set[str] = set()
                for it in value:
                    if isinstance(it, tuple):
                        items.add(OptionsTypesGenerator.python_type_from_value(it[1]))
                    else:
                        items.add(OptionsTypesGenerator.python_type_from_value(it))
                return f"{'| '.join(items)}"
        if value is None:
            value = 'none'
        value = opt.from_string(value)
        return OptionsTypesGenerator.python_type_from_value(value)

    @staticmethod
    def typescript_type_from_value(value: Any) -> str:
        if value is None:
            return 'string | null | undefined'
        if isinstance(value, bool):
            return 'boolean'
        if isinstance(value, (int, float)):
            return 'number'
        if isinstance(value, list):
            if len(value) > 0:
                return f"{OptionsTypesGenerator.guess_python_type(value[0])}[]"
            return 'unknown[]'
        return 'unknown'

    PYTHON_TO_TS_TYPES: ClassVar[dict[str, str]] = {
        "int": "number",
        "float": "number",
        "bool": "boolean",
        "str": "string",
        "None": "null",
        "datetime.datetime": "Date",
        "tuple": "unknown",
    }
    PY_TO_TS_RE = re.compile(r'(\s*)([A-Za-z.]+)($|,|\s|\[)')  # '|'.join([f"({t})" for t in PYTHON_TO_TS_TYPES.keys()]))

    @staticmethod
    def python_to_ts(m: re.Match[str]) -> str:
        try:
            ts_type: str = OptionsTypesGenerator.PYTHON_TO_TS_TYPES[m.group(2)]
            return f"{m.group(1)}{ts_type}{m.group(3)}"
        except KeyError:
            return m.group(0)

    @staticmethod
    def translate_tuple(m: re.Match[str]) -> str:
        fields: str = re.sub(OptionsTypesGenerator.PY_TO_TS_RE, OptionsTypesGenerator.python_to_ts, m.group(1))
        return f"[{fields}]"

    @staticmethod
    def guess_typescript_type(opt: DashOption) -> str:
        hint = opt.python_type_hint()
        if hint is not None:
            if hint.startswith('list['):
                hint = f"{hint[5:-1]}[]"
            hint = re.sub(r"tuple\[([^]]+)\]", OptionsTypesGenerator.translate_tuple, hint)
            hint = re.sub(OptionsTypesGenerator.PY_TO_TS_RE, OptionsTypesGenerator.python_to_ts, hint)
            return hint
        value: Any = ''
        if opt.cgi_choices:
            value = opt.cgi_choices[0]
            if isinstance(value, tuple):
                items: set[str] = {OptionsTypesGenerator.typescript_type_from_value(v) for v in value}
                return '| '.join(items)
        if value is None:
            value = 'none'
        value = opt.from_string(value)
        return OptionsTypesGenerator.typescript_type_from_value(value)

    @classmethod
    def guess_options_container_types(cls) -> tuple[list[DashOptionTypeHint], dict[str, list[DashOptionTypeHint]]]:
        primary_options: list[DashOptionTypeHint] = []
        sub_options: dict[str, list[DashOptionTypeHint]] = {}
        for opt in ALL_OPTIONS:
            if opt.prefix:
                name: str = f"{opt.prefix.title()}OptionsType"
                sub: list[DashOptionTypeHint]
                try:
                    sub = sub_options[name]
                except KeyError:
                    sub = []
                    sub_options[name] = sub
                    primary_options.append(DashOptionTypeHint(
                        name=opt.prefix,
                        short=opt.prefix,
                        cgi=opt.prefix,
                        default=None,
                        factory=name,
                        py_type=name,
                        ts_type=name))
                sub.append(DashOptionTypeHint(
                    name=opt.full_name,
                    short=opt.short_name,
                    cgi=opt.cgi_name,
                    default=opt.default_value(),
                    py_type=cls.guess_python_type(opt),
                    ts_type=cls.guess_typescript_type(opt)))
            else:
                primary_options.append(DashOptionTypeHint(
                    name=opt.full_name,
                    short=opt.short_name,
                    cgi=opt.cgi_name,
                    default=opt.default_value(),
                    py_type=cls.guess_python_type(opt),
                    ts_type=cls.guess_typescript_type(opt)))

        primary_options.sort(key=attrgetter('name'))
        for key in sub_options.keys():
            sub_options[key].sort(key=attrgetter('name'))
        return (primary_options, sub_options,)

    @classmethod
    def create_options_container_types_files(cls, py_dest: Path, ts_dest: Path) -> None:
        primary_options, sub_options = cls.guess_options_container_types()
        cls.create_python_types_file(py_dest, primary_options, sub_options)
        cls.create_typescript_types_file(ts_dest, primary_options, sub_options)

    @classmethod
    def create_python_types_file(cls,
                                 py_dest: Path,
                                 primary_options: list[DashOptionTypeHint],
                                 sub_options: dict[str, list[DashOptionTypeHint]]) -> None:
        print(f"Creating {py_dest}")
        with py_dest.open('wt', encoding='utf-8') as dest:
            dest.write('# this file is auto-generated, do not edit!\n')
            dest.write('# to re-generate this file, use the command:\n')
            dest.write('# uv run -m dashlive.server.options.generate_types\n\n')
            dest.write('import datetime\n')
            dest.write('from dataclasses import dataclass, field\n')
            dest.write('from .options_group import OptionsGroup\n\n')
            for name, options in sub_options.items():
                dest.write(f'@dataclass\nclass {name}(OptionsGroup):\n')
                for opt in options:
                    dest.write(f'    {opt.to_python_hint("name")}\n')
                dest.write('\n\n')
            dest.write('SUB_OPTION_PREFIX_MAP: dict[str, type] = {\n')
            for name in sub_options.keys():
                for opt in primary_options:
                    if opt.py_type == name:
                        dest.write(f'    "{opt.name}": {name},\n')
            dest.write('}\n\n')
            dest.write('@dataclass\nclass OptionsContainerType(OptionsGroup):\n')
            for opt in primary_options:
                dest.write(f'    {opt.to_python_hint("name")}\n')
            dest.write('\n\n@dataclass\nclass ShortOptionsContainerType(OptionsGroup):\n')
            for opt in primary_options:
                if "OptionsType" in opt.py_type:
                    for name, options in sub_options.items():
                        if name not in opt.py_type:
                            continue
                        for short_opt in options:
                            dest.write(f'    {short_opt.to_python_hint("short")}\n')
                else:
                    dest.write(f'    {opt.to_python_hint("short")}\n')
            dest.write('\n\n@dataclass\nclass CgiOptionsContainerType(OptionsGroup):\n')
            for opt in primary_options:
                if "OptionsType" in opt.py_type:
                    for name, options in sub_options.items():
                        if name not in opt.py_type:
                            continue
                        for cgi_opt in options:
                            dest.write(f'    {cgi_opt.to_python_hint("cgi")}\n')
                else:
                    dest.write(f'    {opt.to_python_hint("cgi")}\n')

    @classmethod
    def create_typescript_types_file(cls,
                                     ts_dest: Path,
                                     primary_options: list[DashOptionTypeHint],
                                     sub_options: dict[str, list[DashOptionTypeHint]]) -> None:
        print(f"Creating {ts_dest}")
        with ts_dest.open('wt', encoding='utf-8') as dest:
            dest.write('// this file is auto-generated, do not edit!\n\n')
            dest.write('// to re-generate this file, use the command:\n')
            dest.write('// uv run -m dashlive.server.options.generate_types\n\n')
            drm_names: list[str] = [f'"{d.lower()}"' for d in DrmSystem.keys()]
            dest.write(f'export type DrmSystemType = {" | ".join(drm_names)};\n\n')
            for name, options in sub_options.items():
                dest.write(f'export type {name} = {{\n')
                for opt in options:
                    dest.write(f'  {opt.name}: {opt.ts_type};\n')
                dest.write('}\n\n')
                dest.write(f'export type Short{name} = {{\n')
                for opt in options:
                    dest.write(f'  {opt.short}: {opt.ts_type};\n')
                dest.write('}\n\n')
            dest.write('export type OptionsContainerType = {\n')
            for opt in primary_options:
                dest.write(f'  {opt.name}: {opt.ts_type};\n')
            dest.write('}\n\n')
            dest.write('export type ShortOptionsContainerType = {\n')
            for opt in primary_options:
                if "OptionsType" in opt.ts_type:
                    dest.write(f'  {opt.short}: Short{opt.ts_type};\n')
                else:
                    dest.write(f'  {opt.short}: {opt.ts_type};\n')
            dest.write('}\n\n')
            dest.write('export type CgiOptionsContainerType = {\n')
            for opt in primary_options:
                if "OptionsType" in opt.ts_type:
                    for name, options in sub_options.items():
                        if name not in opt.ts_type:
                            continue
                        for cgi_opt in options:
                            dest.write(f'  {cgi_opt.cgi}: {cgi_opt.ts_type};\n')
                else:
                    dest.write(f'  {opt.cgi}: {opt.ts_type};\n')
            dest.write('}\n')


if __name__ == "__main__":
    py_dest: Path = Path(__file__).parent / "options_types.py"
    ts_dest: Path = Path(__file__).parent.parent.parent.parent / "frontend" / "@types" / "@dashlive" / "dash-options.d.ts"
    OptionsTypesGenerator.create_options_container_types_files(py_dest, ts_dest)
