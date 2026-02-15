# Readme
Struktur folder dan file harus seperti ini:

folder/

├── PlaylistApp.exe

├── fonts/               ✅

└── bin/

    ├── ffmpeg           ✅
    
    ├── ffprobe          ✅
    
    └── yt-dlp           ✅


    ### app.py
    This is the main application file that initializes and runs the Playlist App. It handles user interactions and orchestrates the overall functionality of the application.

    ### downloadmanager.py
    This file is responsible for managing the download processes. It interfaces with external tools like `yt-dlp` to download videos and audio from various sources, ensuring efficient and reliable downloads.
