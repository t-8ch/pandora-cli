from binascii import unhexlify, hexlify
from collections import namedtuple
import json
import time
from operator import attrgetter

import requests
import cryptography
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class PandoraException(Exception):
    pass

PandoraConfig = namedtuple('PandoraConfig',
                           ['tuner_url', 'username', 'password', 'deviceid',
                            'decrypt_password', 'encrypt_password'])

default_config = PandoraConfig('internal-tuner.pandora.com', 'pandora one',
                               'TVCKIBGS9AO9TSYLNNFUML0743LH82D', 'D01',
                               b'U#IO$RZPAB%VX2', b'2%3WCL*JU$MP]4')


class Pandora(object):
    def __init__(self, user, password, config=default_config, proxy=None):
        self.user = user
        self.password = password
        self.config = config
        self._session = requests.Session()
        self._session.proxies = {
            'http': proxy,
            'https': proxy,
        }
        self._encryptor = Encryptor(self.config.encrypt_password,
                                    self.config.decrypt_password)

        self.partner_auth_token = None
        self.partner_id = None
        self.partner_sync_time = None
        self.client_start_time = None
        self.user_auth_token = None
        self.user_id = None

    def request(self, endpoint, payload=None, encrypt=True, tls=True):
        if payload is None:
            payload = {}

        s = self.sync_time
        if s is not None:
            payload['syncTime'] = s
        if self.user_auth_token is not None:
            payload['userAuthToken'] = self.user_auth_token

        data = json.dumps(payload).encode('utf-8')
        if encrypt:
            data = hexlify(self._encryptor.encrypt(data))
        params = {
            'partner_id': self.partner_id,
            'auth_token': self.user_auth_token or self.partner_auth_token,
            'user_id': self.user_id,
            'method': endpoint
        }
        proto = 'https' if tls else 'http'
        url = '{}://{}/services/json/'.format(proto, self.config.tuner_url)
        r = self._session.post(url, data=data, params=params)
        r.raise_for_status()
        j = r.json()
        if j['stat'] != 'ok':
            raise PandoraException(j['code'], j['message'])
        else:
            return j['result']

    def partner_login(self):
        data = {
            'username': self.config.username,
            'password': self.config.password,
            'deviceModel': self.config.deviceid,
            'version': '5',
        }
        r = self.request('auth.partnerLogin', data, encrypt=False, tls=True)
        self.partner_auth_token = r['partnerAuthToken']
        self.partner_id = r['partnerId']
        s = r['syncTime']
        s = self._encryptor.decrypt(unhexlify(s))
        s = s[4:]
        self.partner_sync_time = int(s)
        self.client_start_time = int(time.time())

    def user_login(self):
        data = {
            'loginType': 'user',
            'username': self.user,
            'password': self.password,
            'partnerAuthToken': self.partner_auth_token,
        }
        r = self.request('auth.userLogin', data, tls=True)
        self.user_auth_token = r['userAuthToken']
        self.user_id = r['userId']

    def auth(self):
        self.partner_login()
        self.user_login()

    def stations(self):
        r = self.request('user.getStationList', tls=False, encrypt=True)
        return sorted([Station.from_json(j) for j in r['stations']],
                      key=attrgetter('name'))

    # FIXME maybe we want this
    def ____station(self, station):
        data = {
            'stationToken': station.token,
            'includeExtendedAttributes': True,
        }
        return self.request('station.getStation', data, tls=False,
                            encrypt=True)

    def playlist(self, station):
        data = {
            'stationToken': station.token,
        }
        r = self.request('station.getPlaylist', data, tls=True, encrypt=True)
        return Playlist.from_json(r)

    @property
    def sync_time(self):
        if not self.partner_sync_time:
            return None
        return self.partner_sync_time + int(time.time()) - \
            self.client_start_time

    def __repr__(self):
        return '<Pandora {}>'.format(self.user)


class Encryptor(object):
    def __init__(self, encryption_key, decryption_key):
        self.encryption_key = encryption_key
        self.decryption_key = decryption_key

    def _cipher(self, key):
        backend = cryptography.hazmat.backends.default_backend()
        return Cipher(algorithms.Blowfish(key), modes.ECB(), backend)

    def decrypt(self, data):
        decryptor = self._cipher(self.decryption_key).decryptor()
        r = decryptor.update(data) + decryptor.finalize()
        return self._unpad(r)

    def encrypt(self, data):
        data = self._pad(data, 8)
        encryptor = self._cipher(self.encryption_key).encryptor()
        return encryptor.update(data) + encryptor.finalize()

    def _pad(self, data, blocksize):
        pad_size = len(data) % blocksize
        return data + (chr(pad_size) * (blocksize - pad_size)).encode('utf-8')

    def _unpad(self, data):
        pad_size = data[-1]
        assert data[-pad_size:] == bytes((pad_size,)) * pad_size
        return data[:-pad_size]

import datetime


class Station(object):
    created = None
    quickmix = None
    shared = None
    id = None
    name = None
    token = None

    @classmethod
    def from_json(cls, json):
        r = cls()
        r.created = datetime.datetime.utcfromtimestamp(
            json['dateCreated']['time']/1000)
        r.quickmix = json['isQuickMix']
        r.shared = json['isShared']
        r.id = json['stationId']
        r.name = json['stationName']
        r.token = json['stationToken']
        return r

    def __repr__(self):
        return '<Station {}>'.format(self.name)


class Playlist(object):
    def __init__(self, songs):
        self.songs = songs

    @classmethod
    def from_json(cls, json):
        return cls([Song.from_json(j) for j in json['items']])

    def __repr__(self):
        return repr(self.songs)


class Song(object):
    album_art = None
    album_name = None
    artist_name = None
    name = None
    audios = None

    @classmethod
    def from_json(cls, json):
        r = cls()
        r.album_art = json['albumArtUrl']
        r.album_name = json['albumName']
        r.artist_name = json['artistName']
        r.name = json['songName']
        r.audios = {}
        for name, desc in json['audioUrlMap'].items():
            r.audios[name] = SongAudio.from_json(desc)

        return r

    def __repr__(self):
        return '<Song "{}" by "{}" on "{}">'.format(self.name,
                                                    self.artist_name,
                                                    self.album_name)


class SongAudio(object):
    url = None
    bitrate = None
    encoding = None
    protocol = None

    @classmethod
    def from_json(cls, json):
        r = cls()
        r.url = json['audioUrl']
        r.bitrate = int(json['bitrate'])
        r.encoding = json['encoding']
        r.protocol = json['protocol']
        return r

    def __repr__(self):
        return '<SongAudio {}:{}@{}>'.format(self.protocol, self.encoding,
                                             self.bitrate)


class AudioQuality(object):
    highQuality = 'highQuality'
    mediumQuality = 'mediumQuality'
