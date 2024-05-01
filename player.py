from tkinter import ttk
import tkinter as tk
import pandas as pd
import pathlib as pl
from PIL import Image
from PIL import ImageTk as itk
import winsdk.windows.foundation
import winsdk.windows.foundation.collections
import winsdk.windows.media
import winsdk.windows.media.control
import winsdk.windows.media.core
import winsdk.windows.media.playback
import data_processing as data
from dataclasses import dataclass
from collections import namedtuple

import vlc, os, time, ctypes, winsdk, asyncio, log

import winsdk.windows

## TODO: Load album images during launch if launch gets too slow
## TODO: Add preferences editing
## TODO: Add equalizer
## TODO: Albums Tab
## TODO: Artists Tab
## TODO: Playlists
## TODO: Theme changing
## TODO: failsafe music playing without VLC
## TODO: make prev button skip to beginning of current song and then go to previous song


@dataclass
class Status:
    stopped: bool = True
    playing: bool = False
    seeking: bool = False

@dataclass
class Sizes:
    m: int = 75
    s: int = 30
    xs: int = 20

@dataclass
class Icons:
    play: itk.PhotoImage = None
    pause: itk.PhotoImage = None
    next: itk.PhotoImage = None
    prev: itk.PhotoImage = None
    vol: itk.PhotoImage = None

class WinMedia:
    def __init__(self) -> None:
        self.manager = winsdk.windows.media.control.GlobalSystemMediaTransportControlsSessionManager
    
    async def get_media_info(self):
        sessions = await self.manager.request_async()
        current_session = sessions.get_current_session()
        if current_session:
            info = await current_session.try_get_media_properties_async()
            info_dict = {song_attr: info.__getattribute__(song_attr) for song_attr in dir(info) if song_attr[0] != '_'}
            info_dict['genres'] = list(info_dict['genres'])
            return info_dict
        return None

    def setup(self, record):
        try:
            WM_APPCOMMAND = 0x0319
            APPCOMMAND_MEDIA_PLAY_PAUSE = 14
            APPCOMMAND_MEDIA_NEXTTRACK = 11
            APPCOMMAND_MEDIA_PREVIOUSTRACK = 12
            ctypes.windll.user32.PostMessageW(
                ctypes.windll.user32.GetForegroundWindow(),
                WM_APPCOMMAND,
                0,
                APPCOMMAND_MEDIA_PLAY_PAUSE * 65536
            )
        except Exception as e: log.warning(e)

class MusicPlayer:
    def __init__(self, root: tk.Tk, lib: data.Library):
        #### DEFAULT VALUES ####
        self.tick_len: int = 200
        self.seek_lag: int = 0
        self.track_len: int = 0
        self.track_idx: int = 74
        self.starting_volume: int = 100

        self.sizes = Sizes()
        self.status = Status()

        #### MAIN SETUP ####
        self.root = root
        self.root.title("Music Player")
        self.root.minsize(width=350, height=510)
        self.root.bind("<Configure>", self.on_config)
        self.root.update()

        # vlc player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        # windows controls (TODO: adjust for mac/linux)
        self.win = WinMedia()
        
        # data
        self.lib = lib
        self.df = self.lib.tracks_df

        #### THEME / AESTHETICS ####
        root.tk.call('source', 'assets/forest-dark.tcl')
        ttk.Style().theme_use('forest-dark')
        
        # load icons
        col = 'g' if self.lib.prefs.aes.theme == 'forest_dark' else 'b'
        self.icons = Icons()
        for i in self.icons.__dict__.keys():
            if (path := pl.Path('assets/img')/f"{i}_{col}.png").exists():
                size = self.sizes.s
                if i in ['play', 'pause']: size = self.sizes.m
                elif i in ['vol']: size = self.sizes.xs
                self.icons.__dict__[i] = itk.PhotoImage(Image.open(path).resize((size,size)))
        
        #### LAYOUT ####
        self.f_main = ttk.Frame(self.root)
        self.f_top = ttk.Frame(self.f_main) # top controls
        self.f_bottom = ttk.Frame(self.f_main) # main content

        self.f_ctrl = ttk.Frame(self.f_bottom) # music controls
        self.f_timer = ttk.Frame(self.f_ctrl) # time slider
        self.f_info = ttk.Frame(self.f_ctrl) # current track info

        self.f_list = ttk.Frame(self.f_bottom) # list of tracks
        
        ## Widgets ##
        # Canvas
        self.canvas_size = self.lib.prefs.aes.img_size
        self.picture = tk.Canvas(self.f_ctrl, width=self.canvas_size, height=self.canvas_size,
                                 relief="raised", borderwidth=3)

        self.picture.grid(row=0, column=0, columnspan=3, pady=10)

        # Track info
        self.track_title_label = tk.Label(self.f_info, text="", anchor='w')
        self.track_artist_label = tk.Label(self.f_info, text="", anchor='w')

        self.track_title_label.pack(side=tk.TOP)
        self.track_artist_label.pack(side=tk.TOP)

        # Track Timer
        self.last_time = 0
        self.time = tk.DoubleVar()

        self.time_slider = tk.Scale(self.f_timer, variable=self.time, command=self.on_time,
                                   from_=0, to=10000, orient=tk.HORIZONTAL, relief=tk.FLAT, showvalue=False,
                                   sliderrelief=tk.FLAT, sliderlength=6, troughcolor="#5D5D5D", foreground="#08a3d3",
                                   repeatdelay=10, repeatinterval=3000, length=300)
        self.time_start = ttk.Label(self.f_timer, text="{:02d}:{:02d}".format(0,0))
        self.time_end = ttk.Label(self.f_timer, text='--:--.--')

        self.time_start.pack(side=tk.LEFT, padx=5)
        self.time_end.pack(side=tk.RIGHT, padx=5)
        self.time_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Song List
        self.fill_all_artists(self.f_list)

        # Buttons
        # volume
        self.volume = tk.IntVar()
        self.volume_label = tk.Label(self.f_top, image=self.icons.vol)
        self.volume_scale = ttk.Scale(self.f_top, variable=self.volume, from_=0, to=100,
                                      orient=tk.HORIZONTAL, command=self.on_volume)
        self.volume_scale.set(self.starting_volume)

        self.volume_scale.pack(side=tk.RIGHT, padx=5)
        self.volume_label.pack(side=tk.RIGHT)
        
        # track control buttons
        self.play_pause_button = tk.Button(self.f_ctrl, image=self.icons.play, command=self.play_pause,
                                           width=self.sizes.m, height=self.sizes.m, borderwidth=0, relief=tk.FLAT,
                                           activebackground="#323232")
        self.prev_button = tk.Button(self.f_ctrl, image=self.icons.prev, command=self.prev_song,
                                     width=self.sizes.s, height=self.sizes.s, borderwidth=0, relief=tk.FLAT,
                                     activebackground="#323232")
        self.next_button = tk.Button(self.f_ctrl, image=self.icons.next, command=self.next_song,
                                     width=self.sizes.s, height=self.sizes.s, borderwidth=0, relief=tk.FLAT,
                                     activebackground="#323232")
        
        self.prev_button.grid(row=3, column=0, sticky='e')
        self.play_pause_button.grid(row=3, column=1, pady=10, sticky='ew')
        self.next_button.grid(row=3, column=2, sticky='w')

        ## Pack Frames ##
        self.f_main.pack(fill=tk.BOTH, expand=True)
        self.f_top.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        self.f_bottom.grid(row=1, column=0, sticky='ew')

        self.f_info.grid(row=1, column=0, columnspan=3, sticky='sew')
        self.f_timer.grid(row=2, column=0, columnspan=3, sticky='new')

        self.f_ctrl.pack(side=tk.RIGHT, fill=tk.X, pady=10, padx=20, expand=True)
        self.f_list.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=10, pady=20)

        #### TICK ####
        self.tick()

        #### KEYBINDS ####
        # TODO: use keybinds in preferences
        self.root.bind("<XF86AudioPlay>", self.play_pause_press)
        self.root.bind("<Right>", self.next_press)
        self.root.bind("<Left>", self.prev_press)

    def play_pause_press(self, _):
        self.play_pause()
    def next_press(self, _):
        self.next_song()
    def prev_press(self, _):
        self.prev_song()
    
    def load_album_image(self, image):
        self.album_image = itk.PhotoImage(image)
        self.picture.config(borderwidth=0, relief=tk.FLAT)
        self.picture.create_image(self.canvas_size/2,self.canvas_size/2, image = self.album_image)

    def fill_albums(self, frame: ttk.Frame):
        pass
            
    def change_select(self, event):
        if isinstance(event, tk.Event):
            cmd = "prev" if event.keysym == "Up" else "next"
        else:
            cmd = event
        print(cmd, event, isinstance(event, tk.Event))
        length = len(self.treeview.get_children())
        self.tree_select = (self.tree_select + (1,-1)[cmd=="prev"])%length
        self.treeview.selection_set(self.tree_select)
        self.treeview.focus(self.treeview.get_children()[self.tree_select])
        self.treeview.see(self.treeview.focus())

    def fill_all_artists(self, frame: ttk.Frame):
        self.scrollbar = ttk.Scrollbar(frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.treeview = ttk.Treeview(frame, selectmode="browse",
                                     yscrollcommand=self.scrollbar.set, columns=(1,2,3), height=10)
        self.treeview.pack(expand=True, fill=tk.BOTH)
        self.scrollbar.config(command=self.treeview.yview)

        self.treeview.column("#0", anchor="w", width=300)
        self.treeview.heading("#0", text="Title", anchor="w")
        self.treeview.column(1, anchor="w", width=150)
        self.treeview.heading(1, text="Artist", anchor="w")
        self.treeview.column(2, anchor="w", width=150)
        self.treeview.heading(2, text="Album", anchor="w")
        self.treeview.column(3, anchor="center", width=40)
        self.treeview.heading(3, text="#", anchor="center")
        
        self.df = self.df.sort_values(by=['albumartist', 'album', 'tracknumber', 'title']).reset_index(drop=True)
        for i, item in self.df.iterrows():
            artist = item.artist
            album = 'Single' if pd.isna(item.album) else item.album
            tracknumber = item.tracknumber if item.tracknumber > 0 else ''
            self.treeview.insert('', index="end", iid=i, text=item.title, values=[artist, album, tracknumber])

        # Select and scroll
        self.tree_select = self.track_idx
        self.treeview.selection_set(self.tree_select)
        self.treeview.focus(self.tree_select)
        self.treeview.see(self.treeview.focus())
        self.root.bind('<Double-1>', self.play_selection)
        self.root.bind('<Return>', self.play_selection)
        self.root.bind('<Up>', self.change_select)
        self.root.bind('<Down>', self.change_select)

    def play_selection(self, e):
        self.stop()
        selected_index = int(self.treeview.focus())
        if selected_index != None:
            self.track_idx = selected_index
            self.play()
    
    def play_pause(self):
        self.status.playing = not self.status.playing
        if self.status.playing == False:
            self.pause()
            self.play_pause_button.config(image=self.icons.play)
        else:
            self.play()
            self.play_pause_button.config(image=self.icons.pause)

    def setup_track(self):
        track = self.df.iloc[self.track_idx]
        self.media_display_info = {
            "AlbumArtist": track['albumartist'],
            "AlbumTitle": track['album'],
            "AlbumTrackCount": track['tracknumber'],
            "Title": track["title"],
            "Artist": track["artist"]
        }
        track_path = track["path"]
        media = self.instance.media_new(track_path)
        self.player.set_media(media)
        self.reset_slider()
        self.track_len = self.player.get_length()
        self.player.play()

        title = track["title"]
        artists = track["artist"]
        image = track["image"]
        self.update_track_info(title, artists)
        self.load_album_image(image)

    def play(self):
        if self.status.stopped: self.setup_track()
        else: self.player.play()
        self.status.stopped = False
    
    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()
        if self.status.playing == True:
            self.play_pause_button.config(image=self.icons.play)
            self.status.playing = False
        self.reset_slider()
        self.status.stopped = True

    def reset(self):
        self.player.set_time(0)

    def reset_slider(self):
        self.last_time = 0
        self.time_start.config(text="{:02d}:{:02d}".format(0,0))
        self.time.set(0)

    def next_song(self):
        self.stop()
        self.track_idx = (self.track_idx + 1) % len(self.df)
        self.play()
        self.change_select('next')

    def prev_song(self):
        self.stop()
        self.track_idx = (self.track_idx - 1) % len(self.df)
        self.play()
        self.change_select('prev')

    def on_volume(self, vol):
        self.player.audio_set_volume(round(float(vol)))

    def update_track_info(self, title, artists):
        self.track_title_label.config(text=title)
        self.track_artist_label.config(text=artists)
    
    def on_config(self, *args):
        pass
    
    def on_time(self, *args):
        if self.player:
            if self.player.is_playing():
                self.player.pause()
            self.seek_lag = time.time()
            t = self.player.get_time()
            m2, r2 = divmod(max(t,0), 60000)
            self.time_start.config(text="{:02d}:{:02d}".format(m2,r2//1000))
            if self.status.seeking == False:
                self.status.seeking = True
                self.check_seeking()
    
    def check_seeking(self):
        if (time.time() - self.seek_lag)*1e3 < 300:
            m2, r2 = divmod(max(int(self.time.get()),0), 60000)
            self.time_start.config(text="{:02d}:{:02d}".format(m2,r2//1000))
            self.root.after(max(10,self.tick_len/100), self.check_seeking)
        else:
            self.status.seeking = False
            t = self.time.get()
            self.player.set_time(int(t))
            self.player.play()

    def tick(self):
        if self.player:
            self.track_len = self.player.get_length()
            m, r = divmod(self.track_len, 60000)
            if self.track_len > 0:
                self.time_slider.config(to=self.track_len)
                self.time_end.config(text="{:02d}:{:02d}".format(m,r//1000))
                t = max(self.player.get_time(), 0)
                if t > self.last_time:
                    self.time.set(t)
                    m2, r2 = divmod(self.player.get_time(), 60000)
                    self.time_start.config(text="{:02d}:{:02d}".format(m2,r2//1000))
                    self.last_time = t
                elif (self.track_len - self.player.get_time()) <= self.tick_len and not self.player.is_playing() and not self.status.stopped:
                    self.time_start.config(text="{:02d}:{:02d}".format(m,r//1000))
                    self.next_song()
        self.root.after(self.tick_len, self.tick)
        

if __name__ == "__main__":
    library = data.Library()
    root = tk.Tk()
    music_player = MusicPlayer(root, lib=library)
    root.mainloop()