#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from collections import defaultdict
import copy
import dataclasses
import logging
from typing import AbstractSet, Any, Optional

from dashlive.drm.location import DrmLocation
from dashlive.drm.system import DrmSystem
from dashlive.server.options.drm_options import (
    ALL_DRM_LOCATIONS,
    DrmLocationOption,
    DrmSelectionTuple
)
from dashlive.components.field_group import InputFieldGroup
from dashlive.server.options.form_input_field import FormInputContext
from dashlive.server.options.name_maps import DashOptionNameMaps
from dashlive.server.options.options_types import OptionsContainerType
from dashlive.utils.json_object import JsonObject
from dashlive.utils.objects import dict_to_cgi_params

from .dash_option import DashOption
from .types import OptionUsage

class OptionsContainer(OptionsContainerType):

    @property
    def encrypted(self) -> bool:
        try:
            return len(self.drmSelection) > 0
        except AttributeError:
            return False

    def clone(self, **kwargs) -> "OptionsContainer":
        result: OptionsContainer = copy.deepcopy(self)
        result.update(**kwargs)
        return result

    def update(self, **kwargs) -> None:
        """
        Apply the provided values to this options container. Each item in kwargs
        must be a full-name field name. If a sub-option group is provided, this function
        will recursively apply the provided values to update the sub-option.
        """
        parameter_map = DashOptionNameMaps.get_parameter_map()
        for key, value in kwargs.items():
            assert key in self.__dict__, f"Invalid option name: {key}"
            if key not in parameter_map:  # must be a sub-option group
                assert isinstance(value, dict)
                dest = getattr(self, key)
                for k2, v2 in value.items():
                    opt: DashOption = parameter_map[f'{key}.{k2}']
                    self.set_with_type_coercion(dest, opt, k2, v2)
            elif key == 'drmSelection':
                # special handling for drmSelection to translate to DrmLocation enum values
                # TODO: find a general way to handle this kind of field
                if value is None:
                    value = []
                new_value: list[DrmSelectionTuple] = []
                for name, loc_val in value:
                    locs: set[DrmLocation] = set()
                    if loc_val is None:
                        locs = ALL_DRM_LOCATIONS
                    elif isinstance(loc_val, str):
                        locs.add(DrmLocation.from_string(loc_val))
                    else:
                        for it in loc_val:
                            if isinstance(it, str):
                                locs.add(DrmLocation.from_string(it))
                            else:
                                locs.add(it)
                    new_value.append((name, locs))
                self.drmSelection = new_value
            else:
                opt: DashOption = parameter_map[key]
                self.set_with_type_coercion(self, opt, key, value)

    @staticmethod
    def set_with_type_coercion(dest: object, opt: DashOption, key: str, value: Any) -> None:
        ours = getattr(dest, key)
        if ours == value:
            return
        if ours is not None and value is not None and not isinstance(value, type(ours)):
            if isinstance(value, str):
                value = opt.from_string(value)
            if not isinstance(value, type(ours)):
                py_type: str | None = opt.python_type_hint()
                if py_type is None or value.__class__.__name__ not in py_type:
                    raise ValueError(
                        f"Invalid type for field {key}: expected {type(ours)}, got {type(value)}. Allowed types: {py_type}")
        setattr(dest, key, value)

    def apply_options(self,
                      params: dict[str, str],
                      is_cgi: bool) -> None:
        """
        Apply the provided CGI parameters (or short name parameters) to this options container
        """
        param_map: dict[str, DashOption]
        if is_cgi:
            param_map = DashOptionNameMaps.get_cgi_map()
        else:
            param_map = DashOptionNameMaps.get_short_param_map()
        for key, value in params.items():
            try:
                opt: DashOption = param_map[key]
                value = opt.from_string(value)
                default = opt.default_value()
                if value is None and default is not None:
                    value = default
                if opt.prefix:
                    dest = getattr(self, opt.prefix)
                    setattr(dest, opt.full_name, value)
                else:
                    setattr(self, opt.full_name, value)
            except KeyError as err:
                logging.warning(r'Invalid parameter name %s is_cgi=%s: %s', key, is_cgi, err)
                print(f"Invalid parameter name {key} is_cgi={is_cgi}: {err}")

    def _convert_sub_options(self,
                             destination: dict[str, str],
                             is_cgi: bool,
                             prefix: str,
                             sub_opts: object,
                             use: OptionUsage | None,
                             exclude: AbstractSet | None,
                             defaults: object | None) -> None:
        if exclude is None:
            exclude = set()
        assert dataclasses.is_dataclass(sub_opts)
        parameter_map = DashOptionNameMaps.get_parameter_map()
        for field in dataclasses.fields(sub_opts):
            name: str = f'{prefix}.{field.name}'
            if name in exclude:
                continue
            opt: DashOption = parameter_map[name]
            skip: bool = use is not None and (opt.usage & use) == 0
            value: Any = getattr(sub_opts, field.name)
            if defaults is not None:
                try:
                    dft_val = getattr(defaults, field.name)
                    if value == dft_val:
                        skip = True
                except AttributeError:
                    pass
            if not skip:
                if is_cgi:
                    destination[opt.cgi_name] = opt.to_string(value)
                else:
                    destination[opt.short_name] = value

    def generate_cgi_parameters(self,
                                destination: dict[str, str] | None = None,
                                use: OptionUsage | None = None,
                                exclude: AbstractSet | None = None,
                                remove_defaults: bool = True) -> dict[str, str]:
        """
        Produces a dictionary of CGI parameters that represent these options.
        Any option that matches its default is excluded.
        """
        return self._generate_parameters_dict(
            is_cgi=True, destination=destination, use=use, exclude=exclude,
            remove_defaults=remove_defaults)

    def generate_short_parameters(self,
                                  destination: dict[str, str] | None = None,
                                  use: OptionUsage | None = None,
                                  exclude: AbstractSet | None = None,
                                  remove_defaults: bool = True) -> dict[str, str]:
        """
        Produces a dictionary of shortName parameters that represent these options.
        Any option that matches its default is excluded.
        """
        return self._generate_parameters_dict(
            is_cgi=False, destination=destination, use=use, exclude=exclude,
            remove_defaults=remove_defaults)

    def _generate_parameters_dict(self,
                                  is_cgi: bool,
                                  destination: dict[str, str] | None,
                                  use: OptionUsage | None,
                                  exclude: AbstractSet | None,
                                  remove_defaults: bool) -> dict[str, str]:
        """
        Produces a dictionary of parameters that represent these options.
        Any option that matches its default is excluded if :remove_defaults: is True
        """
        attr_name: str = 'cgi_name' if is_cgi else 'short_name'
        if exclude is None:
            exclude = {'encrypted', 'mode'}
        if destination is None:
            destination = {}
        parameter_map = DashOptionNameMaps.get_parameter_map()
        defaults = OptionsContainer()
        for field in dataclasses.fields(self):
            if field.name in exclude:
                continue

            value = getattr(self, field.name)

            if dataclasses.is_dataclass(value):
                sub_defaults = getattr(defaults, field.name) if remove_defaults else None
                self._convert_sub_options(
                    destination=destination, prefix=field.name, sub_opts=value, use=use,
                    exclude=exclude, defaults=sub_defaults, is_cgi=is_cgi)
                continue

            skip: bool = False
            if remove_defaults:
                try:
                    dft_val = getattr(defaults, field.name)
                    skip = value == dft_val
                except AttributeError:
                    pass
            opt: DashOption = parameter_map[field.name]
            if use is not None and (opt.usage & use) == 0:
                skip = True
            if not skip:
                destination[getattr(opt, attr_name)] = opt.to_string(value)
        return destination

    def json_without_default_values(self, defaults: Optional["OptionsContainer"] = None) -> JsonObject:
        if defaults is None:
            defaults = OptionsContainer()
        result: JsonObject = {}
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            dflt = getattr(defaults, field.name)
            if dataclasses.is_dataclass(value):
                sub_result: JsonObject = {}
                for it in dataclasses.fields(value):
                    v = getattr(value, it.name)
                    d = getattr(dflt, it.name)
                    if d != v:
                        sub_result[it.name] = v
                if sub_result:
                    result[field.name] = sub_result
            elif value != dflt:
                result[field.name] = value
        return result

    def generate_cgi_parameters_string(self,
                                       use: OptionUsage | None = None,
                                       exclude: AbstractSet | None = None) -> str:
        return dict_to_cgi_params(self.generate_cgi_parameters(
            use=use, exclude=exclude))

    def remove_unsupported_features(self, supported_features: AbstractSet[str]) -> None:
        todo: set[str] = {
            'abr', 'audioCodec', 'useBaseUrls', 'drmSelection', 'eventTypes',
            'minimumUpdatePeriod', 'segmentTimeline', 'utcMethod'
        }
        todo.difference_update(supported_features)
        defaults = OptionsContainer()
        for name in todo:
            setattr(self, name, getattr(defaults, name))

    def reset_unused_parameters(
            self,
            mode: str,
            encrypted: bool | None = None,
            use: OptionUsage | None = None) -> None:
        """
        Reset to default all values that are not relevant based upon selected mode.
        """
        if encrypted is None:
            encrypted = self.encrypted
        todo: list[str] = []
        if mode != 'live':
            todo += ['availabilityStartTime', 'minimumUpdatePeriod',
                     'ntpSources', 'timeShiftBufferDepth', 'utcMethod',
                     'utcValue', 'patch']
        if encrypted:
            drms: set[str] = {item[0] for item in self.drmSelection}
            if 'playready' not in drms:
                todo += ['playready.licenseUrl', 'playready.piff', 'playready.version']
            if 'marlin' not in drms:
                todo.append('marlin.licenseUrl')
            if 'clearkey' not in drms:
                todo.append('clearkey.licenseUrl')
        else:
            todo += ['marlin.licenseUrl', 'playready.licenseUrl', 'playready.piff',
                     'playready.version', 'clearkey.licenseUrl']
        if use is not None:
            fields: set[str] = set()
            for field in dataclasses.fields(self):
                if dataclasses.is_dataclass(field.type):
                    for it in dataclasses.fields(field.type):
                        fields.add(f"{field.name}.{it.name}")
                else:
                    fields.add(field.name)
            fields -= set(todo)
            parameter_map = DashOptionNameMaps.get_parameter_map()
            for name in fields:
                try:
                    opt = parameter_map[name]
                    if (opt.usage & use) == 0:
                        todo.append(name)
                except KeyError:
                    pass
        defaults = OptionsContainer()
        for name in todo:
            if '.' in name:
                prefix, key = name.split('.')
                val = getattr(getattr(defaults, prefix), key)
                setattr(getattr(self, prefix), key, val)
            else:
                setattr(self, name, getattr(defaults, name))

    def generate_input_field_groups(
            self, field_choices: dict,
            exclude: AbstractSet | None = None) -> list[InputFieldGroup]:
        sections: dict[str, list[FormInputContext]] = defaultdict(list)
        for field in self.generate_input_fields(field_choices, exclude):
            group: str = field.get('prefix', '')
            if group == "":
                group = "general" if field.get("featured", False) else "advanced"
            sections[group].append(field)
        result: list[InputFieldGroup] = [
            InputFieldGroup("general", "General Options", sections["general"], show=True),
        ]
        del sections["general"]
        for name, fields in sorted(sections.items()):
            result.append(InputFieldGroup(name, f'{name.title()} Options', fields, show=False))
        return result

    def generate_input_fields(self, field_choices: dict,
                              exclude: AbstractSet | None = None) -> list[FormInputContext]:
        fields: list[FormInputContext] = []
        if exclude is None:
            exclude = set()
        parameter_map = DashOptionNameMaps.get_parameter_map()
        for field in dataclasses.fields(self):
            if field.name in exclude:
                continue
            value = getattr(self, field.name)
            if dataclasses.is_dataclass(value):
                for it in dataclasses.fields(value):
                    name: str = f'{field.name}.{it.name}'
                    if name in exclude:
                        continue
                    op: DashOption = parameter_map[name]
                    fields.append(
                        op.input_field(getattr(value, it.name), field_choices))
                continue
            try:
                opt = parameter_map[field.name]
            except KeyError:
                continue
            if opt.full_name == 'drmSelection':
                fields += self.generate_drm_fields(value)
            else:
                input = opt.input_field(value, field_choices)
                fields.append(input)
        fields.sort(key=lambda item: item['title'])
        return fields

    def generate_drm_fields(self, value: list[DrmSelectionTuple | str] | None) -> list[JsonObject]:
        fields: list[JsonObject] = []
        drms: dict[str, set[DrmLocation]] = {}
        all_locations = '-'.join(DrmLocation.values())
        if value:
            for item in value:
                locs: set[DrmLocation] = set()
                for drm_loc in item[1]:
                    if isinstance(drm_loc, str):
                        locs.add(DrmLocation.from_string(drm_loc))
                    else:
                        locs.add(drm_loc)
                drms[item[0]] = locs
        for name in DrmSystem.values():
            fields.append({
                "name": f'{name}__enabled',
                "shortName": f'{name}__enabled',
                "fullName": 'enabled',
                "title": f'{name.title()} DRM',
                "text": f'Enable {name.title()} DRM support?',
                "value": name in drms,
                "type": "checkbox",
                "className": "drm-checkbox",
                "prefix": name,
            })
            locs = drms.get(name, set())
            val = '-'.join(sorted([loc.to_json() for loc in locs]))
            if val == all_locations:
                val = ''
            input = DrmLocationOption.input_field(val, {})
            cgi_name: str = f'{name}__{input["name"]}'
            full_name = input["name"]
            input.update({
                'name': cgi_name,
                'shortName': cgi_name,
                'fullName': full_name,
                'title': f'{name.title()} location',
                'rowClass': f'row mb-3 drm-location prefix-{name}',
                'prefix': name,
            })
            fields.append(input)
        return fields
