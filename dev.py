import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os

class ReloadHandler(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.start_app()

    def start_app(self):
        if self.process:
            self.process.kill()
        self.process = subprocess.Popen(["python", "app.py"])

    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            print("Reloading...")
            self.start_app()

if __name__ == "__main__":
    event_handler = ReloadHandler()
    observer = Observer()
    observer.schedule(event_handler, ".", recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()