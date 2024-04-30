import pathlib as pl
import pandas as pd
import performance as pf

import mutagen.id3
from mutagen.easyid3 import EasyID3

from PIL import Image
from collections import namedtuple

import itertools, threading, io, json, os, log

class Keys:
    def __init__(self) -> None:
        with open("./data/references.json", "r") as f:
            ref:dict = json.load(f)
            self.keybind_map:dict[str,str] = ref['keybinds']
            self.key_map:dict[str,str] = ref['keys']
        self.keybind_names = self.keybind_map.keys()
        self.key_names = self.key_map.keys()

class Preferences:
    def __init__(self, directory:str = "./data/preferences.json") -> None:
        self.load_prefs(directory)
    
    def load_prefs(self, directory) -> None:
        with open(directory, "r") as f:
            prefs = json.load(f)
            self.fill_load(prefs)
            self.fill_aes(prefs)
            self.fill_correct(prefs)
    
    def fill_load(self, prefs: dict):
        Load = namedtuple('Load', ['dirs', 'exts'])
        dirs, exts = ["~/Music"], [".mp3", ".mp4", ".wav"]
        items:dict[str,] = prefs.get('load')
        if items:
            dirs = items.get('music_directories') or dirs
            exts = items.get('extensions') or exts
        else: log.warning("load preferences not found")
        self.load = Load(dirs=dirs, exts=exts)
    
    def fill_aes(self, prefs: dict):
        Aes = namedtuple('Aes', ['theme', 'img_size'])
        theme = 'forest_dark'
        img_size = 250
        items:dict[str,] = prefs.get('load')
        if items:
            theme = items.get('theme') or theme
            img_size = max(50,items['img_size']) if items.get('img_size') else img_size
        else: log.warning("aesthetic preferences not found")
        self.aes = Aes(theme=theme, img_size=img_size)
    
    def fill_correct(self, prefs: dict):
        Correct = namedtuple('Correct', ['slash'])
        slash = ["AC/DC"]
        items:dict[str,] = prefs.get('load')
        if items:
            slash: str = items.get('theme') or slash
        else: log.warning("correction preferences not found")
        self.correct = Correct(slash=slash)
    
    def fill_keybinds(self, prefs: dict): #TODO: bind multiple keys
        Keybinds = namedtuple('Keybinds', [*prefs.keys()])
        items:dict[str,] = prefs.get('keybinds')
        maps = Keys()
        keybinds = maps.keybind_map
        if items:
            for key, bind_key in items.items():
                if not key in maps.keybind_names:
                    log.warning(f"keybind type {key} is not recognized")
                    continue
                bind = maps.key_map.get(bind_key)
                if bind:
                    keybinds.update({key, bind})
                else:
                    log.warning(f"key {bind_key} is not recognized")
                    
        else: log.warning("keybind preferences not found")
        self.keybinds = Keybinds(**keybinds)

class Artist: # currently working on the assumption that artist names are unique
    def __init__(self, name: str):
        self.name = name
    def __hash__(self):
        return hash(self.name)
    def __le__(self, other):
        return self.name <= (other.name if isinstance(other, Artist) else "")
    def __lt__(self, other):
        return self.name < (other.name if isinstance(other, Artist) else "")
    def __ge__(self, other):
        return self.name >= (other.name if isinstance(other, Artist) else "")
    def __gt__(self, other):
        return self.name > (other.name if isinstance(other, Artist) else "")
    def __eq__(self, other):
        return self.name == (other.name if isinstance(other, Artist) else "")
    def __str__(self):
        return self.name
    def __repr__(self):
        return f"Artist('{self.name}')"


class Track:
    ID_GEN = itertools.count(100000)
    def __init__(self, path: pl.Path, image_size:int):
        self.threads: list[threading.Thread] = list()
        self.active_threads = 0
        self.image_size = image_size
        self.image_path = pl.Path('assets/img/albums/default.png')
        self.id = str(next(self.ID_GEN))
        self.path = path
        self.filename = self.path.name
        self.albumartist_obj: Artist = None
        self.albumartist_id: str = None
        self.artists_objs: list[Artist] = []
        self.artists_ids: list[str] = []
        self.metadata = self.read_metadata()
        self.complete_track()
        for thread in self.threads:
            thread.join()
        self.metadata.update({'image':self.image})
        self._update_attr()
    
    def __repr__(self):
        return(f"Track('{self.filename}')")
    
    def __str__(self):
        return "{0} ({1})".format(self.title, "; ".join(self.artists))

    def complete_track(self):
        self.title: str = self.metadata.get('title') or self.filename
        self.artists = self.metadata.get('artist') or ["None"]
        if isinstance(self.artists, str):
            if self.artists == '': self.artists = ["None"]
            elif '/' in self.artists:  self.artists = self.artists.split('/')
            else: self.artists = [self.artists]
        #TODO: Find a better way of setting album artist (maybe after all track loaded, check most common artist in album)
        self.albumartist = self.metadata.get('albumartist') or self.artists[0]
        self.tracknumber = self.metadata.get('tracknumber') or 0
        self.metadata.update({'path':self.path, 'id': self.id, 'title':self.title, 'artists':self.artists,
                              'image_path': self.image_path, 'albumartist':self.albumartist,
                              'tracknumber': self.tracknumber})
                              
    def create_album_image(self):
        if not self.image_path == pl.Path('assets/img/albums/default.png'):
            buffer = io.BytesIO(self.image_data)
            with open(self.image_path, 'wb') as img:
                img.write(buffer.getvalue())
        self.image = Image.open(pl.Path(self.image_path))
        self.image = self.image.resize((self.image_size,self.image_size))
        self.active_threads -= 1

    def attach_artist(self, artist: Artist, main:bool= False):
        if main:
            self.albumartist_obj = artist
            self.metadata.update({'albumartist_obj': self.albumartist_obj})
        else:
            self.artists_objs.append(artist)
            self.metadata.update({'artists_objs': self.artists_objs})
    
    def read_metadata(self):
        meta: dict[str,] = dict()
        audio = mutagen.File(self.path)
        self.threads.append(th_image := threading.Thread(target=self.create_album_image))
        if 'APIC:' in audio.keys():
            self.image_path = f'assets/img/albums/{self.id}.jpg'
            self.image_data = audio.tags.getall('APIC:')[0].data
            meta.update({'image_data': self.image_data})
        self.active_threads += 1
        th_image.start()
        meta = {k:('',v[0],v)[min(2,len(v))] for k, v in EasyID3(self.path).items()}
        return meta

    def _update_attr(self):
        self.__dict__.update(self.metadata)
    
class Library:
    def __init__(self):
        self.threads: list[threading.Thread] = list()
        self.active_threads = 0
        self.prefs: Preferences = Preferences()
        self.tracks: list[Track] = list()
        self.artists: list[Artist] = list()
        self.track_paths: set[pl.Path] = set()
        self.update_library()
    
    def update_track_paths(self) -> set[pl.Path]:
        return({track.path for track in self.tracks})

    def update_tracks(self):
        files = set()
        dirs, exts = self.prefs.load
        for d in dirs:
            if '~' in d:
                d = pl.Path(d).expanduser()
            for ext in exts:
                files = files.union({f for f in pl.Path(d).rglob(f'*{ext}') if f.is_file()})
        self.tracks = [track for track in self.tracks if not track.path in self.track_paths - files] # remove missing tracks
        
        for path in files-self.track_paths:
            self.threads.append(th := threading.Thread(target=self.add_track, args=(path,)))
            self.active_threads += 1
            th.start()
    
    def add_track(self, path: pl.Path):
        track = Track(path, self.prefs.aes.img_size)
        self.update_artists(track)
        self.tracks.append(track)
        self.active_threads -= 1
    
    def update_artists(self, track):
        # due to limitations from tags, you can't have artists with the same name.
        # TODO: allow user to mark artists as different in-app and save that to preferences
        for artist in track.artists:
            artist_obj = Artist(artist)
            track.attach_artist(artist_obj, main=(artist == track.albumartist))
            if not artist in self.artists:
                self.artists.append(Artist(artist))
        # remove duplicates that could occur due to threading
        self.artists = list(set(self.artists))
        
    def update_library(self):
        self.update_tracks()
        for thread in self.threads:
            thread.join()
        self.update_track_paths()
        self.tracks_df = self.__construct_tracks_df()
    
    def __construct_tracks_df(self):
        return pd.DataFrame([t.metadata for t in self.tracks]).astype({'tracknumber': int})