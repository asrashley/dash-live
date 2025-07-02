#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import TypeAlias

import flask  # type: ignore

from dashlive.drm.base import DrmBase, DrmManifestContext
from dashlive.drm.clearkey import ClearKey
from dashlive.drm.playready import PlayReady
from dashlive.drm.marlin import Marlin
from dashlive.drm.system import DrmSystem
from dashlive.server.models import Stream
from dashlive.server.options.container import OptionsContainer

from .utils import is_https_request

DrmLocationTuple: TypeAlias = tuple[str, DrmBase, set[str]]

class DrmContextIterator:
    contexts: list[DrmManifestContext]

    def __init__(self, manifest_context: dict[str, DrmManifestContext]) -> None:
        keys: list[str] = list(manifest_context.keys())
        keys.sort()
        self.contexts = [manifest_context[k] for k in keys]

    def __next__(self) -> DrmManifestContext:
        try:
            return self.contexts.pop(0)
        except IndexError:
            raise StopIteration()


class DrmContext:
    manifest_context: dict[str, DrmManifestContext]

    def __init__(self,
                 stream: str | Stream,
                 keys: dict | list,
                 options: OptionsContainer) -> None:
        self.manifest_context = {}
        if isinstance(stream, str):
            stream = Stream.get(directory=stream)
            assert stream is not None
        drm_tuples = self.generate_drm_location_tuples(options)
        for drm_name, drm, locations in drm_tuples:
            la_url = flask.request.args.get(f'{drm_name}_la_url')
            self.manifest_context[drm_name] = drm.generate_manifest_context(
                stream, keys, getattr(options, drm_name),
                https_request=is_https_request(),
                la_url=la_url, locations=locations)

    def __iter__(self) -> DrmContextIterator:
        return DrmContextIterator(self.manifest_context)

    @staticmethod
    def generate_drm_location_tuples(options: OptionsContainer) -> list[DrmLocationTuple]:
        """
        Returns list of tuples, where each entry is:
          * DRM name,
          * DRM implementation, and
          * DRM data locations
        """
        rv: list[DrmLocationTuple] = []
        for drm_name, locations in options.drmSelection:
            assert drm_name in DrmSystem.values()
            if drm_name == 'playready':
                drm = PlayReady()
            elif drm_name == 'marlin':
                drm = Marlin()
            elif drm_name == 'clearkey':
                drm = ClearKey()
            rv.append((drm_name, drm, locations,))
        return rv
