#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging
from pathlib import Path

import flask
from flask.views import MethodView  # type: ignore

from dashlive.components.field_group import InputFieldGroupJson
from dashlive.drm.system import DrmSystem
from dashlive.server.models.user import User
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.dash_option import DashOption
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.types import OptionUsage
from dashlive.mpeg.dash.content_role import ContentRole
from dashlive.server.routes import routes, ui_routes, RouteJavaScript
from dashlive.utils.json_object import JsonObject

from .spa_context import SpaTemplateContext, create_spa_template_context
from .utils import jsonify

class ModuleWrapper(MethodView):
    """
    Handler that is used to wrap conventional JS libraries into ESM modules
    """

    def get(self, filename: str) -> flask.Response:
        headers = {
            'Content-Type': 'application/javascript',
        }
        app = flask.current_app
        template_folder: Path = Path(app.root_path) / app.template_folder
        js_name = template_folder / 'esm' / Path(filename).name
        js_name = js_name.resolve()
        if not js_name.is_relative_to(template_folder):
            logging.warning('Invalid ESM module path "%s"', filename)
            return flask.make_response('Not Found', 404)
        if not js_name.exists():
            logging.warning('Failed to find ESM module "%s"', js_name)
            return flask.make_response('Not Found', 404)
        body = flask.render_template(f'esm/{filename}')
        return flask.make_response((body, 200, headers))


class RouteMap(MethodView):
    """
    Returns a URL routing map for use by a single-page application.
    """
    def get(self) -> flask.Response:
        route_map: dict[str, RouteJavaScript] = {
            "css": RouteMap.static_route('css', 'style sheets'),
            "fonts": RouteMap.static_route('fonts', 'fonts'),
            "icons": RouteMap.static_route('icons', 'icons'),
            "images": RouteMap.static_route('img', 'images'),
        }
        for name, route in routes.items():
            route_map[self.to_camel_case(name)] = route.to_javascript()

        ui_route_map: dict[str, RouteJavaScript] = {}
        for name, route in ui_routes.items():
            ui_route_map[self.to_camel_case(name)] = route.to_javascript()

        body: str = flask.render_template(
            'esm/routemap.tjs', routes=route_map, ui_routes=ui_route_map)
        headers: dict[str, str] = {
            'Content-Type': 'application/javascript',
            'Content-Length': len(body),
        }
        return flask.make_response((body, 200, headers))

    @staticmethod
    def to_camel_case(name: str) -> str:
        parts: list[str] = [p.title() for p in name.split('-')]
        if parts[0] in {'Api', 'Ui'}:
            parts.pop(0)
        parts[0] = parts[0].lower()
        return ''.join(parts)

    @staticmethod
    def static_route(directory: str, title: str) -> RouteJavaScript:
        filename = f"{directory}/"
        prefix = flask.url_for('static', filename=filename)
        return {
            "template": prefix + r"{filename}",
            "route": prefix + r":filename",
            "rgx": prefix.replace('/', r'\/') + r'(?<filename>[\w_.-]+)',
            "title": f"static {title}",
            "urlFn": f"({{filename}}) => `{prefix}${{filename}}`",
        }


class ContentRoles(MethodView):
    """
    Returns an object describing content roles
    """
    def get(self) -> flask.Response:
        roles: dict[str, list[str]] = {}
        for role in ContentRole.all():
            roles[role.name.lower()] = [use.name.lower() for use in role.usage()]
        return jsonify(roles)


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


class InitialAppState(MethodView):
    """
    Handler that is used to populate the initial app state for the development
    server used by webpack-dev-server
    """
    def get(self) -> flask.Response:
        user: User = User.get_guest_user()
        context: SpaTemplateContext = create_spa_template_context(user)
        body: str = flask.render_template('esm/initial_app_state.tjs', **context)
        headers: dict[str, str] = {
            'Content-Type': 'application/javascript',
            'Content-Length': len(body),
        }
        return flask.make_response((body, 200, headers))

class CgiOptionsPage(MethodView):
    """
    handler for page that describes each CGI option
    """
    def get(self) -> flask.Response:
        options: list[JsonObject] = [opt.toJSON(pure=True) for opt in OptionsRepository.get_cgi_options()]
        for opt in options:
            opt['description'] = opt['html']
            del opt['html']
        return jsonify(options)
