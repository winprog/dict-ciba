#!/usr/bin/env python3
import subprocess
import time
import threading
import os
import sys
import signal
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "word-capture"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LAST_WORD_FILE = CACHE_DIR / "last_word.txt"
PID_FILE = CACHE_DIR / "service.pid"


def get_word_under_mouse():
    try:
        result = subprocess.run(
            ["xdotool", "getmousedown", "0"],
            capture_output=True, text=True, timeout=1
        )
        return None
    except:
        pass

    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=1
        )
        window_name = result.stdout.strip() if result.returncode == 0 else ""
    except:
        window_name = ""

    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            x = y = None
            for line in lines:
                if line.startswith('X='):
                    x = int(line.split('=')[1])
                elif line.startswith('Y='):
                    y = int(line.split('=')[1])
            return x, y, window_name if x is not None else None
    except:
        pass
    
    return None


def get_selected_text():
    for selection in ["primary", "clipboard"]:
        try:
            result = subprocess.run(
                ["xclip", "-selection", selection, "-o"],
                capture_output=True, text=True, timeout=1
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                if text and len(text) < 100 and not text.startswith('file://'):
                    return text
        except:
            pass
    return None


def get_word_at_position(x, y):
    try:
        result = subprocess.run(
            ["xdotool", "mousemove", str(x), str(y), 
             "getwindowname", "getselection", "getclipboard"],
            capture_output=True, text=True, timeout=1
        )
    except:
        pass

    try:
        result = subprocess.run(
            ["xdotool", "key", "ctrl+c"],
            capture_output=True, text=True, timeout=1
        )
        time.sleep(0.05)
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    return None


class WordCaptureService:
    def __init__(self):
        self.running = False
        self.stopping = False
        self.last_word = ""
        self.last_mouse_pos = None
        self.callback = None
        self.poll_interval = 0.2
        self.mouse_check_interval = 10
        self._mouse_stationary_count = 0

    def start(self):
        if self.running:
            return
        
        self.stopping = False
        
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        self.running = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        print(f"Word capture service started (PID: {os.getpid()})")

    def stop(self):
        self.running = False
        self.stopping = True
        if PID_FILE.exists():
            PID_FILE.unlink()
        print("Word capture service stopped")

    def set_callback(self, callback):
        self.callback = callback

    def _monitor_loop(self):
        while self.running:
            try:
                if self.stopping:
                    time.sleep(0.05)
                    continue
                    
                result = subprocess.run(
                    ["xdotool", "getmouselocation", "--shell"],
                    capture_output=True, text=True, timeout=1
                )
                current_pos = None
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    x = y = None
                    for line in lines:
                        if line.startswith('X='):
                            x = int(line.split('=')[1])
                        elif line.startswith('Y='):
                            y = int(line.split('=')[1])
                    if x is not None:
                        current_pos = (x, y)
                
                if current_pos == self.last_mouse_pos and current_pos is not None:
                    self._mouse_stationary_count += 1
                else:
                    self._mouse_stationary_count = 0
                    self.last_mouse_pos = current_pos
                
                if self._mouse_stationary_count >= self.mouse_check_interval:
                    self._mouse_stationary_count = 0
                    selected = get_word_at_position(*self.last_mouse_pos) if self.last_mouse_pos else None
                    if selected and selected != self.last_word and not self.stopping:
                        self.last_word = selected
                        if self.callback:
                            self.callback(selected)
                        else:
                            self._default_handler(selected)
                
                selected = get_selected_text()
                if selected and selected != self.last_word and not self.stopping:
                    self.last_word = selected
                    if self.callback:
                        self.callback(selected)
                    else:
                        self._default_handler(selected)
            except Exception as e:
                pass
            
            time.sleep(self.poll_interval)
        print("Word capture service stopped monitoring")

    def _default_handler(self, word):
        if not self.stopping:
            print(f"Captured: {word}")


_service = None


def get_service():
    global _service
    if _service is None:
        _service = WordCaptureService()
    return _service


def start_service():
    get_service().start()


def stop_service():
    get_service().stop()


def on_capture(callback):
    get_service().set_callback(callback)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Word capture service for Ubuntu")
    parser.add_argument("command", choices=["start", "stop", "status"], 
                       help="Command to execute")
    args = parser.parse_args()
    
    if args.command == "start":
        import fcntl

        def signal_handler(signum, frame):
            stop_service()
            fcntl.fcntl(sys.stdin, fcntl.F_SETFL, fcntl.fcntl(sys.stdin, fcntl.F_GETFL) | os.O_NONBLOCK)
            try:
                sys.stdin.read()
            except:
                pass
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        start_service()
        while get_service().running:
            time.sleep(0.1)
    elif args.command == "stop":
        if PID_FILE.exists():
            with open(PID_FILE) as f:
                pid = int(f.read())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Sent stop signal to {pid}")
            except:
                print("Process not found")
            PID_FILE.unlink()
        else:
            print("Service not running")
    elif args.command == "status":
        if PID_FILE.exists():
            with open(PID_FILE) as f:
                pid = int(f.read())
            try:
                os.kill(pid, 0)
                print(f"Service running (PID: {pid})")
            except:
                print("Service not running (stale PID file)")
                PID_FILE.unlink()
        else:
            print("Service not running")
