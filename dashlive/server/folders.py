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
import json
from os import environ
from pathlib import Path

class AppFolders:
    basedir: Path
    blob_folder: Path
    instance_path: Path
    media_folder: Path
    srcdir: Path
    template_folder: Path
    upload_folder: Path

    def __init__(self, instance_path: str | None = None) -> None:
        self.srcdir = Path(__file__).parent.resolve()
        self.basedir = self.srcdir.parent.parent
        self.template_folder = self.basedir / "templates"
        self.static_folder = self.basedir / "static"
        if not self.template_folder.exists():
            self.template_folder = self.srcdir / "templates"
            self.static_folder = self.srcdir / "static"
        if instance_path is None:
            self.instance_path = Path(
                environ.get('FLASK_INSTANCE_PATH', str(self.basedir))).resolve()
        else:
            self.instance_path = Path(instance_path).resolve()
        self.media_folder = self.instance_path / "media"
        self.blob_folder = self.media_folder / "blobs"
        self.upload_folder = self.media_folder / "blobs"

    def create_media_folders(self) -> None:
        self.media_folder.mkdir(parents=True, exist_ok=True)
        self.blob_folder.mkdir(exist_ok=True)
        self.upload_folder.mkdir(exist_ok=True)

    def check(self, check_media: bool = True) -> None:
        assert self.template_folder.exists()
        assert self.static_folder.exists()
        assert self.instance_path.exists()
        if check_media:
            assert self.media_folder.exists()
            assert self.blob_folder.exists()
            assert self.upload_folder.exists()

    def __str__(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, indent=2, default=str)
