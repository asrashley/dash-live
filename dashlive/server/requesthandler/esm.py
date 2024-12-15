#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import io
from pathlib import Path
import re
from typing import ClassVar

import flask
from flask.views import MethodView  # type: ignore

from dashlive.components.field_group import InputFieldGroupJson
from dashlive.drm.system import DrmSystem
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.dash_option import DashOption
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.types import OptionUsage
from dashlive.mpeg.dash.content_role import ContentRole
from dashlive.server.routes import routes


class ModuleWrapper(MethodView):
    """
    Handler that is used to wrap conventional JS libraries into ESM modules
    """

    def get(self, filename: str) -> flask.Response:
        headers = {
            'Content-Type': 'application/javascript',
        }
        # TODO: check if filename exists
        body = flask.render_template(f'esm/{filename}')
        return flask.make_response((body, 200, headers))


class RouteMap(MethodView):
    """
    Returns a URL routing map for use by a single-page application.
    """
    def get(self) -> flask.Response:
        remove_names = re.compile(r'\?P(<\w+>)')
        find_params = re.compile(r'{(\w+)}')
        route_map: dict[str, dict] = {
            "css": RouteMap.static_route('css', 'style sheets'),
            "fonts": RouteMap.static_route('fonts', 'fonts'),
            "icons": RouteMap.static_route('icons', 'icons'),
            "images": RouteMap.static_route('img', 'images'),
        }
        for name, route in routes.items():
            parts = [p.title() for p in name.split('-')]
            parts[0] = parts[0].lower()
            name: str = ''.join(parts)
            rgx: str = remove_names.sub(r'?\1', route.reTemplate.pattern)
            # rgx = rgx.replace("\\", "\\\\")
            rgx = rgx.replace("/", "\\/")
            route_map[name] = {
                'template': route.formatTemplate,
                're': rgx,
                'title': route.title,
                'route': find_params.sub(r':\1', route.formatTemplate),
            }
        for item in route_map.values():
            names: list[str] = []
            for name in find_params.finditer(item["template"]):
                names.append(name.group(1))
            template: str = item["template"].replace(r'{', r'${')
            params: str = ', '.join(names)
            if params:
                params = f'{{{params}}}'
            item["url"] = f'({params}) => `{template}`'
        body: str = flask.render_template('esm/routemap.tjs', routes=route_map)
        headers: dict[str, str] = {
            'Content-Type': 'application/javascript',
            'Content-Length': len(body),
        }
        return flask.make_response((body, 200, headers))

    @staticmethod
    def static_route(directory: str, title: str) -> dict:
        filename = f"{directory}/"
        return {
            "template": flask.url_for('static', filename=filename) + r"{filename}",
            "route": flask.url_for('static', filename=filename) + r":filename",
            "re": (
                flask.url_for('static', filename=filename).replace('/', r'\/') +
                r'(?<filename>[\w_.-]+)'
            ),
            "title": f"static {title}",
        }


class ContentRoles(MethodView):
    """
    Returns an object describing content roles
    """
    def get(self) -> flask.Response:
        headers = {
            'Content-Type': 'application/javascript',
        }
        roles: dict[str, str] = {}
        for role in ContentRole.all():
            roles[role.name.lower()] = [use.name.lower() for use in role.usage()]
        body = flask.render_template('esm/content_roles.tjs', roles=roles)
        return flask.make_response((body, 200, headers))


class OptionFieldGroups(MethodView):
    """
    Returns JavaScript source that defines all input fields for all CGI options and
    their defaults.
    """
    def get(self) -> flask.Response:
        field_name_map = {}
        for opt in OptionsRepository.get_dash_options(use=~OptionUsage.HTML):
            if opt.prefix:
                field_name_map[f"{opt.prefix}__{opt.cgi_name}"] = opt
            else:
                field_name_map[opt.cgi_name] = opt
        options: OptionsContainer = OptionsRepository.get_default_options()
        field_groups: list[InputFieldGroupJson] = [
            fg.toJSON(exclude={'className', 'show'}) for fg in options.generate_input_field_groups(
                {},
                exclude={
                    'audioErrors', 'dashjsVersion', 'mode', 'manifestErrors', 'textErrors',
                    'videoErrors', 'shakaVersion', 'failureCount', 'videoCorruption',
                    'videoCorruptionFrameCount', 'updateCount', 'utcValue'
                })
        ]
        for group in field_groups:
            for field in group['fields']:
                try:
                    opt: DashOption = field_name_map[field['name']]
                except KeyError:
                    continue
                field['shortName'] = opt.short_name
                field['fullName'] = opt.full_name
        body: str = flask.render_template(
            'esm/options.js',
            full_options=options.toJSON(exclude={"_type"}),
            cgi_options=options.generate_cgi_parameters(remove_defaults=False),
            short_options=options.generate_short_parameters(remove_defaults=False),
            drm_systems=DrmSystem.values(),
            field_groups=field_groups)
        headers: dict[str, str] = {
            'Content-Type': 'application/javascript',
            'Content-Length': len(body),
        }
        return flask.make_response((body, 200, headers))


class BundleDirectory(MethodView):
    DEFAULT_IMPORT: ClassVar[re.Pattern] = re.compile(r'^import (?P<name>[^\s]+) from [''"](?P<library>[^''"]+)[''"];?$')
    NAMED_IMPORT: ClassVar[re.Pattern] = re.compile(
        r'^import\s+{\s*(?P<names>[^}]+)\s*}\s+from\s+[\'"](?P<library>[^\'"]+)[\'"];?$')

    """
    Returns a bundle of all of the UI components
    """
    def get(self, directory: str) -> flask.Response:
        if directory not in {'hooks', 'components'}:
            return flask.make_response('Unknown ESM bundle', 404)
        static_dir: Path = Path(flask.current_app.config['STATIC_FOLDER'])
        ui_folder: Path = static_dir / "js" / "spa" / directory
        js_files: set[str] = set()
        test_file: re.Pattern[str] = re.compile(r'\.test\.')
        default_imports: dict[str, str] = {}
        named_imports: dict[str, set[str]] = {}
        code: list[str] = []
        for js in ui_folder.glob("*.js"):
            if test_file.search(js.name) or js.name == 'index.js':
                continue
            js_files.add(f"./{js.name}")
            code += self.process_file(js, default_imports, named_imports)
        body: io.TextIO = io.StringIO()
        library: str
        name: str
        for library, name in default_imports.items():
            if library not in js_files:
                if library.startswith('../'):
                    library = flask.url_for('static', filename=f"js/spa/{library[3:]}")
                body.write(f"import {name} from '{library}';\n")
        for library, names in named_imports.items():
            if library not in js_files:
                if library.startswith('../'):
                    library = flask.url_for('static', filename=f"js/spa/{library[3:]}")
                body.write(f"import {{{','.join(names)}}} from '{library}';\n")
        for line in code:
            body.write(f"{line}\n")
        headers: dict[str, str] = {
            'Content-Type': 'application/javascript',
            'Content-Length': body.tell(),
        }
        return flask.make_response((body.getvalue(), 200, headers))

    @classmethod
    def process_file(cls, js_file: Path, default_imports: dict[str, str], named_imports: dict[str, set[str]]) -> list[str]:
        code: list[str] = []
        with js_file.open('rt') as src:
            line: str
            for line in src:
                line = line.rstrip()
                if not line:
                    continue
                match: re.Match[str] | None = cls.DEFAULT_IMPORT.match(line)
                if match:
                    default_imports[match['library']] = match['name']
                    continue
                match = cls.NAMED_IMPORT.match(line)
                if match:
                    library: str = match['library']
                    try:
                        name_set: set[str] = named_imports[library]
                    except KeyError:
                        name_set = set()
                        named_imports[library] = name_set
                    name: str
                    for name in match['names'].split(','):
                        name = name.strip()
                        if name:
                            name_set.add(name)
                    continue
                code.append(line)
        return code
