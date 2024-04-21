Python Music Player
====================

The music player is in the "minimal viable product" stage. It has the following functionality currently:

- loads all music from specified directories
- extracts basic ID3 metadata tags
- plays through music continuously (i.e. you do not need to manually select a new song each time the previous one ends)
- displays time elapsed in a given track and allows time seeking without stuttering (The Tkinter example provided by VLC uses a hack to circumvent stuttering while updating time per tick and while seeking, but this program uses a more stable method)
- displays album cover if present
- displays all tracks and binds double click to play
- threading to speed up data processing times

Functionality in development:
- saving data with manual refresh option
- add in-app preference editing
- non-VLC fallback functionality
- changing themes in-app
- playing music by album, artist, or folder
- displaying lyrics from metadata

Some functionality I have planned for the future:
- responsive formatting
- equalizer
- constructing and playing playlists
- more complex ID3 tag handling and exploring other tag formats
- more themes (once I learn tcl better)
- ability to correct errors/gaps in metadata
- ability to fetch info from online sources

## How to run

To run you must have download VideoLans's [VLC](https://www.videolan.org/vlc/) (64 bit). This is to preserve the music quality. I'm currently working on a non-VLC fallback.

This is not in package form yet, so just clone the repo and run
```text
python -m venv venv
venv/Scripts/activate
python -m pip install -r requirements.txt
python player.py
```
inside the main folder.

You can change preferences in `data/preferences.json`. The defaults are
```JSON
{
    "music_directories": ["~/Music"],
    "extensions": [".mp3", ".mp4", ".wav"],
    "theme": "forest-dark"
}
```
where `music_directories` is a list of directories where the program can find music files; `extensions` is a list of extensions you want the program to find and play; and `theme` is the ttk theme.

This program relies on metadata from ID3 tags (which are the default format for music files). I suggest running your music library through [MP3tag](https://www.mp3tag.de/en/) before using the player if they don't have metadata attached. The biggest problem with MP3tag is that it formats multiple artists with a slash. This can become a problem if artists like AC/DC are included. I will likely implement the ability to edit relevant tags in the future.

## Credits

Interface icons are adapted from [apien](https://www.flaticon.com/authors/apien) on flaticon

The interface theme is the [Forest ttk theme](https://github.com/rdbende/Forest-ttk-theme) from [rdbende](https://github.com/rdbende)