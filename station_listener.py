# Code that listens to radio station and adds songs to spotify playlist
# Has no duplicates and pushes to spotify daily? maybe hourly?
# Could also pull from website or list which might be easier

import argparse
import config
import re
import logging
import time
import requests
import spotify
import spotipy
import json


# Used for doctering up the track and artist name for searching
def clean_string(string: str, remove_extra: bool = True):
    removal = ['the', 'feat', 'feat.', 'featuring']
    if remove_extra:
        temp = re.sub('[  ]+', ' ', re.sub('[^A-Za-z0-9$ñ& -]+', '', string.lower()))
    else:
        temp = re.sub('[  ]+', ' ', re.sub('[^A-Za-z0-9$ñ\. -]+', '', string.lower()))
    temp = temp.split()
    fixed = [word for word in temp if word not in removal]
    doctored = ' '.join(fixed)
    return doctored


# Used to get api url from base iHeart Radio station url
def api_url_find(iheart_url: str):
    main = requests.get(iheart_url)
    split = main.text[main.text.find("@id"):main.text.find("@type", main.text.find("@id"))].split('"')[2].split("/")
    if len(split) != 0:
        live = split[2].split("/")
        if len(live) != 0:
            api_url = "https://us.api.iheart.com/api/v3/live-meta/stream/" + live[-1] + "/currentTrackMeta"
            return api_url
    return None


# Argument parser set up
parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--url', '-U', type=str, help='Set iHeart radio station url defaults to config file')
parser.add_argument('--info', '-I', action='store_true', help='Used to set logging to info mode')
parser.add_argument('--debug', '-D', action='store_true', help='Used to set logging to debug mode')
parser.add_argument('--limit', '-L', type=int, default=250, help='Set upper limit of playlist size')

args = parser.parse_args()

# TODO - Config set up via GUI or command line options
# https://github.com/plamere/spotipy/issues/287#issuecomment-576896586

# Spotify API set up
scope = "user-library-read, playlist-modify-public"

oauth = spotipy.oauth2.SpotifyOAuth(username=config.spotify_username, scope=scope,
                                    client_id=config.spotify_client, client_secret=config.spotify_secret,
                                    redirect_uri="https://www.google.com/")
token = oauth.get_cached_token()
if not token:
    print(f"Copy/paste following link into a browser if it does not auto-open:\n{oauth.get_authorize_url()}")
    token = oauth.get_access_token(code=oauth.get_auth_response())
    print("Also paste redirect url in config under spotify_url")
else:
    token = spotipy.util.prompt_for_user_token(username=config.spotify_username, scope=scope,
                                               client_id=config.spotify_client, client_secret=config.spotify_secret,
                                               redirect_uri=config.spotify_uri)

# TODO - If playlist id not given create one
playlist_id = config.spotify_playlist
playlist_cont = []

# https://developer.spotify.com/documentation/web-api/reference/

# Logs set up
if args.debug:
    logging.basicConfig(filename='listener-debug.log', filemode='w',
                        format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=logging.DEBUG)
else:
    if args.info:
        logging.basicConfig(filename='listener-info.log', filemode='w',
                            format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                            level=logging.INFO)
    else:
        logging.basicConfig(filename='listener.log', filemode='w',
                            format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                            level=logging.WARNING)
logging.info('Log file for station_listener.py\n\n')

# TODO - Need better try/catch blocks
try:
    if token:
        sp = spotipy.Spotify(auth=token)
        sp.trace = False

        # TODO - Monitor multiple urls at once
        url = config.iheart_url
        if args.url:
            url = args.url

        api_url = api_url_find(url)

        playlist_cont = spotify.current_playlist_tracks()

        if len(playlist_cont) > args.limit > 0:
            spotify.clear_playlist()
            logging.warning(f'Playlist over {args.limit} songs! Clearing out and starting fresh')

        logging.info('Starting iHeart Radio listener')
        # TODO - What is better while loop or cron tab? Can python edit cron tab?
        while True:
            token = spotipy.util.prompt_for_user_token(username=config.spotify_username, scope=scope,
                                                       client_id=config.spotify_client,
                                                       client_secret=config.spotify_secret,
                                                       redirect_uri=config.spotify_uri)
            sp = spotipy.Spotify(auth=token)

            r = requests.get(api_url)
            if r.status_code == 200:
                artist = None
                track = None
                item = None

                try:
                    content = json.loads(r.text)
                    logging.info(f"iHeartRadio is listening to \"{content['title']}\" - {content['artist']}")
                    track = clean_string(content['title'])
                    artist = clean_string(content['artist'], False)

                    track_id, artists, name, popularity = spotify.search_spotify(artist, track)

                    if not track_id:
                        logging.warning(f"FAILED SPOTIFY SEARCH = Artist:{artist} Track:{track}")
                    else:
                        logging.info(f"Spotify found \"{name}\" - {','.join([artist['name'] for artist in artists])}\t"
                                     f"ID: {track_id}")
                        if track_id in playlist_cont:
                            logging.info("Song is already in playlist")
                            logging.info("--------------------------------------------------------------")
                        elif popularity < 60:
                            logging.info(f"Low song popularity ({popularity}) not added to playlist")
                            logging.info("--------------------------------------------------------------")
                        else:
                            playlist_cont.append(track_id)
                            spotify.add_track([track_id])
                            logging.info("Song has been added to the playlist")
                            logging.info("--------------------------------------------------------------")
                except Exception as e:
                    logging.warning(f'SPOTIFY SEARCH = artist:{artist} track:{track}')
                    logging.warning(f"RESULTS = {item}")
                    logging.exception("Exception occurred")
            elif r.status_code == 204:
                logging.info('Radio station is currently playing an ad')
                logging.info('--------------------------------------------------------------')
            else:
                logging.warning(f"Unknown error code {r.status_code} for {api_url}")
                logging.info('--------------------------------------------------------------')
            time.sleep(100)
    else:
        logging.error("Could not get token")
except Exception as e:
    logging.exception("Unexpected Exception occurred")
