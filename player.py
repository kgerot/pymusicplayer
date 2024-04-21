from tkinter import ttk
import tkinter as tk
import pandas as pd
import pathlib as pl
import vlc, os, time
from PIL import Image
from PIL import ImageTk as itk
import base64, pickle, threading
import data_easy as data

## TODO: Load album images during launch if launch gets too slow
## TODO: Add preferences editing
## TODO: Add equalizer
## TODO: Albums Tab
## TODO: Artists Tab
## TODO: Playlists
## TODO: Theme changing
## TODO: failsafe music playing without VLC
## TODO: make prev button skip to beginning of current song and then go to previous song

class MusicPlayer:
    def __init__(self, root: tk.Tk, lib: data.Library):
        self.stopped = True
        self.playing = False
        self.tick_len = 300
        self.seek_lag = 0
        self.seeking = False
        self.track_len = 0

        self.root = root
        self.root.title("Music Player")

        ## LOAD ICONS
        self.icons = dict()
        p,s,xs,col = (75, 30, 20, 'g')
        t_ic = {'play':p, 'pause':p, 'next':s, 'prev':s, 'vol':xs}
        for k,v in t_ic.items():
            if (path := pl.Path('assets/img')/f"{k}_{col}.png").exists():
                ico = Image.open(path)
                ico = ico.resize((v,v))
                ico_pi = itk.PhotoImage(ico)
                self.icons.update({k: ico_pi})
                print(ico_pi)
        print(self.icons)

        ## LOAD THEME
        root.tk.call('source', 'assets/forest-dark.tcl')
        ttk.Style().theme_use('forest-dark')

        self.root.minsize(width=350, height=510)
        self.root.bind("<Configure>", self.on_config)
        self.root.update()

        ## LOAD VLC PLAYER
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        
        ## LOAD DATAFRAME
        self.lib = lib
        self.df = self.lib.tracks_df
        self.curr_track_idx = 0

        ## FRAMES
        self.f_main = ttk.Frame(self.root)
        self.f_top = ttk.Frame(self.f_main) # top controls
        self.f_bottom = ttk.Frame(self.f_main) # main content

        self.f_ctrl = ttk.Frame(self.f_bottom) # music controls
        self.f_timer = ttk.Frame(self.f_ctrl) # time slider
        self.f_info = ttk.Frame(self.f_ctrl) # current track info

        self.f_list = ttk.Frame(self.f_bottom) # List of tracks

        ##ICONS
        self.i_play = self.icons['play']
        self.i_pause = self.icons['pause']
        self.i_next = self.icons['next']
        self.i_prev = self.icons['prev']
        self.i_vol = self.icons['vol']
        
        ### WIDGETS
        # CANVAS
        self.canvas_size = 250
        self.picture = tk.Canvas(self.f_ctrl, width=self.canvas_size, height=self.canvas_size,
                                 relief="raised", borderwidth=3)

        self.picture.grid(row=0, column=0, columnspan=3, pady=10)

        # TRACK INFO
        self.track_title_label = tk.Label(self.f_info, text="", anchor='w')
        self.track_artist_label = tk.Label(self.f_info, text="", anchor='w')

        self.track_title_label.pack(side=tk.TOP)
        self.track_artist_label.pack(side=tk.TOP)

        # TRACK TIMER
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
        
        ## SONG LIST
        self.fill_all_artists(self.f_list)

        ### BUTTONS WITH ICONS
        ## Volume
        self.volume = tk.IntVar()
        self.volume_label = tk.Label(self.f_top, image=self.i_vol)
        self.volume_scale = ttk.Scale(self.f_top, variable=self.volume, from_=0, to=100,
                                      orient=tk.HORIZONTAL, command=self.on_volume)
        self.volume_scale.set(50)

        self.volume_scale.pack(side=tk.RIGHT, padx=5)
        self.volume_label.pack(side=tk.RIGHT)
        
        # Track Control Button
        self.play_pause_button = tk.Button(self.f_ctrl, image=self.i_play, command=self.play_pause,
                                           width=p, height=p, borderwidth=0, relief=tk.FLAT,
                                           activebackground="#323232")
        self.prev_button = tk.Button(self.f_ctrl, image=self.i_prev, command=self.prev_song,
                                     width=s, height=s, borderwidth=0, relief=tk.FLAT,
                                     activebackground="#323232")
        self.next_button = tk.Button(self.f_ctrl, image=self.i_next, command=self.next_song,
                                     width=s, height=s, borderwidth=0, relief=tk.FLAT,
                                     activebackground="#323232")
        
        self.prev_button.grid(row=3, column=0, sticky='e')
        self.play_pause_button.grid(row=3, column=1, pady=10, sticky='ew')
        self.next_button.grid(row=3, column=2, sticky='w')

        ## PACK FRAMES
        self.f_main.pack(fill=tk.BOTH, expand=True)
        self.f_top.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        self.f_bottom.grid(row=1, column=0, sticky='ew')

        self.f_info.grid(row=1, column=0, columnspan=3, sticky='sew')
        self.f_timer.grid(row=2, column=0, columnspan=3, sticky='new')

        self.f_ctrl.pack(side=tk.RIGHT, fill=tk.X, pady=10, padx=20, expand=True)
        self.f_list.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=10, pady=20)

        self.tick()
    
    def load_album_image(self, image):
        self.album_image = itk.PhotoImage(image)
        self.picture.config(borderwidth=0, relief=tk.FLAT)
        self.picture.create_image(self.canvas_size/2,self.canvas_size/2, image = self.album_image)

    def fill_albums(self, frame: ttk.Frame):
        pass
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
        self.treeview.selection_set(0)
        self.treeview.bind('<Double-1>', self.on_double_click)

    def on_double_click(self, e):
        self.stop()
        selected_index = int(self.treeview.focus())
        print(selected_index)
        if selected_index != None:
            self.curr_track_idx = selected_index
            self.setup_track()
            self.play()
    
    def play_pause(self):
        self.playing = not self.playing
        if self.playing == False:
            self.pause()
            self.play_pause_button.config(image=self.i_play)
        else:
            self.play()
            self.play_pause_button.config(image=self.i_pause)

    def setup_track(self):
        track_path = self.df.iloc[self.curr_track_idx]["path"]
        media = self.instance.media_new(track_path)
        self.player.set_media(media)
        self.reset_slider()
        self.track_len = self.player.get_length()
        self.player.play()

        title = self.df.iloc[self.curr_track_idx]["title"]
        artists = self.df.iloc[self.curr_track_idx]["artist"]
        image = self.df.iloc[self.curr_track_idx]["image"]
        self.update_track_info(title, artists)
        self.load_album_image(image)

    def play(self):
        if self.stopped: self.setup_track()
        else: self.player.play()
        self.stopped = False
    
    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()
        if self.playing == True:
            self.play_pause_button.config(image=self.i_play)
            self.playing = False
        self.reset_slider()
        self.stopped = True

    def reset(self):
        self.player.set_time(0)

    def reset_slider(self):
        self.last_time = 0
        self.time_start.config(text="{:02d}:{:02d}".format(0,0))
        self.time.set(0)

    def next_song(self):
        self.stop()
        self.curr_track_idx = (self.curr_track_idx + 1) % len(self.df)
        self.play()

    def prev_song(self):
        self.stop()
        self.curr_track_idx = (self.curr_track_idx - 1) % len(self.df)
        self.play()

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
            if self.seeking == False:
                self.seeking = True
                self.check_seeking()
    
    def check_seeking(self):
        if (time.time() - self.seek_lag)*1e3 < 300:
            m2, r2 = divmod(max(int(self.time.get()),0), 60000)
            self.time_start.config(text="{:02d}:{:02d}".format(m2,r2//1000))
            self.root.after(max(10,self.tick_len/100), self.check_seeking)
        else:
            self.seeking = False
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
                elif (self.track_len - self.player.get_time()) <= self.tick_len and not self.player.is_playing() and not self.stopped:
                    self.time_start.config(text="{:02d}:{:02d}".format(m,r//1000))
                    self.next_song()
        self.root.after(self.tick_len, self.tick)
        

if __name__ == "__main__":
    library = data.Library()
    root = tk.Tk()
    music_player = MusicPlayer(root, lib=library)
    root.mainloop()