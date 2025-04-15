#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from gi.repository import Pango
import subprocess
import os
import socket
import time
import hashlib
import threading
import random
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import sys
import math
import wave
import array
import progressbar
import argparse
import cairo
import logging

# Setup basic logging (will be configured properly after parsing arguments)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')

# Precompute sine wave table
SINE_TABLE_SIZE = 1024
sine_table = np.sin(np.linspace(0, 2 * np.pi, SINE_TABLE_SIZE, endpoint=False))

def genSine(freq=2000, volume=100, duration=3, phase=0, sampleRate=88200):
    numSamples = int(sampleRate * duration)
    t = np.arange(numSamples) + phase
    sine_wave = np.interp((freq * t) % sampleRate, np.arange(SINE_TABLE_SIZE) * (sampleRate / SINE_TABLE_SIZE), sine_table)
    edge_size = int(numSamples * 0.15)
    window = np.ones(numSamples)
    edge = np.hanning(edge_size * 2)
    window[:edge_size] = edge[:edge_size]
    window[-edge_size:] = edge[edge_size:]
    sine_wave = sine_wave * window
    sine_wave = sine_wave * ((32767.0 / 100.0) * volume)
    return (sine_wave, t[-1])

def create_spectrogram(text=None, image_path=None, output_file="spectrogram.wav", font_size=50, hflip=0, invert=1, 
                      sampleRate=8000, duration=0.10, maxpixelwidth=256, min_freq=450, max_freq=2700, progress_callback=None, mode="USB", rotation=0):
    # Log rotation value for debugging
    logging.debug(f"Rotation value: {rotation} degrees")
    output_dir = os.path.dirname(os.path.abspath(output_file))
    temp_text_image = os.path.join(output_dir, 'text_image.png')
    
    font_files = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf'
    ]
    
    font = None
    for font_file in font_files:
        try:
            if os.path.exists(font_file):
                font = ImageFont.truetype(font_file, font_size)
                break
        except Exception:
            continue
    
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception as e:
            print(f"Error: Could not load any fonts - {e}")
            return False
    
    if text:
        try:
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[0]
            image = Image.new('L', (text_width, text_height), color=255)
            draw = ImageDraw.Draw(image)
            text_x = (text_width - bbox[2]) // 1
            text_y = (text_height - bbox[3]) // 2
            draw.text((text_x, text_y), text, font=font, fill=0)
            if hflip == 1:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            
            image = image.rotate(180)
            logging.debug("Applied standard 180 degree rotation to text image")
            
            os.makedirs(output_dir, exist_ok=True)
            image.save(temp_text_image)
            image_path = temp_text_image
        except Exception as e:
            print(f"Error generating text image: {e}")
            return False
    
    if not image_path:
        print("Error: No image path provided.")
        return False
    
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        return False
        
    try:
        im = Image.open(image_path).convert('L')
        
        # For non-text images, apply standard rotation if no custom rotation was applied
        if text is None and rotation == 0:
            # Only apply the standard 180 degree rotation if no custom rotation was applied
            # (custom rotation was already applied in the UI processing step)
            im = im.rotate(180)
            logging.debug("Applied standard 180 degree rotation to loaded image")
        else:
            # For text images, no rotation is applied as per user request
            logging.debug("Using image with rotation already applied")
        
        width, height = im.size

        if width > maxpixelwidth:
            r = float(maxpixelwidth) / float(width)
            im = im.resize((int(width * r), int(height * r)))
            width, height = im.size

        lastphase = [random.randint(0, 360) for _ in range(width)]
        step = (max_freq - min_freq) / float(width - 1)
        
        # Determine transmission orientation based on mode
        mode_str = str(mode).strip().split('\n')[0].upper()  # Take only first line, before frequency
        logging.debug(f"Mode detected (raw): '{mode}'")
        logging.debug(f"Mode after processing: '{mode_str}'")
        
        if mode_str == "USB":
            logging.debug("Entering USB mode processing block")
            effective_flip = True  
            if hflip:
                logging.debug("USB mode with hflip")
                effective_flip = False
            else:
                logging.debug("USB mode without hflip")
        else:  # LSB mode
            logging.debug("Entering LSB mode processing block")
            effective_flip = False  
            if hflip:
                logging.debug("LSB mode with hflip")
                effective_flip = True
            else:
                logging.debug("LSB mode without hflip")
        
        logging.debug(f"Final orientation - mode: {mode_str}, hflip: {hflip}, effective_flip: {effective_flip}")
        
        os.makedirs(output_dir, exist_ok=True)

        with wave.open(output_file, 'w') as f:
            f.setparams((1, 2, sampleRate, int(sampleRate * duration), "NONE", "Uncompressed"))
            edge_size = int(width * 0.05)
            window = np.ones(width)
            edge = np.hamming(edge_size * 2)
            window[:edge_size] = edge[:edge_size]
            window[-edge_size:] = edge[edge_size:]

            for h in range(height):
                data = []
                max_amplitude = 0
                for w in range(width):
                    vol = (100.0 / 255.0) * im.getpixel((w, h))
                    if invert:
                        vol = 100.0 - vol
                    vol = vol * 1.2
                    if vol < 5.0:
                        vol = 0
                    elif vol < 10.0:
                        vol = vol * ((vol - 5.0) / 5.0) ** 1.5
                    vol = vol * window[w]
                    
                    # Calculate frequency based on mode and flip settings
                    if effective_flip:
                        freq = max_freq - (w * step)  
                        if w == 0:
                            logging.debug(f"First pixel freq (left): {freq:.2f} Hz")
                    else:
                        freq = min_freq + (w * step)  
                        if w == 0:
                            logging.debug(f"First pixel freq (right): {freq:.2f} Hz")
                            
                    (sw, p) = genSine(freq, volume=vol, phase=lastphase[w], duration=duration, sampleRate=sampleRate)
                    data.append(sw)
                    lastphase[w] = p
                    current_max = np.max(np.abs(sw))
                    if current_max > max_amplitude:
                        max_amplitude = current_max
                    if progress_callback:
                        progress = (width * h + w) / (width * height)
                        progress_callback(progress)

                data = np.array(data)
                if max_amplitude > 0:
                    scale_factor = 30000.0 / max_amplitude
                    data = data * scale_factor
                    data = np.clip(data, -30000, 30000)
                final_data = np.sum(data, axis=0) / (width * 1.0)
                final_data = np.clip(final_data, -32767, 32767)
                f.writeframes(array.array('h', [int(x) for x in final_data]).tobytes())
        
        if text and os.path.exists(temp_text_image):
            try:
                os.remove(temp_text_image)
            except:
                pass
        return True
    except Exception as e:
        print(f"Error generating spectrogram: {e}")
        return False

class SpectrogramApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="Spectrogram Generator")
        self.set_border_width(10)
        self.set_default_size(400, -1)
        self.set_size_request(400, -1)

        self.grid = Gtk.Grid()
        self.add(self.grid)

        menubar = Gtk.MenuBar()
        file_menu = Gtk.Menu()
        file_item = Gtk.MenuItem(label="File")
        file_item.set_submenu(file_menu)

        about_item = Gtk.MenuItem(label="About")
        about_item.connect("activate", self.show_about_dialog)
        file_menu.append(about_item)

        settings_item = Gtk.MenuItem(label="Settings")
        settings_item.connect("activate", self.show_settings_dialog)
        file_menu.append(settings_item)

        menubar.append(file_item)

        self.mode_label = Gtk.Label(label="Mode: ---")
        self.mode_label.set_halign(Gtk.Align.END)
        self.mode_label.set_valign(Gtk.Align.START)
        self.mode_label.set_margin_end(10)
        
        # Use CSS styling instead of deprecated override_font
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"label { font: 8pt Sans; }")
        context = self.mode_label.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.grid.attach(menubar, 0, 0, 1, 1)
        self.grid.attach(self.mode_label, 1, 0, 1, 1)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.grid.attach(self.box, 0, 1, 2, 1)

        self.image_file_button = Gtk.FileChooserButton(title="Select Image")
        filter_png = Gtk.FileFilter()
        filter_png.set_name("PNG Images")
        filter_png.add_mime_type("image/png")
        self.image_file_button.add_filter(filter_png)
        self.image_file_button.connect("file-set", self.on_image_file_button_clicked)

        self.text_entry = Gtk.Entry()
        self.text_entry.set_placeholder_text("Enter text here")

        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.play_button = Gtk.Button(label="Play")
        self.play_button.connect("clicked", self.on_play_button_clicked)
        self.clear_button = Gtk.Button(label="Clear")
        self.clear_button.connect("clicked", self.on_clear_button_clicked)

        self.status_label = Gtk.Label(label="Please enter text or select a PNG file to generate")
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        self.progress_bar.hide()

        self.waterfall_area = Gtk.DrawingArea()
        self.waterfall_area.set_size_request(400, 100)
        self.waterfall_area.connect("draw", self.draw_waterfall)
        self.waterfall_data = []
        self.waterfall_max_rows = 100

        self.box.pack_start(self.image_file_button, False, False, 0)
        self.box.pack_start(self.text_entry, False, False, 0)
        self.button_box.pack_start(self.play_button, True, True, 0)
        self.button_box.pack_start(self.clear_button, True, True, 0)
        self.box.pack_start(self.button_box, False, False, 0)
        self.box.pack_start(self.progress_bar, False, False, 0)
        self.box.pack_start(self.waterfall_area, False, False, 0)
        self.box.pack_start(self.status_label, False, False, 0)

        self.max_freq_label = Gtk.Label(label="TX Bandwidth (Hz):")
        self.max_freq_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 2000, 3000, 100)
        self.max_freq_scale.set_value(2700)
        self.max_freq_scale.set_digits(0)
        self.max_freq_scale.set_hexpand(True)
        self.max_freq_label.set_no_show_all(True)
        self.max_freq_scale.set_no_show_all(True)
        self.max_freq_label.hide()
        self.max_freq_scale.hide()
        self.box.pack_start(self.max_freq_label, False, False, 0)
        self.box.pack_start(self.max_freq_scale, False, False, 0)

        self.min_freq_label = Gtk.Label(label="Min Frequency (Hz):")
        self.min_freq_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 100, 2000, 100)
        self.min_freq_scale.set_value(450)
        self.min_freq_scale.set_digits(0)
        self.min_freq_scale.set_hexpand(True)
        self.min_freq_label.set_no_show_all(True)
        self.min_freq_scale.set_no_show_all(True)
        self.min_freq_label.hide()
        self.min_freq_scale.hide()
        self.box.pack_start(self.min_freq_label, False, False, 0)
        self.box.pack_start(self.min_freq_scale, False, False, 0)

        self.font_size_label = Gtk.Label(label="Font Size:")
        self.font_size_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 50, 100, 5)
        self.font_size_scale.set_value(50)
        self.font_size_scale.set_digits(0)
        self.font_size_scale.set_hexpand(True)
        self.font_size_label.set_no_show_all(True)
        self.font_size_scale.set_no_show_all(True)
        self.font_size_label.hide()
        self.font_size_scale.hide()
        self.box.pack_start(self.font_size_label, False, False, 0)
        self.box.pack_start(self.font_size_scale, False, False, 0)

        self.hflip_check = Gtk.CheckButton(label="Horizontal Flip")
        self.hflip_check.set_active(False)
        self.invert_check = Gtk.CheckButton(label="Invert Colors")
        self.invert_check.set_active(True)
        
        # Hide these controls by default (will show when image is loaded)
        self.hflip_check.hide()
        self.invert_check.hide()
        self.hflip_check.set_no_show_all(True)
        self.invert_check.set_no_show_all(True)
        
        self.box.pack_start(self.hflip_check, False, False, 0)
        self.box.pack_start(self.invert_check, False, False, 0)

        self.rotation_label = Gtk.Label(label="Image Rotation:")
        # Create a ComboBox instead of a Scale for discrete rotation values
        self.rotation_combo = Gtk.ComboBoxText()
        self.rotation_combo.append_text("0°")
        self.rotation_combo.append_text("90°")
        self.rotation_combo.append_text("180°")
        self.rotation_combo.append_text("270°")
        self.rotation_combo.set_active(0)  # Default to 0 degrees
        
        # Hide rotation controls by default (will show when image is loaded)
        self.rotation_label.hide()
        self.rotation_combo.hide()
        self.rotation_label.set_no_show_all(True)
        self.rotation_combo.set_no_show_all(True)
        
        self.box.pack_start(self.rotation_label, False, False, 0)
        self.box.pack_start(self.rotation_combo, False, False, 0)

        self.output_file = "spectrogram.wav"
        self.image_path = None
        self.previous_hash = None
        self.settings_dialog = None
        self.spectrogram_data = None
        self.audio_data = None
        self.playback_thread = None
        self.is_playing = False
        self.waterfall_top_down = True
        self.current_mode = None  
        self.playback_lock = threading.Lock()
        self.hamlib_lock = threading.Lock()

        self.connect_to_hamlib()

    def connect_to_hamlib(self):
        try:
            self.hamlib_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.hamlib_socket.settimeout(2.0)
            self.hamlib_socket.connect(('127.0.0.1', 4532))
            logging.debug("Hamlib connection established")
        except Exception as e:
            self.update_status(f"Failed to connect to Hamlib server: {e}")
            logging.error(f"Hamlib connection failed: {e}")

    def close_hamlib(self):
        if hasattr(self, 'hamlib_socket') and self.hamlib_socket:
            try:
                self.hamlib_socket.close()
                logging.debug("Hamlib socket closed")
            except Exception as e:
                self.update_status(f"Failed to close Hamlib socket: {e}")
                logging.error(f"Failed to close Hamlib socket: {e}")
            finally:
                self.hamlib_socket = None
            self.update_status("Hamlib connection closed")

    def send_hamlib_command(self, command):
        """Send a command to hamlib and get response."""
        try:
            with self.hamlib_lock:
                self.hamlib_socket.send(f"{command}\n".encode())
                response = self.hamlib_socket.recv(1024).decode().strip()
                parts = response.split('\n')
                if len(parts) >= 1:
                    logging.debug(f"Sent Hamlib command: {command}")
                    logging.debug(f"Received Hamlib response: {response}")
                    return parts[0].strip()
                return None
        except Exception as e:
            logging.error(f"Error sending hamlib command: {e}")
            return None

    def get_hamlib_mode(self):
        """Get the current mode from hamlib."""
        if self.current_mode is None:
            try:
                with self.hamlib_lock:
                    self.hamlib_socket.send(b"m\n")
                    response = self.hamlib_socket.recv(1024).decode().strip()
                    # Parse response more carefully - format is "MODE\nRESPONSE_CODE"
                    parts = response.split('\n')
                    if len(parts) >= 1:
                        mode = parts[0].strip()
                        if mode in ["USB", "LSB"]:
                            self.current_mode = mode
                            logging.debug(f"Cached new mode: {mode}")
                        else:
                            logging.error(f"Invalid mode received: {mode}")
                            return "USB"  # Default to USB if invalid
                    else:
                        logging.error("Empty response from hamlib")
                        return "USB"
            except Exception as e:
                logging.error(f"Error getting mode: {e}")
                return "USB"  # Default to USB if error
        return self.current_mode

    def update_mode(self):
        """Force update of cached mode."""
        self.current_mode = None
        return self.get_hamlib_mode()

    def calculate_hash(self, text, image_path):
        hash_object = hashlib.md5()
        if text:
            hash_object.update(text.encode('utf-8'))
        if image_path:
            hash_object.update(image_path.encode('utf-8'))
        hash_object.update(str(int(self.max_freq_scale.get_value())).encode('utf-8'))
        hash_object.update(str(int(self.min_freq_scale.get_value())).encode('utf-8'))
        hash_object.update(str(int(self.font_size_scale.get_value())).encode('utf-8'))
        hash_object.update(str(int(self.hflip_check.get_active())).encode('utf-8'))
        hash_object.update(str(int(self.invert_check.get_active())).encode('utf-8'))
        hash_object.update(str(int(self.rotation_combo.get_active() * 90)).encode('utf-8'))
        return hash_object.hexdigest()

    def on_play_button_clicked(self, widget):
        text = self.text_entry.get_text()
        if self.image_file_button.get_file():
            self.image_path = self.image_file_button.get_file().get_path()
        else:
            self.image_path = None

        if not text and not self.image_path:
            self.update_status("Error: Please enter text or select a PNG file.")
            return

        current_hash = self.calculate_hash(text, self.image_path)

        if current_hash == self.previous_hash and os.path.exists(self.output_file):
            self.update_status("No changes. Transmitting existing spectrogram...")
            self.check_mode_and_play()
        else:
            self.update_status("Changes detected. Generating new spectrogram...")
            self.previous_hash = current_hash
            self.progress_bar.show()
            self.progress_bar.set_fraction(0)
            self.progress_bar.set_text("")
            generation_thread = threading.Thread(target=self.create_spectrogram, args=(text,))
            generation_thread.start()

    def on_clear_button_clicked(self, widget):
        self.text_entry.set_text("")
        self.image_path = None
        self.image_file_button.unselect_all()
        self.spectrogram_data = None
        
        # Hide rotation control when no image is loaded
        self.rotation_label.hide()
        self.rotation_combo.hide()
        self.rotation_label.set_no_show_all(True)
        self.rotation_combo.set_no_show_all(True)
        logging.debug("Cleared image, hiding rotation controls")
        
        # Hide invert control
        self.invert_check.hide()
        self.invert_check.set_no_show_all(True)
        
        self.waterfall_data = []
        self.waterfall_area.queue_draw()
        self.update_status("Status: Cleared input fields")

    def create_spectrogram(self, text=None):
        """Create a spectrogram from text or image."""
        # Force update mode before encoding
        self.update_mode()  # Clear cache and get fresh mode
        mode = self.get_hamlib_mode()
        logging.debug(f"Creating spectrogram in mode: {mode}")
        
        try:
            GLib.idle_add(self.update_status, "Generating spectrogram...")
            max_freq = int(self.max_freq_scale.get_value())
            min_freq = int(self.min_freq_scale.get_value())
            font_size = int(self.font_size_scale.get_value())
            
            # For transmission:
            if mode == "USB":
                baseline_hflip = 0  # No flip by default
                if self.hflip_check.get_active():
                    baseline_hflip = 1  # Flip when requested
            else:  # LSB
                if text:
                    # Text mode: Default flip for LSB
                    baseline_hflip = 1  # Flip by default
                    if self.hflip_check.get_active():
                        baseline_hflip = 0  # No flip when requested
                else:
                    # PNG mode: Need flip for LSB
                    baseline_hflip = 1  # Always flip for LSB PNG
                    if self.hflip_check.get_active():
                        baseline_hflip = 0  # Unless hflip requested
                
            logging.debug(f"Transmission orientation - mode: {mode}, hflip: {self.hflip_check.get_active()}, baseline_hflip: {baseline_hflip}, is_text: {bool(text)}")
            
            # Process image if loading from PNG
            if self.image_path and not text:
                img = Image.open(self.image_path)
                img = img.convert('L')  # Convert to grayscale
                
                # Apply rotation if specified
                rotation_index = self.rotation_combo.get_active()
                rotation = rotation_index * 90  # Convert index to degrees (0, 90, 180, 270)
                
                if rotation > 0:
                    logging.debug(f"Pre-applying {rotation} degree rotation to PNG in UI")
                    # Use PIL's built-in rotation constants for more reliable rotation
                    if rotation == 90:
                        img = img.transpose(Image.ROTATE_90)
                    elif rotation == 180:
                        img = img.transpose(Image.ROTATE_180)
                    elif rotation == 270:
                        img = img.transpose(Image.ROTATE_270)
                
                # For LSB mode, flip the image before processing
                if mode == "LSB":
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    logging.debug("LSB mode: Pre-flipping PNG image")
                
                # Save the pre-processed image
                temp_path = self.image_path + ".temp.png"
                img.save(temp_path)
                self.image_path = temp_path
                logging.debug(f"Saved pre-processed image: {self.image_path}")
            
            invert = 1 if self.invert_check.get_active() else 0
            success = create_spectrogram(text=text, image_path=self.image_path, output_file=self.output_file, 
                                      max_freq=max_freq, min_freq=min_freq, font_size=font_size, 
                                      hflip=baseline_hflip, invert=invert, progress_callback=self.update_progress, 
                                      mode=mode, rotation=0)
            
            # Clean up temporary image if it exists
            if self.image_path and self.image_path.endswith('.temp.png'):
                try:
                    os.remove(self.image_path)
                    logging.debug(f"Cleaned up temporary image: {self.image_path}")
                except Exception as e:
                    logging.error(f"Error cleaning up temp image: {e}")
                
            if success and os.path.exists(self.output_file):
                GLib.idle_add(self.update_status, "Spectrogram generated. Ready to Transmit...")
                GLib.idle_add(self.check_mode_and_play)
            else:
                GLib.idle_add(self.update_status, "Failed to generate spectrogram.")
            GLib.idle_add(self.progress_bar.hide)
        except Exception as e:
            GLib.idle_add(self.update_status, f"Error generating spectrogram: {e}")
            logging.error(f"Error generating spectrogram: {e}")

    def check_mode_and_play(self):
        if self.playback_thread and self.playback_thread.is_alive():
            self.update_status("Waiting for previous transmission to finish...")
            self.playback_thread.join()
        
        self.current_mode = self.get_hamlib_mode()
        if self.current_mode:
            self.mode_label.set_text(f"Mode: {self.current_mode}")
        else:
            self.mode_label.set_text("Mode: ---")
        self.play_audio()

    def update_progress(self, fraction):
        GLib.idle_add(self.progress_bar.set_fraction, fraction)
        GLib.idle_add(self.progress_bar.set_text, f"{int(fraction * 100)}%")

    def play_audio(self):
        with self.playback_lock:
            if self.is_playing:
                return
            
            # Clear waterfall buffer before playing
            self.waterfall_data = []
            self.waterfall_area.queue_draw()
            
            self.is_playing = True
            try:
                self.send_hamlib_command("T 1\n")
                time.sleep(0.5)
                self.update_status("Transmitting spectrogram...")
                with wave.open(self.output_file, 'rb') as wf:
                    sample_rate = wf.getframerate()
                    audio_data = wf.readframes(wf.getnframes())
                    self.audio_data = np.frombuffer(audio_data, dtype=np.int16)
                    self.sample_rate = sample_rate
                
                self.playback_thread = threading.Thread(target=self.play_and_analyze)
                self.playback_thread.start()
            except Exception as e:
                self.update_status(f"Failed to start playback: {e}")
                self.is_playing = False

    def play_and_analyze(self):
        chunk_size = 1024
        process_rate = self.sample_rate
        num_samples = len(self.audio_data)
        position = 0

        proc = subprocess.Popen(['aplay', '-D', 'plughw:CARD=2,DEV=0', self.output_file])
        logging.debug("Started aplay process")

        while position < num_samples and self.is_playing:
            chunk = self.audio_data[position:position + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)), 'constant')
            
            fft_data = np.abs(np.fft.rfft(chunk))[:chunk_size // 2]
            fft_data = 20 * np.log10(fft_data + 1e-6)
            logging.debug(f"FFT data range: {np.min(fft_data)} to {np.max(fft_data)}")
            
            if self.waterfall_top_down:
                self.waterfall_data.insert(0, fft_data)
                if len(self.waterfall_data) > self.waterfall_max_rows:
                    self.waterfall_data.pop()
            else:
                self.waterfall_data.append(fft_data)
                if len(self.waterfall_data) > self.waterfall_max_rows:
                    self.waterfall_data.pop(0)
            
            GLib.idle_add(self.waterfall_area.queue_draw)
            
            position += chunk_size
            time.sleep(chunk_size / process_rate)

        proc.wait()
        logging.debug("aplay process completed")
        self.is_playing = False
        self.send_hamlib_command("T 0\n")
        GLib.idle_add(self.update_status, "Transmit finished.")

    def draw_waterfall(self, widget, cr):
        """Draw the waterfall display."""
        if not self.waterfall_data:
            return

        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        active_width = width * 0.8
        x_offset = (width - active_width) / 2

        # Waterfall display:
        # For text: match transmission mode default orientation
        # For PNG: show as loaded, but flip for LSB
        mode = self.get_hamlib_mode()
        if mode == "USB":
            # USB: flip only if requested
            flip = self.hflip_check.get_active()
        else:  # LSB
            if self.image_path:
                # LSB PNG: Default flip, unless hflip requested
                flip = not self.hflip_check.get_active()
            else:
                # LSB text: Default right-to-left, flip when requested
                flip = not self.hflip_check.get_active()
        
        logging.debug(f"Waterfall orientation - mode: {mode}, hflip: {self.hflip_check.get_active()}, flip: {flip}, is_png: {bool(self.image_path)}")

        for i, fft_row in enumerate(self.waterfall_data):
            if self.waterfall_top_down:
                y = i * height / self.waterfall_max_rows
            else:
                y = height - (i + 1) * height / self.waterfall_max_rows

            for j in range(len(fft_row)):
                if flip:
                    flipped_j = len(fft_row) - (j + 1)
                    x = x_offset + ((flipped_j - 0) / (len(fft_row) - 0)) * active_width
                else:
                    x = x_offset + ((j - 0) / (len(fft_row) - 0)) * active_width
                value = fft_row[j]
                intensity = min(value / max(fft_row), 1.0)
                cr.set_source_rgb(intensity, intensity, intensity)
                cr.rectangle(x, y, active_width / len(fft_row), height / self.waterfall_max_rows)
                cr.fill()

            cr.set_source_rgb(0, 0, 0)
            cr.rectangle(0, y, x_offset, height / self.waterfall_max_rows)
            cr.rectangle(x_offset + active_width, y, width - (x_offset + active_width), height / self.waterfall_max_rows)
            cr.fill()

    def update_status(self, message):
        self.status_label.set_text(message)
        while Gtk.events_pending():
            Gtk.main_iteration()

    def show_about_dialog(self, widget):
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_transient_for(self)
        about_dialog.set_modal(True)
        about_dialog.set_program_name("sBitx Spectrogram Generator")
        about_dialog.set_version("2.04")
        about_dialog.set_copyright(" 2025 W2JON \n sBitx 64Bit Dev Team")
        about_dialog.run()
        about_dialog.destroy()

    def show_settings_dialog(self, widget):
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
            self.settings_dialog.connect("response", self.on_settings_dialog_response)
            self.settings_dialog.connect("delete-event", self.on_settings_dialog_delete)
        self.settings_dialog.show()

    def on_settings_dialog_response(self, dialog, response):
        dialog.hide()

    def on_settings_dialog_delete(self, dialog, event):
        dialog.hide()
        return True

    def on_image_file_button_clicked(self, widget):
        self.image_path = self.image_file_button.get_file().get_path()
        self.spectrogram_data = self.load_spectrogram_data(self.image_path)
        
        # Show rotation and invert controls when an image is loaded
        if self.image_path and os.path.exists(self.image_path):
            # Show rotation controls
            self.rotation_label.set_no_show_all(False)
            self.rotation_combo.set_no_show_all(False)
            self.rotation_label.show()
            self.rotation_combo.show()
            
            # Show invert colors control
            self.invert_check.set_no_show_all(False)
            self.invert_check.show()
            
            logging.debug(f"Image loaded, showing rotation and invert controls: {self.image_path}")
        
        self.queue_draw()

    def load_spectrogram_data(self, image_path):
        if os.path.exists(image_path):
            image = Image.open(image_path)
            return np.array(image.convert('L'))
        return None

class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Settings", transient_for=parent, flags=0)
        self.set_default_size(300, 150)
        self.parent = parent

        self.show_tx_bandwidth = Gtk.CheckButton(label="Show TX Bandwidth Slider")
        self.show_tx_bandwidth.set_active(False)
        self.show_tx_bandwidth.connect("toggled", self.on_tx_bandwidth_toggle)
        self.show_font_size = Gtk.CheckButton(label="Show Font Size Slider")
        self.show_font_size.set_active(False)
        self.show_font_size.connect("toggled", self.on_font_size_toggle)
        self.show_hflip = Gtk.CheckButton(label="Show Horizontal Flip Control")
        self.show_hflip.set_active(False)
        self.show_hflip.connect("toggled", self.on_hflip_toggle)
        self.show_invert = Gtk.CheckButton(label="Show Invert Control")
        self.show_invert.set_active(False)
        self.show_invert.connect("toggled", self.on_invert_toggle)
        self.waterfall_top_down = Gtk.CheckButton(label="Waterfall Top-Down")
        self.waterfall_top_down.set_active(True)
        self.waterfall_top_down.connect("toggled", self.on_waterfall_top_down_toggle)

        box = self.get_content_area()
        box.set_spacing(6)
        box.pack_start(self.show_tx_bandwidth, False, False, 0)
        box.pack_start(self.show_font_size, False, False, 0)
        box.pack_start(self.show_hflip, False, False, 0)
        box.pack_start(self.show_invert, False, False, 0)
        box.pack_start(self.waterfall_top_down, False, False, 0)
        self.show_all()

    def on_tx_bandwidth_toggle(self, widget):
        if widget.get_active():
            self.parent.max_freq_label.show()
            self.parent.max_freq_scale.show()
            self.parent.min_freq_label.show()
            self.parent.min_freq_scale.show()
        else:
            self.parent.max_freq_label.hide()
            self.parent.max_freq_scale.hide()
            self.parent.min_freq_label.hide()
            self.parent.min_freq_scale.hide()
        self.parent.resize(1, 1)

    def on_font_size_toggle(self, widget):
        if widget.get_active():
            self.parent.font_size_label.show()
            self.parent.font_size_scale.show()
        else:
            self.parent.font_size_label.hide()
            self.parent.font_size_scale.hide()
        self.parent.resize(1, 1)

    def on_hflip_toggle(self, widget):
        if widget.get_active():
            self.parent.hflip_check.show()
        else:
            self.parent.hflip_check.hide()
        self.parent.resize(1, 1)

    def on_invert_toggle(self, widget):
        if widget.get_active():
            self.parent.invert_check.show()
        else:
            self.parent.invert_check.hide()
        self.parent.resize(1, 1)

    def on_waterfall_top_down_toggle(self, widget):
        self.parent.waterfall_top_down = widget.get_active()
        self.parent.waterfall_area.queue_draw()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate a spectrogram from text or image')
    parser.add_argument('--text', help='Text to convert to spectrogram')
    parser.add_argument('--image', help='Image file to convert to spectrogram')
    parser.add_argument('--output', default='spectrogram.wav', help='Output WAV file')
    parser.add_argument('--font-size', type=int, default=50, help='Font size for text')
    parser.add_argument('--hflip', type=int, default=0, help='Horizontally flip the image')
    parser.add_argument('--invert', type=int, default=1, help='Invert the colors')
    parser.add_argument('--rotation', type=int, default=0, help='Rotate the image')
    parser.add_argument('--transmit', action='store_true', help='Transmit the audio after generating')
    parser.add_argument('--mode', help='Force radio mode (USB or LSB). If not specified, will attempt to detect from radio.')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    
    # Configure logging based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    if args.text or args.image:
        # Initialize a minimal app just for mode detection if needed
        temp_app = None
        current_mode = args.mode
        
        if args.transmit and not current_mode:
            # Initialize GTK for hamlib communication
            if not Gtk.init_check()[0]:
                print("Error: GTK initialization failed")
                sys.exit(1)
                
            # Create temporary app to detect mode
            temp_app = SpectrogramApp()
            
            # Connect to hamlib and get current mode
            print("Detecting radio mode...")
            temp_app.connect_to_hamlib()
            current_mode = temp_app.get_hamlib_mode()
            
            if current_mode:
                print(f"Detected radio mode: {current_mode}")
            else:
                print("Could not detect radio mode, defaulting to USB")
                current_mode = "USB"
        
        # Default to USB if mode not specified or detected
        if not current_mode:
            current_mode = "USB"
            
        # Create the spectrogram with the correct mode
        success = create_spectrogram(text=args.text, image_path=args.image, output_file=args.output,
                                    font_size=args.font_size, hflip=args.hflip, invert=args.invert, 
                                    rotation=args.rotation, mode=current_mode)
        
        if success and args.transmit:
            if not temp_app:
                # Initialize GTK if not already done
                if not Gtk.init_check()[0]:
                    print("Error: GTK initialization failed")
                    sys.exit(1)
                temp_app = SpectrogramApp()
            
            # Set the output file path
            temp_app.output_file = args.output
            
            # Create a minimal window to show just the waterfall display
            waterfall_window = Gtk.Window(title="Spectrogram Transmission")
            waterfall_window.set_default_size(400, 100)  
            waterfall_window.set_border_width(10)
            waterfall_window.set_position(Gtk.WindowPosition.CENTER)  # Center on screen
            waterfall_window.set_decorated(False) # No decorations
            
            # Create a vertical box to hold the waterfall and status
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            waterfall_window.add(vbox)
            
            # Add the waterfall display area
            waterfall_area = Gtk.DrawingArea()
            waterfall_area.set_size_request(400, 75)  # Reduced height to 75
            waterfall_area.connect("draw", temp_app.draw_waterfall)
            vbox.pack_start(waterfall_area, True, True, 0)
            
            # Add a status label
            status_label = Gtk.Label(label=f"Transmitting in {current_mode} mode...")
            vbox.pack_start(status_label, False, False, 0)
            
            # Set up the waterfall display
            temp_app.waterfall_area = waterfall_area
            temp_app.waterfall_data = []
            
            # Show the window
            waterfall_window.show_all()
            
            # Play the audio (non-blocking)
            print(f"Transmitting audio from {args.output} in {current_mode} mode...")
            temp_app.play_audio()
            
            # Set up a timer to update the status and close when done
            def check_playback_status():
                if not temp_app.is_playing:
                    status_label.set_text("Transmission complete. Closing...")
                    # Schedule window close after a short delay
                    GLib.timeout_add(1000, Gtk.main_quit)
                    return False  # Stop the timer
                return True  # Continue the timer
            
            # Check status every 100ms
            GLib.timeout_add(100, check_playback_status)
            
            # Run the GTK main loop
            Gtk.main()
            
            # Clean up
            if temp_app and hasattr(temp_app, 'close_hamlib'):
                temp_app.close_hamlib()
            
            print("Transmission complete.")
        
        sys.exit(0 if success else 1)
    else:
        if not Gtk.init_check()[0]:
            print("Error: GTK initialization failed")
            sys.exit(1)
        win = SpectrogramApp()
        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        Gtk.main()