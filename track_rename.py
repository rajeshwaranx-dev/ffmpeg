"""
track_rename.py — Builds FFmpeg -metadata arguments to rename audio & subtitle tracks
"""


def build_track_metadata_args(
    audio_tracks: list,
    subtitle_tracks: list,
    channel_name: str,
) -> list:
    """
    Returns a flat list of FFmpeg arguments for renaming:
      - Each audio track  →  "{channel_name} - {Language}"
      - Each subtitle track → "{channel_name}"

    Example output:
        [
          "-metadata:s:a:0", "title=@TechifyBots - Tamil",
          "-metadata:s:a:1", "title=@TechifyBots - Telugu",
          "-metadata:s:a:2", "title=@TechifyBots - Hindi",
          "-metadata:s:s:0", "title=@TechifyBots",
        ]
    """
    args = []

    for i, track in enumerate(audio_tracks):
        lang  = track["lang_name"]
        title = f"{channel_name} - {lang}"
        args += [f"-metadata:s:a:{i}", f"title={title}"]

    for i, _ in enumerate(subtitle_tracks):
        args += [f"-metadata:s:s:{i}", f"title={channel_name}"]

    return args
    
