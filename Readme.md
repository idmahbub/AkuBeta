# Readme
Download and extract Zip:
folder/

├── PlaylistApp (executable file)

├── _internal (Lib and module included ffmpeg etc.)


    ### app.py
    This is the main application file that initializes and runs the Playlist App. It handles user interactions and orchestrates the overall functionality of the application.

    ### downloadmanager.py
    This file is responsible for managing the download processes. It interfaces with external tools like `yt-dlp` to download videos and audio from various sources, ensuring efficient and reliable downloads.

# mac build
``
    pyinstaller app.py \
    --name PlaylistApp \
    --windowed \
    --onedir \
    --clean \
    --noconfirm \
    --hidden-import=DownloadManager \
    --hidden-import=arabic_reshaper \
    --hidden-import=bidi.algorithm \
    --add-data "fonts:fonts" \
    --add-data "bin:bin"

``
# win build one dir
``
    pyinstaller app.py --name PlaylistApp --windowed --noconfirm --clean `
    --hidden-import arabic_reshaper `
    --hidden-import bidi.algorithm `
    --add-data "fonts;fonts" `
    --add-binary "bin/ffmpeg.exe;bin" `
    --add-binary "bin/ffprobe.exe;bin"
``