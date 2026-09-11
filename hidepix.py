"""
HidePix - A deliberately useless "privacy" prank app 😂
-------------------------------------------------------
Implementation of HidePixApp Specification:
- FrontPage(): Cartoon decorative UI, DEMO MODE label, rounded emoji buttons, preview
- HidePhotoTrap(): Sets photo as Windows wallpaper + fake "Close Friends Alert"
- CloseFriendsSection(): Add/remove emails locally + the grand mystery of why emails were asked
- ResetTimer(): 5-minute lock with countdown + snake cartoon unlock + restore wallpaper
- PuzzleTrap(): Interactive mini-riddles; solving plays "Wow nice try!" voice without resetting
- MemeScreens(): Random meme refusal popups when reset is attempted early
- CuteVoiceOver(): Plays nope_voice.wav ("Nope! I'm not deleting that!"), replay button

100% LOCAL & SAFE:
- No internet connection required
- No real emails sent (mystery joke)
- Built with Python, Tkinter, Pillow, pygame/winsound, and ctypes
"""

import os
import sys
import json
import time
import math
import struct
import wave
import platform
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# --- Dependency check: Pillow ---
try:
    from PIL import Image, ImageTk
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# --- Dependency check: Pygame ---
try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception:
    HAS_PYGAME = False

APP_DIR = Path(__file__).parent.resolve()
FRIENDS_FILE = APP_DIR / "friends_list.json"
NOPE_VOICE_FILE = APP_DIR / "nope_voice.wav"
WOW_VOICE_FILE = APP_DIR / "wow_voice.wav"


# ================= AUDIO GENERATION & PLAYBACK =================

def synthesize_fallback_wav(filepath, tone_type="nope"):
    """
    Generates a cute cartoon 8-bit soundwave WAV file using Python's standard wave library.
    Ensures that audio files always exist on disk even with zero external setup.
    """
    sample_rate = 22050
    duration = 1.0 if tone_type == "nope" else 1.2
    total_samples = int(sample_rate * duration)

    wav_file = wave.open(str(filepath), 'w')
    wav_file.setnchannels(1)        # mono
    wav_file.setsampwidth(2)        # 16-bit
    wav_file.setframerate(sample_rate)

    frames = bytearray()
    for i in range(total_samples):
        t = float(i) / sample_rate
        if tone_type == "nope":
            # Two-tone cute "Uh-oh / Nope!" frequency sweep (480Hz -> 320Hz)
            freq = 520 if t < 0.35 else (310 if t < 0.75 else 260)
            decay = max(0.0, 1.0 - (t / duration) * 0.8)
        else:
            # Arpeggio fanfare for "Wow nice try!" (440Hz -> 554Hz -> 659Hz -> 880Hz)
            step = int(t * 4)
            freqs = [440, 554, 659, 880]
            freq = freqs[min(step, 3)]
            decay = max(0.0, 1.0 - (t / duration) * 0.5)

        # Generate harmonic sine + square wobble for cute cartoon sound
        value = int(16000 * decay * (0.7 * math.sin(2 * math.pi * freq * t) +
                                      0.3 * (1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0)))
        value = max(-32768, min(32767, value))
        frames.extend(struct.pack('<h', value))

    wav_file.writeframes(frames)
    wav_file.close()


def ensure_audio_assets():
    """
    Checks for nope_voice.wav and wow_voice.wav.
    Attempts Windows Speech Synthesis via PowerShell to render realistic voice,
    and cleanly falls back to cute synthesized cartoon waves if unavailable.
    """
    def generate_voice_sapi(target_path, spoken_text, tone_type):
        if target_path.exists():
            return
        # Try Windows SAPI SpeechSynthesizer via PowerShell
        if platform.system() == "Windows":
            try:
                ps_cmd = (
                    f"Add-Type -AssemblyName System.Speech; "
                    f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$synth.Rate = 1; "
                    f"$synth.SetOutputToWaveFile('{target_path.as_posix()}'); "
                    f"$synth.Speak('{spoken_text}'); "
                    f"$synth.Dispose();"
                )
                res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                                     capture_output=True, timeout=6)
                if res.returncode == 0 and target_path.exists() and target_path.stat().st_size > 1000:
                    return
            except Exception:
                pass
        # Fallback to pure-Python wave generation
        synthesize_fallback_wav(target_path, tone_type)

    if not NOPE_VOICE_FILE.exists():
        synthesize_fallback_wav(NOPE_VOICE_FILE, "nope")
    if not WOW_VOICE_FILE.exists():
        synthesize_fallback_wav(WOW_VOICE_FILE, "wow")

    threading.Thread(target=lambda: generate_voice_sapi(NOPE_VOICE_FILE, "Nope! I am not deleting that!", "nope"), daemon=True).start()
    threading.Thread(target=lambda: generate_voice_sapi(WOW_VOICE_FILE, "Wow nice try! It was fun, but still a prank!", "wow"), daemon=True).start()


def play_audio(wav_path, spoken_text_fallback=""):
    """Plays audio via pygame if available, or falls back to Windows winsound / SAPI."""
    def _run():
        played = False
        if HAS_PYGAME and wav_path.exists():
            try:
                sound = pygame.mixer.Sound(str(wav_path))
                sound.play()
                played = True
            except Exception:
                played = False

        if not played and platform.system() == "Windows":
            try:
                import winsound
                if wav_path.exists():
                    winsound.PlaySound(str(wav_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                    played = True
            except Exception:
                played = False

        # If audio device / sound files fail, try direct text-to-speech fallback
        if not played and platform.system() == "Windows" and spoken_text_fallback:
            try:
                ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{spoken_text_fallback}');"
                subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                               capture_output=True, timeout=5)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


# ================= WALLPAPER MANAGEMENT =================

def get_windows_wallpaper():
    """Reads current Windows desktop wallpaper from Registry so it can be restored."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
        value, _ = winreg.QueryValueEx(key, "WallPaper")
        winreg.CloseKey(key)
        return value
    except Exception:
        return None


def set_wallpaper_windows(image_path):
    """Sets wallpaper on Windows using ctypes SystemParametersInfoW."""
    import ctypes
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    abs_path = os.path.abspath(image_path)
    # SPI_SETDESKWALLPAPER = 20, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE = 3
    result = ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
    if not result:
        raise RuntimeError("Windows refused to set desktop wallpaper.")


def set_wallpaper_generic(image_path):
    """OS-agnostic wallpaper setter with Windows primary support."""
    sys_name = platform.system()
    if sys_name == "Windows":
        set_wallpaper_windows(image_path)
        return True, "Wallpaper successfully updated!"
    elif sys_name == "Darwin":  # macOS
        script = f'tell application "Finder" to set desktop picture to POSIX file "{os.path.abspath(image_path)}"'
        subprocess.run(["osascript", "-e", script], check=True)
        return True, "Wallpaper updated via AppleScript!"
    elif sys_name == "Linux":
        uri = f"file://{os.path.abspath(image_path)}"
        for schema in [["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
                       ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri]]:
            try:
                subprocess.run(schema, check=True)
                return True, "Wallpaper updated via gsettings!"
            except Exception:
                continue
    return False, f"Unsupported operating system: {sys_name}"


# ================= MAIN HIDEPIX APPLICATION CLASS =================

class HidePixApp:
    """
    HidePix Main Class matching the C++ specification:
    - FrontPage()
    - HidePhotoTrap()
    - CloseFriendsSection()
    - ResetTimer()
    - PuzzleTrap()
    - MemeScreens()
    - CuteVoiceOver()
    """

    def __init__(self, root):
        self.root = root
        self.root.title("HidePix — Military Grade Privacy™ 🔒😂")
        self.root.geometry("640x780")
        self.root.minsize(580, 720)
        self.root.configure(bg="#FDF6F0")  # Warm cartoon pastel cream

        # State variables
        self.selected_photo_path = None
        self.original_wallpaper = None
        if platform.system() == "Windows":
            self.original_wallpaper = get_windows_wallpaper()

        self.lock_seconds = 300       # 5 minutes lock
        self.time_left = 300
        self.is_locked = False
        self.timer_running = False
        self.friends_list = self.load_friends_list()

        # Generate audio assets on background thread
        ensure_audio_assets()

        # Render FrontPage
        self.FrontPage()

    # -------------------------------------------------------------
    # 1. FrontPage: Cartoon decorative UI, DEMO MODE label, buttons
    # -------------------------------------------------------------
    def FrontPage(self):
        """Constructs the cartoon decorative UI."""
        # Top Header Banner Frame
        header_frame = tk.Frame(self.root, bg="#6C5CE7", padx=16, pady=12)
        header_frame.pack(fill="x")

        title_label = tk.Label(
            header_frame,
            text="✨ HidePix 🔒 ✨",
            font=("Segoe UI", 24, "bold"),
            bg="#6C5CE7",
            fg="#FFFFFF"
        )
        title_label.pack()

        subtitle_label = tk.Label(
            header_frame,
            text="Ultra-Secret Photo Vault* (*we put it straight on your desktop)",
            font=("Segoe UI", 10, "italic"),
            bg="#6C5CE7",
            fg="#DFE6E9"
        )
        subtitle_label.pack()

        # Prominent DEMO MODE Badge
        demo_badge = tk.Label(
            header_frame,
            text="⚠️ DEMO MODE: USELESS PRANK EDITION • 100% LOCAL ⚠️",
            font=("Segoe UI", 9, "bold"),
            bg="#FDCB6E",
            fg="#2D3436",
            padx=10,
            pady=3,
            relief="solid",
            bd=1
        )
        demo_badge.pack(pady=(6, 0))

        # Main Scrollable / Stacked Body
        body_frame = tk.Frame(self.root, bg="#FDF6F0", padx=20, pady=10)
        body_frame.pack(fill="both", expand=True)

        # Name Entry Row (for gossip & fake notifications)
        name_row = tk.Frame(body_frame, bg="#FDF6F0")
        name_row.pack(pady=4)
        tk.Label(name_row, text="👤 Your Name for Gossip:", font=("Segoe UI", 10, "bold"),
                 bg="#FDF6F0", fg="#2D3436").pack(side="left", padx=(0, 8))
        self.name_entry = tk.Entry(name_row, font=("Segoe UI", 10), width=18, relief="solid", bd=1)
        self.name_entry.insert(0, "Bestie")
        self.name_entry.pack(side="left")

        # Photo Preview Center with cartoon frame
        preview_container = tk.LabelFrame(
            body_frame,
            text=" 🖼️ Photo Vault Preview ",
            font=("Segoe UI", 10, "bold"),
            bg="#FFFFFF",
            fg="#6C5CE7",
            relief="groove",
            bd=3,
            padx=10,
            pady=10
        )
        preview_container.pack(fill="x", pady=8)

        self.preview_label = tk.Label(
            preview_container,
            text="🙈 No photo selected yet!\n\nClick '📁 Select Photo' below or use the bundled sample.",
            font=("Segoe UI", 11),
            bg="#F8F9FA",
            fg="#7F8C8D",
            width=50,
            height=9,
            relief="sunken",
            bd=1
        )
        self.preview_label.pack(fill="both", expand=True)

        # Photo selection shortcuts row
        photo_btn_row = tk.Frame(preview_container, bg="#FFFFFF")
        photo_btn_row.pack(fill="x", pady=(8, 0))

        select_btn = tk.Button(
            photo_btn_row,
            text="📁 Select My Photo",
            font=("Segoe UI", 10, "bold"),
            bg="#74B9FF",
            fg="#2D3436",
            activebackground="#0984E3",
            activeforeground="#FFFFFF",
            relief="raised",
            bd=2,
            padx=10,
            pady=4,
            command=self._pick_photo_dialog
        )
        select_btn.pack(side="left", expand=True, padx=4)

        sample_btn = tk.Button(
            photo_btn_row,
            text="🎲 Use Sample Prank Photo",
            font=("Segoe UI", 10),
            bg="#FFEAA7",
            fg="#2D3436",
            activebackground="#FDCB6E",
            relief="raised",
            bd=2,
            padx=10,
            pady=4,
            command=self._use_sample_photo
        )
        sample_btn.pack(side="right", expand=True, padx=4)

        # Rounded Emoji Action Buttons Grid
        btn_grid = tk.Frame(body_frame, bg="#FDF6F0")
        btn_grid.pack(fill="x", pady=6)

        # Row 1: Hide Photo Trap & Close Friends
        self.trap_btn = tk.Button(
            btn_grid,
            text="🔒 Hide My Photo (Trap!) 🚀",
            font=("Segoe UI", 11, "bold"),
            bg="#FF7675",
            fg="#FFFFFF",
            activebackground="#D63031",
            activeforeground="#FFFFFF",
            relief="raised",
            bd=3,
            pady=8,
            command=self.HidePhotoTrap
        )
        self.trap_btn.pack(fill="x", pady=3)

        friends_btn = tk.Button(
            btn_grid,
            text="👥 Close Friends Section (Mystery) 🤫",
            font=("Segoe UI", 10, "bold"),
            bg="#A29BFE",
            fg="#2D3436",
            activebackground="#6C5CE7",
            activeforeground="#FFFFFF",
            relief="raised",
            bd=2,
            pady=6,
            command=self.CloseFriendsSection
        )
        friends_btn.pack(fill="x", pady=3)

        # Row 2: Puzzle Trap
        puzzle_btn = tk.Button(
            btn_grid,
            text="🧠 Solve Puzzle to Unlock Early 🧩",
            font=("Segoe UI", 10, "bold"),
            bg="#55EFC4",
            fg="#2D3436",
            activebackground="#00B894",
            activeforeground="#FFFFFF",
            relief="raised",
            bd=2,
            pady=6,
            command=self.PuzzleTrap
        )
        puzzle_btn.pack(fill="x", pady=3)

        # Row 3: Reset Wallpaper Button (Controlled by ResetTimer)
        self.reset_btn = tk.Button(
            btn_grid,
            text="🔄 Change / Reset Wallpaper 🧹",
            font=("Segoe UI", 10, "bold"),
            bg="#DFE6E9",
            fg="#2D3436",
            activebackground="#B2BEC3",
            relief="raised",
            bd=2,
            pady=6,
            command=self._on_reset_clicked
        )
        self.reset_btn.pack(fill="x", pady=3)

        # Bottom Utilities: Cute Voice Replay & Demo Fast-Forward
        util_row = tk.Frame(body_frame, bg="#FDF6F0")
        util_row.pack(fill="x", pady=4)

        voice_btn = tk.Button(
            util_row,
            text="🔊 Replay Voice: 'Nope!' 🎤",
            font=("Segoe UI", 9, "bold"),
            bg="#FD79A8",
            fg="#FFFFFF",
            relief="groove",
            bd=2,
            padx=8,
            pady=3,
            command=lambda: self.CuteVoiceOver("nope")
        )
        voice_btn.pack(side="left", padx=2)

        # Demo skip button for fast testing during presentations/judging
        demo_skip_btn = tk.Button(
            util_row,
            text="⚡ Demo Skip (0s)",
            font=("Segoe UI", 9),
            bg="#FFEAA7",
            fg="#636E72",
            relief="groove",
            bd=1,
            padx=6,
            pady=3,
            command=self._demo_skip_timer
        )
        demo_skip_btn.pack(side="right", padx=2)

        # Timer Display Banner
        self.timer_label = tk.Label(
            body_frame,
            text="⏳ Timer Status: Inactive (Trigger trap to start 5 min lock)",
            font=("Segoe UI", 9, "bold"),
            bg="#F1F2F6",
            fg="#57606F",
            relief="solid",
            bd=1,
            pady=4
        )
        self.timer_label.pack(fill="x", pady=6)

        # Status Footer
        self.status_label = tk.Label(
            self.root,
            text="🛡️ 100% Offline • No real emails sent • Made with ❤️ for TinkerHub",
            font=("Segoe UI", 8),
            bg="#FDF6F0",
            fg="#747D8C",
            pady=6
        )
        self.status_label.pack(side="bottom")

    # -------------------------------------------------------------
    # 2. HidePhotoTrap: Wallpaper change, fake notification, emails
    # -------------------------------------------------------------
    def HidePhotoTrap(self):
        """Sets photo as Windows wallpaper + fake 'Close Friends Alert'."""
        if self.is_locked:
            mins, secs = divmod(self.time_left, 60)
            time_str = f"{mins:02d}:{secs:02d}"
            res = messagebox.askyesno(
                "Trap Already Active! 🔒",
                f"⚠️ CANNOT CHANGE WALLPAPER IMMEDIATELY!\n\n"
                f"Changes can ONLY be done after 5 minutes ({time_str} remaining)!\n\n"
                "Do you want to try the Emergency Puzzle to unlock early? 🧠"
            )
            if res:
                self.PuzzleTrap(from_change_request=True)
            return

        if not self.selected_photo_path or not os.path.exists(self.selected_photo_path):
            # If no photo selected, offer to use sample
            if not self._use_sample_photo():
                messagebox.showwarning("HidePix 🔒", "Please select or sample a photo first!")
                return

        # Prepare a safe copy in app directory
        try:
            ext = Path(self.selected_photo_path).suffix or ".jpeg"
            trap_wallpaper_path = APP_DIR / f"hidepix_wallpaper{ext}"
            if Path(self.selected_photo_path).resolve() != trap_wallpaper_path.resolve():
                shutil.copy(self.selected_photo_path, trap_wallpaper_path)
            target = str(trap_wallpaper_path)
        except Exception:
            target = str(self.selected_photo_path)

        # Set desktop wallpaper
        ok, msg = set_wallpaper_generic(target)

        # Play cute voice over
        self.CuteVoiceOver("nope")

        # Start 5-minute timer lock
        self.ResetTimer()

        # Update status
        user_name = self.name_entry.get().strip() or "Bestie"
        self.status_label.config(text="👀 Photo safely hidden on your desktop wallpaper! 💀")

        # Fake notification toast
        self._show_fake_notification(user_name)

        # Prank message popup
        if ok:
            messagebox.showinfo(
                "HidePix Security Alert 🔒",
                f"Congratulations {user_name}!\n\n"
                "Your photo has been safely encrypted and hidden...\n"
                "RIGHT ON YOUR DESKTOP WALLPAPER! 👀💀\n\n"
                "The Reset button is now LOCKED for 5 minutes! ⏳"
            )
        else:
            messagebox.showinfo(
                "HidePix Demo 🔒",
                f"Demo Simulation:\n{msg}\n\n"
                "Imagine your photo displayed in 4K on your desktop! 💀\n"
                "Reset button is locked for 5 minutes! ⏳"
            )

        # Mystery Close Friends prompt if list is empty
        if not self.friends_list:
            self.root.after(800, self.CloseFriendsSection)

    def _show_fake_notification(self, name):
        """Displays a phone-style dark toast popup in the corner."""
        toast = tk.Toplevel(self.root)
        toast.title("📱 Close Friends Alert")
        toast.geometry("420x150+50+50")
        toast.resizable(False, False)
        toast.configure(bg="#1E1E24")
        toast.attributes("-topmost", True)

        header = tk.Label(
            toast,
            text="🔔 INSTA-GOSSIP • CLOSE FRIENDS NOTIFICATION",
            font=("Segoe UI", 9, "bold"),
            bg="#1E1E24",
            fg="#FF7675"
        )
        header.pack(pady=(12, 4), padx=15, anchor="w")

        body = tk.Label(
            toast,
            text=f"📢 {name} just hid a top secret photo…\nby broadcasting it across their entire desktop wallpaper! 💀",
            font=("Segoe UI", 10),
            bg="#1E1E24",
            fg="#FFFFFF",
            wraplength=380,
            justify="left"
        )
        body.pack(pady=4, padx=15, anchor="w")

        footer = tk.Label(
            toast,
            text="(No real friends were actually notified. This is a local joke 😌)",
            font=("Segoe UI", 8, "italic"),
            bg="#1E1E24",
            fg="#A4B0BE"
        )
        footer.pack(pady=(6, 10), padx=15, anchor="w")

        # Auto dismiss toast after 5 seconds
        toast.after(5000, toast.destroy)

    # -------------------------------------------------------------
    # 3. CloseFriendsSection: Add/Remove email addresses + Mystery
    # -------------------------------------------------------------
    def CloseFriendsSection(self):
        """Opens Close Friends dialog with email management and the mystery explanation."""
        friends_win = tk.Toplevel(self.root)
        friends_win.title("👥 Close Friends Network (Top Secret)")
        friends_win.geometry("520x600")
        friends_win.minsize(480, 520)
        friends_win.configure(bg="#F8F9FA")
        friends_win.attributes("-topmost", True)

        # Header
        f_header = tk.Frame(friends_win, bg="#6C5CE7", pady=10, padx=15)
        f_header.pack(fill="x")
        tk.Label(f_header, text="🤫 Close Friends Alert Network", font=("Segoe UI", 14, "bold"),
                 bg="#6C5CE7", fg="white").pack()
        tk.Label(f_header, text="Add emails below to broadcast your wallpaper adventures",
                 font=("Segoe UI", 9), bg="#6C5CE7", fg="#DFE6E9").pack()

        content = tk.Frame(friends_win, bg="#F8F9FA", padx=15, pady=10)
        content.pack(fill="both", expand=True)

        # Input Row
        add_frame = tk.Frame(content, bg="#F8F9FA")
        add_frame.pack(fill="x", pady=6)
        email_entry = tk.Entry(add_frame, font=("Segoe UI", 10), width=28, relief="solid", bd=1)
        email_entry.insert(0, "friend@example.com")
        email_entry.pack(side="left", padx=(0, 6), expand=True, fill="x")

        # Listbox for friends
        list_frame = tk.LabelFrame(content, text=" Stored Close Friends List (Local Only) ",
                                   font=("Segoe UI", 9, "bold"), bg="white", fg="#2D3436")
        list_frame.pack(fill="both", expand=True, pady=6)

        friends_box = tk.Listbox(list_frame, font=("Segoe UI", 10), height=8, relief="flat")
        friends_box.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        scrollbar = tk.Scrollbar(list_frame, command=friends_box.yview)
        scrollbar.pack(side="right", fill="y")
        friends_box.config(yscrollcommand=scrollbar.set)

        def refresh_box():
            friends_box.delete(0, tk.END)
            for f in self.friends_list:
                friends_box.insert(tk.END, f"📱 {f}")

        refresh_box()

        def add_email():
            email = email_entry.get().strip()
            if email and email not in self.friends_list:
                self.friends_list.append(email)
                self.save_friends_list()
                refresh_box()
                email_entry.delete(0, tk.END)

        def remove_email():
            sel = friends_box.curselection()
            if sel:
                idx = sel[0]
                self.friends_list.pop(idx)
                self.save_friends_list()
                refresh_box()

        add_btn = tk.Button(add_frame, text="➕ Add Friend", font=("Segoe UI", 9, "bold"),
                            bg="#55EFC4", fg="#2D3436", relief="groove", command=add_email)
        add_btn.pack(side="right")

        rm_btn = tk.Button(content, text="➖ Remove Selected Friend", font=("Segoe UI", 9),
                           bg="#FF7675", fg="white", relief="groove", command=remove_email)
        rm_btn.pack(fill="x", pady=3)

        # The Mystery Section (Why are emails asked?)
        mystery_card = tk.LabelFrame(
            content,
            text=" 🔮 THE GRAND MYSTERY 🔮 ",
            font=("Segoe UI", 10, "bold"),
            bg="#FFF3CD",
            fg="#856404",
            relief="solid",
            bd=1,
            padx=10,
            pady=10
        )
        mystery_card.pack(fill="x", pady=10)

        mystery_text = (
            "❓ Why did HidePix ask for your friends' emails?\n\n"
            "• Are we sending them an email? ABSOLUTELY NOT.\n"
            "• Are they stored in the cloud? NOPE, 100% OFFLINE.\n"
            "• Status: Synced with Satellite Pigeon Network 🕊️\n\n"
            "👉 The Mystery Solved:\n"
            "We asked for their emails purely so you would panic and wonder: "
            "'Wait, is this app really going to email them?!'\n"
            "Your secret remains safe... between you and your wallpaper! 😂"
        )
        tk.Label(mystery_card, text=mystery_text, font=("Segoe UI", 9),
                 bg="#FFF3CD", fg="#856404", justify="left", wraplength=420).pack()

        close_btn = tk.Button(content, text="Close Window 🚪", font=("Segoe UI", 9, "bold"),
                              bg="#DFE6E9", command=friends_win.destroy)
        close_btn.pack(pady=4)

    # -------------------------------------------------------------
    # 4. ResetTimer: 5-minute lock, countdown, snake cartoon unlock
    # -------------------------------------------------------------
    def ResetTimer(self):
        """Locks reset for 5 minutes and runs background countdown."""
        self.is_locked = True
        self.time_left = self.lock_duration = 300  # 5 minutes
        self.reset_btn.config(
            text="🔒 Change Wallpaper (LOCKED: 05:00) ⏳",
            bg="#FF7675",
            fg="white"
        )
        if not self.timer_running:
            self.timer_running = True
            self._tick_timer()

    def _tick_timer(self):
        """Updates timer every second."""
        if not self.timer_running:
            return

        if self.time_left > 0 and self.is_locked:
            mins, secs = divmod(self.time_left, 60)
            time_str = f"{mins:02d}:{secs:02d}"
            self.timer_label.config(
                text=f"⏳ WALLPAPER TRAP ACTIVE: {time_str} remaining until unlock!",
                bg="#FFEAA7",
                fg="#D63031"
            )
            self.reset_btn.config(text=f"🔒 Change Wallpaper (LOCKED: {time_str}) ⏳")
            self.time_left -= 1
            self.root.after(1000, self._tick_timer)
        elif self.time_left <= 0 and self.is_locked:
            # 5 minutes elapsed: Unlock reset with snake cartoon!
            self.is_locked = False
            self.timer_running = False
            self.timer_label.config(
                text="🎉 5 MINUTES EXPIRED! Snake has unlocked wallpaper changes! 🐍",
                bg="#55EFC4",
                fg="#006266"
            )
            self.reset_btn.config(
                text="🎉 5 Min Complete! Change / Reset Wallpaper Now 🐍",
                bg="#00B894",
                fg="white"
            )
            self._show_snake_unlock_popup()

    def _demo_skip_timer(self):
        """Fast-forward cheat for presenters to showcase timer expiration instantly."""
        if self.is_locked:
            self.time_left = 1
            self.status_label.config(text="⚡ Demo fast-forward triggered: expiring timer...")
        else:
            messagebox.showinfo("Demo Tip ⚡", "Activate 'Hide My Photo' first to start the 5-minute lock!")

    def _show_snake_unlock_popup(self):
        """Cartoon Snake popup when the 5-minute lock is conquered."""
        snake_win = tk.Toplevel(self.root)
        snake_win.title("🐍 Snake Forgiveness Granted!")
        snake_win.geometry("460x360")
        snake_win.configure(bg="#2D3436")
        snake_win.attributes("-topmost", True)

        snake_art = (
            r"      /^\/^\ " + "\n"
            r"    _|__|  O|   'Sssssssurvived! 🐍'" + "\n"
            r"\/     (~ \_)   " + "\n"
            r" \____|____/    "
        )
        art_label = tk.Label(
            snake_win,
            text=snake_art,
            font=("Courier New", 12, "bold"),
            bg="#2D3436",
            fg="#55EFC4"
        )
        art_label.pack(pady=(20, 10))

        msg = (
            "Snake says: Ssssurvived! 🐍\n\n"
            "Since you patiently endured the full 5 minutes of shame,\n"
            "you have earned forgiveness!\n\n"
            "The Reset button is now UNLOCKED.\n"
            "Click it to return your desktop back to normal."
        )
        tk.Label(snake_win, text=msg, font=("Segoe UI", 10), bg="#2D3436",
                 fg="#FFFFFF", justify="center").pack(padx=20, pady=10)

        ok_btn = tk.Button(snake_win, text="Restore My Dignity 🙏", font=("Segoe UI", 10, "bold"),
                           bg="#55EFC4", fg="#2D3436", command=snake_win.destroy)
        ok_btn.pack(pady=10)

    def _on_reset_clicked(self):
        """
        Handles click on the reset / change wallpaper button.
        If locked: wallpaper does NOT change immediately; changes can only be done
        after 5 minutes. Gives the user a puzzle challenge, but winning is also a prank!
        """
        if self.is_locked:
            # Cannot change immediately: launch the emergency puzzle trap!
            self.PuzzleTrap(from_change_request=True)
        else:
            # After 5 min: restore original wallpaper
            self._restore_original_wallpaper()

    def _restore_original_wallpaper(self):
        """Restores original desktop wallpaper using Windows registry backup."""
        if platform.system() == "Windows" and self.original_wallpaper and os.path.exists(self.original_wallpaper):
            try:
                set_wallpaper_windows(self.original_wallpaper)
                messagebox.showinfo("HidePix 🙈", "Phew! Original desktop wallpaper restored! Secret safe (almost) 😌")
                self.reset_btn.config(text="🔄 Change / Reset Wallpaper (Ready) 🧹", bg="#DFE6E9", fg="#2D3436")
                self.timer_label.config(text="⏳ Timer Status: Inactive", bg="#F1F2F6", fg="#57606F")
                return
            except Exception as e:
                messagebox.showwarning("HidePix", f"Could not auto-restore: {e}\nRight-click Desktop > Personalize.")
        else:
            messagebox.showinfo(
                "HidePix 🛠️",
                "Original wallpaper backup not found.\n"
                "Right-click on your Desktop > Personalize to choose any background image!"
            )
            self.reset_btn.config(text="🔄 Change / Reset Wallpaper (Ready) 🧹", bg="#DFE6E9", fg="#2D3436")

    # -------------------------------------------------------------
    # 5. PuzzleTrap: Interactive riddles during lock + Double Prank
    # -------------------------------------------------------------
    def PuzzleTrap(self, from_change_request=False):
        """
        Interactive mini-puzzle.
        If user is trying to change wallpaper during 5-minute lock:
        Wallpaper does NOT change immediately! They are given this puzzle to try to
        unlock early, but winning the puzzle is ALSO a prank (wallpaper is not changed)!
        """
        mins, secs = divmod(self.time_left, 60)
        time_str = f"{mins:02d}:{secs:02d}"

        p_win = tk.Toplevel(self.root)
        p_win.title("🧩 Emergency Wallpaper Bypass Puzzle 🧠")
        p_win.geometry("520x600")
        p_win.minsize(480, 560)
        p_win.configure(bg="#FDF6F0")
        p_win.attributes("-topmost", True)

        # Header Warning Banner
        warning_frame = tk.Frame(p_win, bg="#D63031", padx=10, pady=8)
        warning_frame.pack(fill="x")

        tk.Label(
            warning_frame,
            text="⚠️ CANNOT CHANGE WALLPAPER IMMEDIATELY! ⚠️",
            font=("Segoe UI", 11, "bold"),
            bg="#D63031",
            fg="white"
        ).pack()

        tk.Label(
            warning_frame,
            text=f"Changes can ONLY be done after 5 minutes! (Remaining: {time_str})\n"
                 f"Want to bypass the wait? Solve this puzzle to unlock immediately! 👀",
            font=("Segoe UI", 9),
            bg="#D63031",
            fg="#FFEAA7",
            justify="center"
        ).pack(pady=(2, 0))

        content_frame = tk.Frame(p_win, bg="#FDF6F0", padx=15, pady=10)
        content_frame.pack(fill="both", expand=True)

        # Puzzle 1
        q1_frame = tk.LabelFrame(content_frame, text=" Question 1: The Cryptic Riddle ",
                                 font=("Segoe UI", 9, "bold"), bg="white", fg="#2D3436", padx=10, pady=8)
        q1_frame.pack(fill="x", pady=6)
        tk.Label(q1_frame, text="What has keys but no locks, space but no room,\nand you can enter but can never go inside?",
                 font=("Segoe UI", 9), bg="white", justify="left").pack(anchor="w")

        v1 = tk.StringVar(value="")
        for opt in ["A Piano", "A Computer Keyboard", "A Haunted House", "A Mystery Box"]:
            tk.Radiobutton(q1_frame, text=opt, variable=v1, value=opt, bg="white", font=("Segoe UI", 9)).pack(anchor="w")

        # Puzzle 2
        q2_frame = tk.LabelFrame(content_frame, text=" Question 2: Snake Math ",
                                 font=("Segoe UI", 9, "bold"), bg="white", fg="#2D3436", padx=10, pady=8)
        q2_frame.pack(fill="x", pady=6)
        tk.Label(q2_frame, text="Snake asks: What is: 2 + 2 × 0 + 1 ?",
                 font=("Segoe UI", 9), bg="white", justify="left").pack(anchor="w")

        v2 = tk.StringVar(value="")
        for opt in ["1", "3", "0", "42"]:
            tk.Radiobutton(q2_frame, text=opt, variable=v2, value=opt, bg="white", font=("Segoe UI", 9)).pack(anchor="w")

        def submit_puzzle():
            ans1 = v1.get()
            ans2 = v2.get()

            if ans1 == "A Computer Keyboard" and ans2 == "3":
                # USER WON THE PUZZLE!
                # But this is ALSO A PRANK!
                p_win.destroy()

                # Play cute audio voice prank
                self.CuteVoiceOver("wow")
                self.root.after(1200, lambda: self.CuteVoiceOver("nope"))

                # Pop up the Double Prank reveal!
                self._show_puzzle_won_prank_popup()
            else:
                messagebox.showwarning(
                    "Snake Says 🐍",
                    "Hissssss! Incorrect answer! 🐍\n"
                    "Remember order of operations (multiplication first)!\n"
                    "Try again if you want to bypass the 5 minutes!"
                )

        btn_row = tk.Frame(content_frame, bg="#FDF6F0")
        btn_row.pack(fill="x", pady=10)

        submit_btn = tk.Button(
            btn_row,
            text="🚀 Submit & Change Wallpaper Now! 🔓",
            font=("Segoe UI", 11, "bold"),
            bg="#55EFC4",
            fg="#2D3436",
            activebackground="#00B894",
            relief="raised",
            bd=3,
            pady=8,
            command=submit_puzzle
        )
        submit_btn.pack(fill="x", pady=4)

        meme_btn = tk.Button(
            btn_row,
            text="Can't solve it? Show me a Meme 🎭",
            font=("Segoe UI", 9),
            bg="#FFEAA7",
            command=lambda: [p_win.destroy(), self.MemeScreens()]
        )
        meme_btn.pack(fill="x", pady=2)

    def _show_puzzle_won_prank_popup(self):
        """
        THE DOUBLE PRANK:
        The user won the puzzle, but winning is a prank too!
        The wallpaper does NOT change!
        """
        mins, secs = divmod(self.time_left, 60)
        time_str = f"{mins:02d}:{secs:02d}"

        prank_win = tk.Toplevel(self.root)
        prank_win.title("🎉 YOU WON!... BUT WAIT! 😂")
        prank_win.geometry("520x420")
        prank_win.configure(bg="#2D3436")
        prank_win.attributes("-topmost", True)

        art = (
            r"      /^\/^\ " + "\n"
            r"    _|__|  O|   'Sssssike! Still a prank! 🐍'" + "\n"
            r"\/     (~ \_)   " + "\n"
            r" \____|____/    "
        )
        tk.Label(
            prank_win,
            text=art,
            font=("Courier New", 12, "bold"),
            bg="#2D3436",
            fg="#FF7675"
        ).pack(pady=(16, 6))

        tk.Label(
            prank_win,
            text="🎉 CONGRATULATIONS! YOU WON THE PUZZLE! 🧠\n...BUT THAT WAS A PRANK ALSO! 😂",
            font=("Segoe UI", 13, "bold"),
            bg="#2D3436",
            fg="#FFEAA7",
            justify="center"
        ).pack(pady=4)

        msg = (
            "Voice: 'Wow nice try!' ... 'Nope! I'm not deleting that!' 🎤\n\n"
            "🐍 Snake says:\n"
            "'Did you really think winning a math puzzle would let you change your wallpaper early?!'\n\n"
            "🛑 CHANGES CAN ONLY BE DONE AFTER THE FULL 5 MINUTES! 🛑\n\n"
            f"Your wallpaper is NOT being changed early!\n"
            f"Time remaining: {time_str}.\n"
            "Sit back and admire your new desktop aesthetic! 🖼️💀"
        )
        tk.Label(
            prank_win,
            text=msg,
            font=("Segoe UI", 10),
            bg="#2D3436",
            fg="#FFFFFF",
            justify="center"
        ).pack(padx=20, pady=8)

        dismiss_btn = tk.Button(
            prank_win,
            text="I Got Trolled Twice... I'll Wait 😭",
            font=("Segoe UI", 10, "bold"),
            bg="#FF7675",
            fg="white",
            relief="raised",
            bd=3,
            command=prank_win.destroy
        )
        dismiss_btn.pack(pady=10)


    # -------------------------------------------------------------
    # 6. MemeScreens: Random memes when reset attempted early
    # -------------------------------------------------------------
    def MemeScreens(self):
        """Displays random meme refusal popups when reset is clicked early."""
        # Play "Nope!" audio
        self.CuteVoiceOver("nope")

        mins, secs = divmod(self.time_left, 60)
        time_rem = f"{mins}m {secs}s"

        memes = [
            {
                "title": "🐍 Snake says: Sssstop rushing! 🐍",
                "art": r"  /^\/^\ " + "\n" + r"_|__|  O|   'Ssssstop rushing!'" + "\n" + r"\/   (~ \_) " + "\n" + r" \___|___/  ",
                "text": f"Snake says: 'A quality prank must marinate on your desktop for 5 full minutes!'\n\nRemaining lock: {time_rem}.\nTake a sip of water and embrace your new aesthetic."
            },
            {
                "title": "🕵️ Nice Try, Sherlock!",
                "art": "  ( ͡° ͜ʖ ͡°)\n   / | \\ \n    / \\   'Not so fast!'",
                "text": f"Nice try, Sherlock!\nYour wallpaper has signed a 5-minute lease and refuses to vacate.\n\nTime remaining: {time_rem}."
            },
            {
                "title": "🫖 ERROR 418: I'm a Teapot",
                "art": "      ( (\n       ) )\n    .------.\n    |      |]\n    \\      /\n     `----'",
                "text": f"The reset button has temporarily transformed into a teapot.\nIt refuses to brew wallpaper changes until: {time_rem}."
            },
            {
                "title": "🐢 The Patient Turtle Speaks",
                "art": "     ___\n  .-'   `-.\n /  o   o  \\ \n|     ^     |  'Chill, bro.'\n \\  `---'  /\n  `-------'",
                "text": f"Patience is a virtue that you clearly do not possess.\n\nWallpaper will remain locked for {time_rem}.\nRelax, your friends will love it!"
            },
            {
                "title": "🥺 Wallpaper Separation Anxiety",
                "art": "   ( ; _ ; )\n  Reset Rejected for Emotional Reasons",
                "text": f"Your desktop wallpaper has developed attachment issues.\nDeleting it now would hurt its feelings.\n\nPlease check back in {time_rem}!"
            }
        ]

        import random
        choice = random.choice(memes)

        meme_win = tk.Toplevel(self.root)
        meme_win.title(choice["title"])
        meme_win.geometry("450x340")
        meme_win.configure(bg="#2D3436")
        meme_win.attributes("-topmost", True)

        art_label = tk.Label(
            meme_win,
            text=choice["art"],
            font=("Courier New", 12, "bold"),
            bg="#2D3436",
            fg="#FDCB6E"
        )
        art_label.pack(pady=(16, 8))

        text_label = tk.Label(
            meme_win,
            text=choice["text"],
            font=("Segoe UI", 10),
            bg="#2D3436",
            fg="#FFFFFF",
            justify="center",
            wraplength=400
        )
        text_label.pack(padx=15, pady=8)

        dismiss_btn = tk.Button(
            meme_win,
            text="Fine, I'll Wait 😤",
            font=("Segoe UI", 9, "bold"),
            bg="#FF7675",
            fg="white",
            relief="raised",
            bd=2,
            command=meme_win.destroy
        )
        dismiss_btn.pack(pady=12)

    # -------------------------------------------------------------
    # 7. CuteVoiceOver: Audio playback + Replay button
    # -------------------------------------------------------------
    def CuteVoiceOver(self, voice_type="nope"):
        """Plays audio file nope_voice.wav or wow_voice.wav with speech fallback."""
        if voice_type == "nope":
            play_audio(NOPE_VOICE_FILE, "Nope! I'm not deleting that!")
        else:
            play_audio(WOW_VOICE_FILE, "Wow nice try! It was fun, but still a prank!")

    # -------------------------------------------------------------
    # Helper & Utility Functions
    # -------------------------------------------------------------
    def _pick_photo_dialog(self):
        """Allows user to choose any image file from computer."""
        if self.is_locked:
            mins, secs = divmod(self.time_left, 60)
            time_str = f"{mins:02d}:{secs:02d}"
            res = messagebox.askyesno(
                "Wallpaper Locked 🔒",
                f"⚠️ CANNOT CHANGE WALLPAPER IMMEDIATELY!\n\n"
                f"Changes can ONLY be done after 5 minutes ({time_str} remaining)!\n\n"
                "Do you want to take the Emergency Puzzle to try to bypass the wait? 🧠"
            )
            if res:
                self.PuzzleTrap(from_change_request=True)
            return

        filetypes = [("Image files", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"), ("All files", "*.*")]
        chosen = filedialog.askopenfilename(title="Select your secret photo 🤫", filetypes=filetypes)
        if chosen:
            self.selected_photo_path = chosen
            self._update_preview(chosen)
            self.status_label.config(text=f"Selected: {Path(chosen).name} — primed for wallpaper prank! 😈")

    def _use_sample_photo(self):
        """Uses bundled sample photo if available, or creates a fun cartoon prank graphic."""
        sample_path = APP_DIR / "hidepix_wallpaper.jpeg"
        if not sample_path.exists():
            # Try to look for any image in current folder
            for p in APP_DIR.glob("*.jpg"):
                sample_path = p
                break

        if sample_path.exists():
            self.selected_photo_path = str(sample_path)
            self._update_preview(self.selected_photo_path)
            self.status_label.config(text="Loaded bundled sample prank photo! 🖼️")
            return True
        return False

    def _update_preview(self, img_path):
        """Renders thumbnail inside preview box using Pillow."""
        if HAS_PILLOW:
            try:
                img = Image.open(img_path)
                img.thumbnail((380, 180))
                photo = ImageTk.PhotoImage(img)
                self.preview_label.config(image=photo, text="")
                self.preview_label.image = photo
            except Exception as e:
                self.preview_label.config(text=f"📷 Image Selected: {Path(img_path).name}\n(Preview error: {e})")
        else:
            self.preview_label.config(
                text=f"📷 Photo Ready:\n{Path(img_path).name}\n\n(Install Pillow for visual thumbnail)"
            )

    def load_friends_list(self):
        """Loads locally stored close friends emails."""
        if FRIENDS_FILE.exists():
            try:
                with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return ["bestie@secret.local", "roommate@dorm.edu", "judge@tinkerhub.org"]

    def save_friends_list(self):
        """Persists close friends emails locally."""
        try:
            with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.friends_list, f, indent=2)
        except Exception:
            pass


# ================= APP ENTRY POINT =================

def main():
    root = tk.Tk()
    app = HidePixApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
