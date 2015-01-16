import os
import time
from operator import attrgetter

import click

from . import api
from .downloader import Downloader


FOREVER = -1


def info(message, *args, **kwargs):
    click.echo(click.style(message.format(*args, **kwargs), 'blue'))


@click.group()
@click.option('--config', help='configuration file to load',
              default=os.path.join(click.get_app_dir('pianobar'), 'config'),
              type=click.File('r'))
@click.pass_context
def main(ctx, config):
    settings = {}
    for line in config.readlines():
        line = line.strip()
        if line and line[0] != '#':
            k, v = line.split('=')
            settings[k.strip()] = v.strip()
    ctx.obj = api.Pandora(user=settings['user'],
                          password=settings['password'],
                          proxy=settings['proxy'])


@main.group()
def station():
    pass


@station.command('list')
@click.pass_context
def station_list(ctx):
    pandora = ctx.find_object(api.Pandora)
    pandora.auth()

    for i, station in enumerate(pandora.stations()):
        click.echo('{:2}: {} ({})'.format(i, station.name, station.id))


@main.command()
@click.argument('station')
@click.option('--target', help='where to store files',
              default='.',
              type=click.Path(exists=True, file_okay=False, writable=True))
@click.option('--add-station-tags/--no-add-station-tags', default=True)
@click.option('--sleep/--no-sleep', default=True)
@click.option('--count', default=FOREVER, type=int,
              help='amount of songs to download')
@click.option('--sleep-factor', default=1.0, type=float,
              help='which fraction of a job to sleep')
@click.pass_context
def download(ctx, station, target, add_station_tags, sleep, count,
             sleep_factor):
    if count != FOREVER:
        raise Exception('not implemented')

    pandora = ctx.find_object(api.Pandora)
    downloader = Downloader(target)
    pandora.auth()

    stations = pandora.stations()

    station = find_station(station, stations)

    if not station:
        click.echo('Station not found')
        return -1

    else:
        info('Downloading station "{}" to {}"', station.name, target)

    while True:
        playlist = pandora.playlist(station)
        info('Got songs {}', ', '.join(
            map(attrgetter('name'), playlist.songs)))

        for song in playlist.songs:
            info('Downloading {}', song.name)
            length = downloader.download(song)

            if add_station_tags:
                info('Tagging with {}', station)
                downloader.add_station_tag(song, station)

            if sleep:
                sleep_length = sleep_factor * length
                info('Sleeping {} seconds', sleep_length)
                time.sleep(sleep_length)


def find_station(criterion, stations):
    for i, station in enumerate(stations):
        if criterion in (station.id, station.name, str(i)):
            return station
