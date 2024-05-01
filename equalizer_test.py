import vlc, time, sys

instance: vlc.Instance = vlc.Instance()
player: vlc.MediaPlayer = instance.media_player_new()
track: vlc.Media = instance.media_new("/assets/example_audio.mp3")
player.set_media(track)

preset_count = vlc.libvlc_audio_equalizer_get_preset_count()

for preset in range(preset_count):
    preset_name: bytes = vlc.libvlc_audio_equalizer_get_preset_name(preset)
    print(preset_name.decode(), end=": ")
    sys.stdout.flush()
    equalizer: vlc.AudioEqualizer = vlc.libvlc_audio_equalizer_new_from_preset(preset)
    player.set_equalizer(equalizer)
    player.play()
    for _ in range(5):
        print('.', end="")
        sys.stdout.flush()
        time.sleep(1)
    print("|")
    sys.stdout.flush()
    player.stop()
    if preset > 0:
        vlc.libvlc_audio_equalizer_release(equalizer)

# Release player and instance
player.release()
instance.release()