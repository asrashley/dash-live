#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging
from pathlib import Path
import urllib.parse
import urllib.parse

import flask

from dashlive.server import manifests, models
from dashlive.server.options.container import OptionsContainer
from dashlive.server.routes import Route
from dashlive.server.options.drm_options import DrmLocationOption
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.types import OptionUsage
from dashlive.utils.json_object import JsonObject

from .base import HTMLHandlerBase, RequestHandlerBase
from .decorators import (
    current_manifest,
    uses_manifest,
)
from .manifest_context import ManifestContext
from .navbar import NavBarItem
from .template_context import TemplateContext, create_template_context
from .utils import add_allowed_origins, is_https_request, jsonify

class MainPage(HTMLHandlerBase):
    """
    handler for main index page
    """

    def get(self, **kwargs) -> flask.Response:
        static_dir: Path = Path(flask.current_app.config['STATIC_FOLDER'])
        return flask.send_from_directory(static_dir / 'html', 'index.html')


class ES5MainPage(HTMLHandlerBase):
    """
    handler for main index page for use by browsers that only support
    ECMAScript v5 (i.e. very old browsers)
    """

    def get(self) -> flask.Response:
        context = self.create_context(
            title="DASH test streams",
            rows=[],
            streams=list(models.Stream.all()),
            form_id="id_main_form",
            form_name="main",
            mp_streams=list(models.MultiPeriodStream.all()),
            exclude_buttons=True,
        )
        if context["streams"]:
            context.update(
                {
                    "default_stream": context["streams"][0],
                    "default_url": flask.url_for(
                        "dash-mpd-v3",
                        mode="vod",
                        manifest="hand_made.mpd",
                        stream=context["streams"][0].directory,
                    ),
                }
            )
        defaults: OptionsContainer = OptionsRepository.get_default_options()
        field_choices = {
            "representation": [
                dict(value=mf.name, title=mf.name) for mf in models.MediaFile.all()
            ],
            "audio_representation": [
                dict(value=mf.name, title=mf.name)
                for mf in models.MediaFile.search(content_type="audio")
            ],
            "text_representation": [
                dict(value=mf.name, title=mf.name)
                for mf in models.MediaFile.search(content_type="text")
            ],
        }
        for name in ["representation", "audio_representation", "text_representation"]:
            field_choices[name].insert(
                0,
                {
                    "title": "--",
                    "value": "",
                },
            )
        context["field_groups"] = defaults.generate_input_field_groups(
            field_choices,
            exclude={
                "mode",
                "dashjsVersion",
                "marlin.licenseUrl",
                "audioErrors",
                "manifestErrors",
                "textErrors",
                "videoErrors",
                "playready.licenseUrl",
                "shakaVersion",
                "failureCount",
                "videoCorruption",
                "videoCorruptionFrameCount",
                "updateCount",
                "utcValue",
            },
        )
        dash_options = OptionsRepository.get_cgi_map()
        for idx, group in enumerate(context["field_groups"]):
            if idx > 0:
                group.className = "advanced hidden"
            for field in group.fields:
                field["rowClass"] = "row advanced hidden"
                try:
                    if dash_options[field["name"]].featured:
                        field["rowClass"] = "row featured"
                except KeyError:
                    pass
        filenames = list(manifests.manifest_map.keys())
        filenames.sort(key=lambda name: manifests.manifest_map[name].title)

        for name in filenames:
            url_template: str = flask.url_for(
                "dash-mpd-v3", manifest=name, stream="placeholder", mode="live"
            )
            url_template = url_template.replace("/placeholder/", "/{stream}/")
            url_template = url_template.replace("/live/", "/{mode}/")
            mps_url_template: str = flask.url_for(
                "mps-manifest", manifest=name, mps_name="placeholder", mode="live"
            )
            mps_url_template = mps_url_template.replace("/placeholder/", "/{stream}/")
            mps_url_template = mps_url_template.replace("/live/", "/{mode}/")
            context["rows"].append(
                {
                    "filename": name,
                    "url": url_template,
                    "mps_url": mps_url_template,
                    "manifest": manifests.manifest_map[name],
                    "option": [],
                }
            )
        cgi_options = OptionsRepository.get_cgi_options(
            featured=True, omit_empty=False, extras=[DrmLocationOption]
        )
        for idx, opt in enumerate(cgi_options):
            try:
                row = context["rows"][idx]
                row["option"] = opt
            except IndexError:
                row = {"manifest": None, "option": opt}
                context["rows"].append(row)
        headers = {
            "X-Frame-Options": "SAMEORIGIN",
        }
        body = self.render_template(context)
        add_allowed_origins(headers)
        return flask.make_response((body, 200, headers))

    def render_template(self, context: dict) -> str:
        context["navbar"] = [
            {
                "title": "Home",
                "href": flask.url_for("es5-home"),
            }
        ]
        return flask.render_template("es5/index.html", **context)

    def get_breadcrumbs(self, route: Route) -> list[NavBarItem]:
        breadcrumbs: list[NavBarItem] = [
            NavBarItem(title="Home", active=True)
        ]
        return breadcrumbs

class VideoPlayer(RequestHandlerBase):
    """
    Responds with an HTML page that contains a video element to play
    the specified stream
    """
    decorators = [uses_manifest]

    def get(self,
            manifest: str,
            mode: str,
            stream: str) -> flask.Response:
        logging.debug('VideoPlayer.get(%s, %s, %s)', manifest, mode, stream)
        stream_model: models.Stream | None = None
        mps_model: models.MultiPeriodStream | None = None
        if mode.startswith("mps-"):
            mode = mode[4:]
            mps_model = models.MultiPeriodStream.get(name=stream)
        else:
            stream_model = models.Stream.get(directory=stream)
        if stream_model is None and mps_model is None:
            return flask.make_response("Not Found", 404)
        try:
            options: OptionsContainer = self.calculate_options(
                mode=mode,
                args=flask.request.args,
                stream=stream_model,
                restrictions=current_manifest.restrictions,
                features=current_manifest.features)
        except ValueError as e:
            logging.info('Invalid CGI parameters: %s', e)
            return flask.make_response('Invalid CGI parameters', 400)
        mc = ManifestContext(
            manifest=current_manifest, options=options, stream=stream_model,
            multi_period=mps_model)
        dash: JsonObject = mc.to_dict(exclude={
            'ref_representation', 'cgi_params', 'options', 'periods', 'period',
            'timing_ref',
        })
        dash['periods'] = []
        for period in mc.periods:
            dash_period: JsonObject = period.toJSON(exclude={'adaptationSets', '_type'})
            dash_period['adaptationSets'] = []
            for adaptation_set in period.adaptationSets:
                asj: JsonObject = adaptation_set.toJSON(
                    exclude={'drm', 'event_streams', 'representations', 'segment_timeline', '_type'})
                keyIds: list[str] = [k.hex for k in adaptation_set.key_ids()]
                asj['keys'] = {}
                for kid in keyIds:
                    key_model: models.Key | None = models.Key.get(hkid=kid)
                    if key_model is not None:
                        asj['keys'][kid] = key_model.toJSON()
                        asj['keys'][kid]['guidKid'] = key_model.KID.hex_to_le_guid(raw=False)
                        asj['keys'][kid]['b64Key'] = key_model.KEY.b64
                if adaptation_set.drm is not None:
                    asj['drm'] = {}
                    for name, drm_context in adaptation_set.drm.items():
                        asj['drm'][name] = {
                            'laurl': drm_context.laurl,
                            'scheme_id': drm_context.scheme_id,
                            'version': drm_context.version
                        }
                dash_period['adaptationSets'].append(asj)
            dash['periods'].append(dash_period)
        if stream_model:
            mpd_url: str = flask.url_for(
                "dash-mpd-v3", stream=stream, manifest=manifest, mode=mode
            )
        else:
            mpd_url = flask.url_for(
                "mps-manifest", mps_name=stream, manifest=manifest, mode=mode
            )
        drm_selections: set[str] = {d[0] for d in options.drmSelection}
        if options.clearkey.licenseUrl is None:
            options.clearkey.licenseUrl = flask.url_for('clearkey')
        js_opts = options.toJSON(exclude={'drmSelection', 'videoPlayer'})
        js_opts['drmSelection'] = drm_selections
        options.remove_unused_parameters(mode)
        mpd_url += options.generate_cgi_parameters_string(use=~OptionUsage.HTML)
        return jsonify({
            'dash': dash,
            'options': js_opts,
            'url': mpd_url,
        })


class ES5VideoPlayer(RequestHandlerBase):
    """
    Responds with an HTML page that contains a video element to play
    the specified stream on ES5 browsers
    """
    decorators = []

    def get(
        self,
        manifest: str,
        mode: str,
        stream: str | None = None
    ) -> flask.Response:
        stream_model: models.Stream | None = None
        multi_period: models.MultiPeriodStream | None = None
        title: str = manifest

        if mode.startswith("mps-"):
            mode = mode[4:]
            multi_period = models.MultiPeriodStream.get(name=stream)
            if multi_period is None:
                return flask.make_response("Stream not Found", 404)
            title = multi_period.title
        else:
            stream_model = models.Stream.get(directory=stream)
            if stream_model is None:
                return flask.make_response("MPS stream not Found", 404)
            title = stream_model.title
            if stream_model.timing_reference is None:
                return flask.make_response(
                    f'The timing reference needs to be set for stream "{stream_model.title}"',
                    409
                )
        assert stream is not None or multi_period is not None
        manifest += ".mpd"
        context: TemplateContext = create_template_context(title=title)
        try:
            options: OptionsContainer = self.calculate_options(mode, flask.request.args)
        except ValueError as err:
            logging.error("Invalid CGI parameters: %s", err)
            return flask.make_response("Invalid CGI parameters", 400)
        options.remove_unused_parameters(mode)
        if stream_model:
            mpd_url: str = flask.url_for(
                "dash-mpd-v3", stream=stream, manifest=manifest, mode=mode
            )
        else:
            mpd_url = flask.url_for(
                "mps-manifest", mps_name=stream, manifest=manifest, mode=mode
            )
        mpd_url += options.generate_cgi_parameters_string(use=~OptionUsage.HTML)
        context.update(
            {
                "drm": "",
                "mimeType": "application/dash+xml",
                "source": urllib.parse.urljoin(flask.request.host_url, mpd_url),
                "title": title,
            }
        )
        if is_https_request():
            context["source"] = context["source"].replace("http://", "https://")
        if options.drmSelection:
            drms: set[str] = {d[0] for d in options.drmSelection}
            if "marlin" in drms:
                licenseUrl: str | None = None
                if options.marlin and options.marlin.licenseUrl:
                    licenseUrl = options.marlin.licenseUrl
                elif stream_model.marlin_la_url:
                    licenseUrl = stream_model.marlin_la_url
                if licenseUrl:
                    context["source"] = f'{licenseUrl}#{context["source"]}'
        return flask.render_template("es5/video.html", **context)


def favicon() -> flask.Response:
    return flask.send_from_directory(
        flask.current_app.static_folder,
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
        conditional=True,
    )
