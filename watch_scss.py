from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import subprocess

class SCSSHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.scss'):
            print("SCSS changed, compiling...")
            subprocess.run(['python3', 'compile.py'])

if __name__ == "__main__":
    event_handler = SCSSHandler()
    observer = Observer()
    observer.schedule(event_handler, path='scss', recursive=True)
    observer.start()
    print("Watching SCSS files for changes...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()