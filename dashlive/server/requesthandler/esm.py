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
from pathlib import Path
import re

import flask
from flask.views import MethodView  # type: ignore

from dashlive.server.options.repository import OptionsRepository
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
        context = {}
        if 'default' in filename:
            context['defaults'] = OptionsRepository.get_default_options().generate_cgi_parameters(
                exclude={'_type'})
        # TODO: check if filename exists
        body = flask.render_template(f'esm/{filename}', **context)
        return flask.make_response((body, 200, headers))


class RouteMap(MethodView):
    """
    Returns a URL routing map for use by a single-page application.
    """
    def get(self) -> flask.Response:
        headers = {
            'Content-Type': 'application/javascript',
        }
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
        body = flask.render_template('esm/routemap.js', routes=route_map)
        return flask.make_response((body, 200, headers))

    @staticmethod
    def static_route(directory: str, title: str) -> dict:
        filename = f"{directory}/"
        return {
            "template": flask.url_for('static', filename=filename) + r"{filename}",
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
        body = flask.render_template('esm/content_roles.js', roles=roles)
        return flask.make_response((body, 200, headers))

class UiComponents(MethodView):
    """
    Returns a bundle of all of the UI components
    """
    def get(self) -> flask.Response:
        headers = {
            'Content-Type': 'application/javascript',
        }
        static_dir: Path = Path(flask.current_app.config['STATIC_FOLDER'])
        ui_folder = static_dir / "js" / "spa" / "components"
        js_files: list[str] = []
        for js in ui_folder.glob("*.js"):
            url: str = flask.url_for(
                'static', filename=f'js/spa/components/{js.name}')
            js_files.append(f"export * from '{url}';")
        body: str = '\n'.join(js_files)
        headers['Content-Length'] = len(body)
        return flask.make_response((body, 200, headers))
