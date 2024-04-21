"""
main data processing module (TODO)
"""
import json, mutagen, os
import pathlib as pl
import mutagen.id3
import pandas as pd
import warnings, log

def setup():
    lib = Library()

class ID3Tag:
    def __init__(self, id:str, supported:bool = True, val_dict:dict[str,] = {}, depth:int = 0):
        self.id = id
        self.supported = supported
        self.depth = depth
        self.tag_type:str = val_dict.get('tag_type')
        self.complete_tag(val_dict)
        if not self.tag_type: self.tag_type = "X"
        if not self.__dict__.get("name"): self.name:str = id
    
    def __str__(self):
        d = self.depth
        if d == 0: ret = "{:35s}{:11s}{:s}"
        else: ret = " "*((d-1)*3)+"|_ "+"{:"+str(32-(d-1)*3)+"s}{:11s}{:s}"
        if not self.supported: return ret.format(self.id, "<NULL>", "Unsupported")
        ret = ret.format(self.id,self.tag_type,self.name)
        if self.tag_type == "struct": return ret+f"\n{self.subtags}"
        return ret
    
    def complete_tag(self, val_dict:dict[str,]) -> None:
        if not self.supported: return None
        match self.tag_type:
            case "str": self.__dict__.update(val_dict)
            case "list": self.__dict__.update(val_dict)
            case "map": self.__dict__.update(val_dict)
            case "copy":
                self.copy_id:str = val_dict.get('copyOf')
                self.copy_d:int = val_dict.get('copyDepth')
                if self.copy_id == None or self.copy_d == None:
                    log.warning(f"[{self.id}] Can't copy {self.copy_id} at depth {self.copy_d}")
                    self.supported = False
                    return None
            case "struct":
                self.__dict__.update(val_dict)
                sub_dict = val_dict.get('subtags')
                if sub_dict: self.subtags = ID3TagList(sub_dict, depth = self.depth+1)
                else: 
                    log.warning(f"[{self.id}] Type is 'struct', but no subtags are provided")
                    self.supported = False
                    return None
            case _:
                log.warning(f"[{self.id}] Type {self.tag_type} is unrecognized")
                self.supported = False
                return None
    
    def get_subtag_ids(self, supported_only=False):
        if not self.supported or not self.tag_type == "struct": return list()
        ids = list()
        iter_t = self.subtags.supported_tags if supported_only else self.subtags.tags
        for st in iter_t: ids += st.get_subtag_ids() + [st.id]
        return ids
    
    def get_value(self, meta):
        if not self.supported: return None
        try:
            match self.tag_type:
                case "str": return meta.getall(self.id)[0].text[0]
                case "int": return int(meta.getall(self.id)[0].text[0])
                case "list": return meta.getall(self.id)[0].text[0].split('/')
                case "map": return meta.getall(self.id)[0].text[0] # TODO: map values
                case "struct": return meta.getall(self.id)[0] # TODO: implement struct
        except:
            log.warning(f"Couldn't extract values for {self.id}")
            return None

class ID3TagList:
    def __init__(self, tag_dict:dict[str,dict[str,]], depth:int = 0):
        self.tags: list[ID3Tag] = list()
        self.depth = depth
        self.construct_list(tag_dict)
        self.supported_tags = [t for t in self.tags if t.supported]
    
    def __str__(self):
        ret = "\n".join([str(t) for t in self.tags])
        if self.depth == 0: return ("{:35s}{:11s}{:s}\n"+"="*80+"\n").format("Tag", "Type", "Name")+ret+"\n"+"="*80
        else: return ret
    
    def pprint(self, verbosity:int|None=2, supported_only=False):
        iter_t = self.supported_tags if supported_only else self.tags
        match verbosity:
            case 0:
                ids = list()
                for t in iter_t: ids += t.get_subtag_ids(supported_only) + [t.id]
                print(*ids, sep=", ")
            case 1:
                tag_fmts = ["{0} [{1}] <{2}>".format(t.id, t.name, t.tag_type) for t in iter_t]
                col = False
                for f in tag_fmts:
                    if len(f) > 50:
                        print("\n"*col+f)
                        col = False
                    else: print("{:50s}".format(f), end=("\n","")[col:=not col])
            case 2: print(self)
            case _: print(self)

    def update_supported(self) -> None:
        self.supported_tags = [t for t in self.tags if t.supported]
    
    def get_tag_by_id(self, id, depth:int=0) -> ID3Tag|None:
        if depth == 0:
            for tag in self.tags:
                if id == tag.id: return tag
        elif depth > 0:
            for tag in self.supported_tags:
                if tag.tag_type == "struct":
                    recursive_tag = tag.subtags.get_tag_by_id(id, depth=depth-1)
                    if recursive_tag: return recursive_tag
        return None
    
    def construct_list(self, tag_dict:dict[str,dict[str,]]) -> None:
        for tag, values in tag_dict.items():
            self.tags.append(ID3Tag(tag, supported=values.get('supported') or False, val_dict=values, depth=self.depth))

class Preferences:
    def __init__(self, directory:str = "./data/preferences.json"):
        self.music_directories: set[str] = []
        self.extensions: set[str] = []
        self.load_prefs(directory)
    
    def load_prefs(self, directory) -> None:
        with open(directory, "r") as f:
            prefs = json.load(f)
            self.dirs = set(prefs['music_directories'])
            self.exts = set(prefs['extensions'])

class Track:
    def __init__(self, path: pl.Path):
        self.path = path
        self.metadata = self.read_metadata()
        try: self.title: str|None = self.metadata.tags.getall('TIT2')[0].text[0]
        except: self.title = self.path.name
        try: self.artists: list[str] = self.metadata.tags.getall('TPE1')[0].text[0].split('/')
        except: self.artists = []
        try: self.album_artist: str|None = self.metadata.tags.getall('TPE2')[0].text[0]
        except: self.album_artist = None
        try: self.album: str|None = self.metadata.tags.getall('TALB')[0].text[0]
        except: self.album = None
        try: self.track_num: int|None = int(self.metadata.tags.getall('TRCK')[0].text[0])
        except: self.track_num = None
    
    def __repr__(self):
        return(f"Track('{self.path.name}')")
    
    def __str__(self):
        ret = f"{self.title} - "
        if self.album_artist:
            ret += self.album_artist+(f" with {', '.join(list(set(self.artists)-{self.album_artist}))}" if len(self.artists)>1 else'')
        else: ret += ", ".join(self.artists) if self.artists else "No Artist"
        if self.album: ret += f" ({self.album}{f', #{self.track_num}' if self.track_num else''})"
        return(ret)

    def read_metadata(self):
        audio = mutagen.File(self.path)
        return(audio)
    
    def to_dict(self):
        known_dict = {"Title": self.title, "Album Artist": self.album_artist, "Artists": "; ".join(self.artists),
                "Album": self.album, "Track #": self.track_num or 0}
        ref = make_id3_tags()
        for key in self.metadata.tags.keys():
            if key in ['TIT2', 'TPE1', 'TPE2', 'TALB', 'TRCK']: continue
            tag = ref.get_tag_by_id(key)
            if not tag: log.warning(f"[{self.title}] Can't find tag {key}"); continue
            try: known_dict.update({tag.name:tag.get_value(self.metadata.tags)})
            except: continue
        return(known_dict)

class Library:
    def __init__(self):
        self.prefs: Preferences = Preferences()
        self.tracks: list[Track] = list()
        self.track_paths: set[pl.Path] = set()
        self.update_library()
        self.df = self.load_df()

    def load_df(self) -> pd.DataFrame:
        return pd.DataFrame([t.to_dict() for t in self.tracks]).astype({"Track #":int})
    
    def update_track_paths(self) -> set[pl.Path]:
        return({track.path for track in self.tracks})
    
    def extract_albums(self) -> list[tuple[str, str]]:
        {(track.album_artist[0], track.album) for track in self.tracks}

    def update_library(self) -> list[Track]:
        files = set()
        for d in self.prefs.dirs:
            for ext in self.prefs.exts:
                files = files.union({f for f in pl.Path(d).rglob(f'*{ext}') if f.is_file()})
        self.tracks = [track for track in self.tracks if not track.path in self.track_paths - files] # remove missing tracks
        self.tracks += [Track(path) for path in files - self.track_paths] # add new tracks to list
        self.update_track_paths()

def copy_tags(tag, base) -> ID3Tag:
    for key, val in base.__dict__.items():
        if not "__" in key and not callable(base.__dict__[key]):
            tag.__dict__.update({key:val})
    return tag

def make_id3_tags(directory:str = "./data/reference.json") -> ID3TagList:
    with open(directory, "r") as f:
        tag_dict:dict[str,dict[str,]] = json.load(f)['id3_tags']
    tag_list = ID3TagList(tag_dict)
    for tag in tag_list.supported_tags:
        if tag.tag_type == "copy":
            copy_tag = tag_list.get_tag_by_id(tag.copy_id, depth=tag.copy_d)
            if copy_tag: tag = copy_tags(tag, copy_tag)
            else:  log.warning(f"{tag.id} is a copy of {tag.copy_id}, but {tag.copy_id} doesn't exist at depth ({tag.copy_d})")
    
    return tag_list