from __future__ import absolute_import, unicode_literals

import io
import locale
import logging
import operator
import os

from mopidy import backend

from . import Extension, translator

logger = logging.getLogger(__name__)


def log_environment_error(message, error):
    if isinstance(error.strerror, bytes):
        strerror = error.strerror.decode(locale.getpreferredencoding())
    else:
        strerror = error.strerror
    logger.error('%s: %s', message, strerror)


class M3UPlaylistsProvider(backend.PlaylistsProvider):

    def __init__(self, backend, config):
        super(M3UPlaylistsProvider, self).__init__(backend)

        ext_config = config[Extension.ext_name]
        if ext_config['playlists_dir'] is None:
            self._playlists_dir = Extension.get_data_dir(config)
        else:
            self._playlists_dir = ext_config['playlists_dir']
        self._default_encoding = ext_config['default_encoding']
        self._default_extension = ext_config['default_extension']

    def as_list(self):
        result = []
        for entry in os.listdir(self._playlists_dir):
            if not entry.endswith((b'.m3u', b'.m3u8')):
                continue
            elif not os.path.isfile(self._abspath(entry)):
                continue
            else:
                result.append(translator.path_to_ref(entry))
        result.sort(key=operator.attrgetter('name'))
        return result

    def create(self, name):
        path = translator.path_from_name(name.strip(), self._default_extension)
        try:
            with self._open(path, 'w'):
                pass
            mtime = os.path.getmtime(self._abspath(path))
        except EnvironmentError as e:
            log_environment_error('Error creating playlist %s' % name, e)
        else:
            return translator.playlist(path, [], mtime)

    def delete(self, uri):
        path = translator.uri_to_path(uri)
        try:
            os.remove(self._abspath(path))
        except EnvironmentError as e:
            log_environment_error('Error deleting playlist %s' % uri, e)

    def get_items(self, uri):
        path = translator.uri_to_path(uri)
        try:
            with self._open(path, 'r') as fp:
                items = translator.load_items(fp, self._playlists_dir)
        except EnvironmentError as e:
            log_environment_error('Error reading playlist %s' % uri, e)
        else:
            return items

    def lookup(self, uri):
        path = translator.uri_to_path(uri)
        try:
            with self._open(path, 'r') as fp:
                items = translator.load_items(fp, self._playlists_dir)
            mtime = os.path.getmtime(self._abspath(path))
        except EnvironmentError as e:
            log_environment_error('Error reading playlist %s' % uri, e)
        else:
            return translator.playlist(path, items, mtime)

    def refresh(self):
        pass  # nothing to do

    def save(self, playlist):
        path = translator.uri_to_path(playlist.uri)
        name = translator.name_from_path(path)
        try:
            with self._open(path, 'w') as fp:
                translator.dump_items(playlist.tracks, fp)
            if playlist.name and playlist.name != name:
                opath, ext = os.path.splitext(path)
                path = translator.path_from_name(playlist.name.strip()) + ext
                os.rename(self._abspath(opath + ext), self._abspath(path))
            mtime = os.path.getmtime(self._abspath(path))
        except EnvironmentError as e:
            log_environment_error('Error saving playlist %s' % playlist.uri, e)
        else:
            return translator.playlist(path, playlist.tracks, mtime)

    def _abspath(self, path):
        return os.path.join(self._playlists_dir, path)

    def _open(self, path, mode='r'):
        if path.endswith(b'.m3u8'):
            encoding = 'utf-8'
        else:
            encoding = self._default_encoding
        if not os.path.isabs(path):
            path = os.path.join(self._playlists_dir, path)
        return io.open(path, mode, encoding=encoding, errors='replace')
