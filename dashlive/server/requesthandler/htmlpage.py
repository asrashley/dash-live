#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import html
import logging
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error
import urllib.parse

import flask
from flask_login import current_user

from dashlive.server import manifests, models
from dashlive.server.options.container import OptionsContainer
from dashlive.server.routes import Route
from dashlive.server.options.drm_options import DrmLocationOption, DrmSelection
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.player_options import ShakaVersion, DashjsVersion
from dashlive.server.options.types import OptionUsage

from .base import HTMLHandlerBase
from .decorators import (
    current_stream,
)
from .manifest_context import ManifestContext
from .navbar import NavBarItem
from .utils import add_allowed_origins, is_https_request

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
            url: str = flask.url_for(
                "dash-mpd-v3", manifest=name, stream="placeholder", mode="live"
            )
            url = url.replace("/placeholder/", "/{directory}/")
            url = url.replace("/live/", "/{mode}/")
            context["rows"].append(
                {
                    "filename": name,
                    "url": url,
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

class VideoPlayer(HTMLHandlerBase):
    """
    Responds with an HTML page that contains a video element to play
    the specified stream
    """

    SHAKA_CDN_TEMPLATE = r"https://ajax.googleapis.com/ajax/libs/shaka-player/{shakaVersion}/shaka-player.compiled.js"
    DASHJS_CDN_TEMPLATE = r"https://cdn.dashjs.org/{dashjsVersion}/dash.all.min.js"

    def get(
        self,
        manifest: str,
        mode: str,
        stream: str | None = None,
        mps_name: str | None = None,
    ) -> flask.Response:
        stream_model: models.Stream | None = None
        multi_period: models.MultiPeriodStream | None = None
        title: str = manifest

        if stream is None and mps_name is None:
            return flask.make_response("Not Found", 404)

        if stream is not None:
            stream_model = models.Stream.get(directory=stream)
            if stream_model is None:
                logging.error("Unknown stream: %s", stream)
                return flask.make_response(
                    f"Unknown stream: {html.escape(stream)}", 404
                )
            title = stream_model.title
            if stream_model.timing_reference is None:
                flask.flash(
                    f'The timing reference needs to be set for stream "{current_stream.title}"',
                    "error",
                )
                return flask.redirect(flask.url_for("home"))
        else:
            multi_period = models.MultiPeriodStream.get(name=mps_name)
            if multi_period is None:
                logging.error("Unknown multi-period stream: %s", mps_name)
                return flask.make_response(
                    f"Unknown stream: {html.escape(mps_name)}", 404
                )
            title = multi_period.title
        app_cfg = flask.current_app.config["DASH"]
        manifest += ".mpd"
        context = self.create_context(title=title)
        try:
            options = self.calculate_options(mode, flask.request.args)
        except ValueError as err:
            logging.error("Invalid CGI parameters: %s", err)
            return flask.make_response("Invalid CGI parameters", 400)
        options.remove_unused_parameters(mode)
        dash_parms = ManifestContext(
            manifest=manifests.manifest_map[manifest],
            options=options,
            stream=stream_model,
            multi_period=multi_period,
        )
        if stream_model:
            dash_parms.stream = stream_model.to_dict(
                only={"pk", "title", "directory", "playready_la_url", "marlin_la_url"}
            )
        context["dash"] = dash_parms.to_dict(
            exclude={"periods", "period", "ref_representation", "audio", "video"}
        )
        if stream:
            mpd_url: str = flask.url_for(
                "dash-mpd-v3", stream=stream, manifest=manifest, mode=mode
            )
        else:
            mpd_url = flask.url_for(
                "mps-manifest", mps_name=mps_name, manifest=manifest, mode=mode
            )
        mpd_url += options.generate_cgi_parameters_string(use=~OptionUsage.HTML)
        context.update(
            {
                "dashjsUrl": None,
                "drm": None,
                "mimeType": "application/dash+xml",
                "source": urllib.parse.urljoin(flask.request.host_url, mpd_url),
                "shakaUrl": None,
                "title": manifests.manifest_map[manifest].title,
                "videoPlayer": options.videoPlayer,
            }
        )
        if options.drmSelection:
            context["drm"] = DrmSelection.to_string(options.drmSelection)
        if options.videoPlayer == "dashjs":
            if options.dashjsVersion is None:
                options.dashjsVersion = DashjsVersion.cgi_choices[1]
            if options.dashjsVersion in set(DashjsVersion.cgi_choices):
                context["dashjsUrl"] = flask.url_for(
                    "static", filename=f"js/prod/dashjs-{options.dashjsVersion}.js"
                )
            else:
                cdn_template = app_cfg.get(
                    "DASHJS_CDN_TEMPLATE", VideoPlayer.DASHJS_CDN_TEMPLATE
                )
                context["dashjsUrl"] = cdn_template.format(
                    dashjsVersion=options.dashjsVersion
                )
        else:
            if options.shakaVersion is None:
                options.shakaVersion = ShakaVersion.cgi_choices[1]
            if options.shakaVersion in set(ShakaVersion.cgi_choices):
                context["shakaUrl"] = flask.url_for(
                    "static", filename=f"js/prod/shaka-player.{options.shakaVersion}.js"
                )
            else:
                cdn_template = app_cfg.get(
                    "SHAKA_CDN_TEMPLATE", VideoPlayer.SHAKA_CDN_TEMPLATE
                )
                context["shakaUrl"] = cdn_template.format(
                    shakaVersion=options.shakaVersion
                )
        if is_https_request():
            context["source"] = context["source"].replace("http://", "https://")
        if options.drmSelection and context["drm"] and "marlin" in context["drm"]:
            licenseUrl: str | None = None
            if options.marlin and options.marlin.licenseUrl:
                licenseUrl = options.marlin.licenseUrl
            elif stream_model.marlin_la_url:
                licenseUrl = stream_model.marlin_la_url
            if licenseUrl:
                context["source"] = f'{licenseUrl}#{context["source"]}'
        return flask.render_template("video.html", **context)


class DashValidator(HTMLHandlerBase):
    """
    Responds with an HTML page that allows a manifest to be validated
    """

    def get(self):
        context = self.create_context()
        context["form"] = [
            {
                "name": "manifest",
                "title": "Manifest to check",
                "type": "url",
                "required": True,
                "placeholder": "... manifest URL ...",
            },
            {
                "name": "duration",
                "title": "Maximum duration",
                "type": "number",
                "text": "seconds",
                "value": 30,
                "min": 1,
                "max": 3600,
            },
        ]
        if current_user.has_permission(models.Group.MEDIA):
            context["form"] += [
                {
                    "name": "prefix",
                    "title": "Destination directory",
                    "type": "text",
                    "disabled": True,
                    "pattern": r"[A-Za-z0-9]{3,31}",
                    "text": "3 to 31 characters without any special characters",
                    "minlength": 3,
                    "maxlength": 31,
                },
                {
                    "name": "title",
                    "title": "Stream title",
                    "type": "text",
                    "disabled": True,
                    "minlength": 3,
                    "maxlength": 119,
                },
            ]
        context["form"] += [
            {
                "name": "encrypted",
                "title": "Stream is encrypted?",
                "type": "checkbox",
                "inline": True,
            },
            {
                "name": "media",
                "title": "Check media segments",
                "type": "checkbox",
                "inline": True,
                "value": True,
            },
            {
                "name": "verbose",
                "title": "Verbose output",
                "type": "checkbox",
                "inline": True,
            },
            {
                "name": "pretty",
                "title": "Pretty print XML before validation",
                "type": "checkbox",
                "inline": True,
                "newRow": True,
            },
        ]
        if current_user.has_permission(models.Group.MEDIA):
            context["form"].append(
                {
                    "name": "save",
                    "title": "Add stream to this server?",
                    "type": "checkbox",
                    "inline": True,
                }
            )
        return flask.render_template("validator.html", **context)


def favicon() -> flask.Response:
    return flask.send_from_directory(
        flask.current_app.static_folder,
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
        conditional=True,
    )
