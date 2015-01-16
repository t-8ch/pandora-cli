import os

import requests
from mutagen import easyid3, mp3, id3

from .api import AudioQuality


class Downloader(object):
    def __init__(self, target, quality=AudioQuality.highQuality,
                 pattern='{artist_name}/{album_name}/{name}.mp3'):
        self.target = target
        self.pattern = pattern
        self.quality = quality
        self._tmp_subdir = '.tmp'
        self._http_session = requests.Session()
        self._station_tag = 'pandora:station'

    def download(self, song):
        target = self._format_target(song)
        tmp_path = self._format_tmp(song)

        url = song.audios[self.quality].url

        self._ensure_dirname(tmp_path)

        if not os.path.exists(target):
            with open(tmp_path, 'wb') as fd:
                res = self._http_session.get(url, stream=True)

                for chunk in res.iter_content(2048):
                    fd.write(chunk)

            length = self._tag_file_get_length(tmp_path, song)
            self._ensure_dirname(target)
            os.rename(tmp_path, target)

            return length

        else:
            return False

    def add_station_tag(self, song, station):
        name = '{} ({})'.format(station.name, station.id)
        path = self._format_target(song)
        audio = id3.ID3(path)
        found = False

        comments = audio.getall('TXXX')

        for comment in comments:
            if comment.desc == self._station_tag:
                found = True
                if name not in comment.text:
                    comment.text.append(name)

        if not found:
            audio.add(id3.TXXX(encoding=3, desc=self._station_tag, text=name))

        audio.save()

    def _format_tail(self, song):
        return self.pattern.format(artist_name=song.artist_name,
                                   album_name=song.album_name,
                                   name=song.name)

    def _format_target(self, song):
        return os.path.join(self.target, self._format_tail(song))

    def _format_tmp(self, song):
        return os.path.join(self.target, self._tmp_subdir,
                            self._format_tail(song))

    @staticmethod
    def _ensure_dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)

    @staticmethod
    def _tag_file_get_length(path, song):
        audio = mp3.MP3(path, ID3=easyid3.EasyID3)
        length = audio.info.length
        audio['title'] = song.name
        audio['artist'] = song.artist_name
        audio['album'] = song.album_name
        audio.save()

        return length
