#!/usr/bin/env python3

"""
Copyright (c) 2024 Harry Zhu

This software is provided 'as-is', without any express or implied warranty.
In no event will the authors be held liable for any damages arising from
the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it freely,
subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
"""

import json
import os
import subprocess
import time
import requests
import logging
import concurrent.futures
from typing import List, Dict
import os
import platform

# Suppress macOS warnings
if platform.system() == 'Darwin':  # macOS
    os.environ['TK_SILENCE_DEPRECATION'] = '1'

import tkinter as tk
import signal
import atexit
from tkinter import ttk, scrolledtext, messagebox, filedialog
import queue
import threading
from typing import Optional

"""
TikTok Video Downloader with GUI Interface by HarryZ10 (v0.1)

A GUI application for downloading TikTok videos from data export with parallel processing
and batch download capabilities. Features include progress tracking, real-time logging,
and the ability to pause/resume downloads.

Features:
- Parallel download with configurable worker threads
- Batch processing with progress tracking
- Real-time logging in GUI
- File format detection and proper naming
- Automatic retry on failed downloads
- ZIP archive creation of downloaded content
- Duplicate URL detection and skipping

Dependencies:
    - tkinter
    - requests
    - concurrent.futures
    - logging
    
Usage:
    1. Run the script to launch GUI
    2. Select your JSON file
    3. Configure workers and batch size
    4. Start download and monitor progress

"""

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('errors.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

video_logger = logging.getLogger('video_links')
video_logger.setLevel(logging.INFO)
video_handler = logging.FileHandler('videos.log')
video_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
video_logger.addHandler(video_handler)


class TkinterHandler(logging.Handler):
    """Custom logging handler for Tkinter text widget.

    Implements a thread-safe logging handler that redirects log messages to a Tkinter
    text widget using a queue to ensure thread safety.

    Args:
        text_widget: ScrolledText widget to display logs
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.queue = queue.Queue()
        self.text_widget.after(100, self.check_queue)

    def emit(self, record):
        msg = self.format(record)
        self.queue.put(msg)

    def check_queue(self):
        while True:
            try:
                msg = self.queue.get_nowait()
                self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.see(tk.END)
            except queue.Empty:
                break
        self.text_widget.after(100, self.check_queue)


class TikTokGUI:
    """Main GUI application class for TikTok video downloader.

    Implements the graphical interface with progress tracking, logging display,
    and download controls.

    Args:
        root: Tkinter root window
    """
    def __init__(self, root):
        self.root = root
        self.root.title("TikTok Video Downloader")
        self.root.geometry("900x600")

        # Setup close window protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.downloader: Optional[TikTokDownloader] = None
        self.download_thread: Optional[threading.Thread] = None
        self.is_downloading = False
        self.executor = None  # Store ThreadPoolExecutor reference
        self.stop_event = threading.Event()

        self.create_gui()
        self.setup_logging()

    def create_gui(self):
        """Create and setup all GUI elements.

        Initializes all widgets including:
            - Settings frame with worker and batch size inputs
            - File selection controls
            - Progress bar
            - Log display area
            - Control buttons
        """
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Settings frame
        settings_frame = ttk.LabelFrame(
            main_frame, text="Settings", padding="5")
        settings_frame.grid(row=0, column=0, columnspan=2,
                            sticky=(tk.W, tk.E), pady=5)

        # Workers setting
        ttk.Label(settings_frame, text="Workers:").grid(
            row=0, column=0, padx=5)
        self.workers_var = tk.StringVar(value="2")
        ttk.Entry(settings_frame, textvariable=self.workers_var,
                  width=10).grid(row=0, column=1, padx=5)

        # Batch size setting
        ttk.Label(settings_frame, text="Batch Size:").grid(
            row=0, column=2, padx=5)
        self.batch_size_var = tk.StringVar(value="100")
        ttk.Entry(settings_frame, textvariable=self.batch_size_var,
                  width=10).grid(row=0, column=3, padx=5)

        # Schema file selection
        ttk.Label(settings_frame, text="Schema:").grid(row=0, column=4, padx=5)
        self.schema_path_var = tk.StringVar()
        self.schema_entry = ttk.Entry(
            settings_frame, textvariable=self.schema_path_var, width=30)
        self.schema_entry.grid(row=0, column=5, padx=5)

        # Schema status label
        self.status_var = tk.StringVar(value="No schema loaded")
        self.status_label = ttk.Label(
            settings_frame, textvariable=self.status_var, foreground='red')
        self.status_label.grid(
            row=1, column=4, columnspan=2, padx=5, pady=(2, 0))

        ttk.Button(settings_frame, text="Browse",
                   command=self.browse_schema).grid(row=0, column=6, padx=5)

        # Control buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=1, column=0, columnspan=2, pady=5)

        # Style configuration for taller buttons
        button_style = ttk.Style()

        # Horizontal and vertical padding
        button_style.configure('Tall.TButton', padding=(10, 8))

        self.start_button = tk.Button(
            buttons_frame,
            text="Start Download",
            command=self.start_download,
            state=tk.DISABLED,
            height=2,
            width=20,
            relief=tk.RAISED,
            font=('TkDefaultFont', 10, 'bold'),
            bg='#e1e1e1',
            fg='black',
            activebackground='#d4d4d4',
            activeforeground='black',
            disabledforeground='#666666'
        )
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = tk.Button(
            buttons_frame,
            text="Stop",
            command=self.stop_download,
            state=tk.DISABLED,
            height=2,
            width=20,
            relief=tk.RAISED,
            font=('TkDefaultFont', 10, 'bold'),
            bg='#e1e1e1',
            fg='black',
            activebackground='#d4d4d4',
            activeforeground='black',
            disabledforeground='#666666'
        )
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)


        # Add tooltip-style help text
        help_text = "Upload a schema file to enable downloads. You might need to wait a minute before starting to download."
        self.help_label = ttk.Label(
            buttons_frame, text=help_text, foreground='gray')
        self.help_label.grid(row=1, column=0, columnspan=2, pady=(2, 0))

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(
            row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # Log display
        self.log_text = scrolledtext.ScrolledText(main_frame, height=20)
        self.log_text.grid(row=3, column=0, columnspan=2,
                           sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def setup_logging(self):
        """Configure logging handlers for GUI and file output."""

        # Add GUI logging handler
        gui_handler = TkinterHandler(self.log_text)
        gui_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(gui_handler)
        video_logger.addHandler(gui_handler)

    def validate_schema(self, filename):
        """Validate the schema file and update UI accordingly"""
        try:
            # Try to load and validate the schema
            self.status_var.set("Validating schema...")
            self.status_label.configure(foreground='orange')
            self.root.update()

            with open(filename, 'r') as f:
                data = json.load(f)

            # Basic validation that it's a TikTok schema
            if 'Video' in data and 'Videos' in data['Video']:
                video_count = len(data['Video']['Videos'].get('VideoList', []))
                self.status_var.set(
                    f"Valid schema loaded - {video_count} videos found")
                self.status_label.configure(foreground='green')
                self.start_button.configure(state=tk.NORMAL)
            else:
                self.status_var.set("Invalid schema format")
                self.status_label.configure(foreground='red')
                self.start_button.configure(state=tk.DISABLED)

        except json.JSONDecodeError:
            self.status_var.set("Invalid JSON file")
            self.status_label.configure(foreground='red')
            self.start_button.configure(state=tk.DISABLED)
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            self.status_label.configure(foreground='red')
            self.start_button.configure(state=tk.DISABLED)

    def browse_schema(self):
        """Open file dialog for schema.json selection.

        Opens system file dialog filtered to show JSON files and updates
        the schema path variable with selected file.
        """

        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.schema_path_var.set(filename)
            self.validate_schema(filename)

    def update_progress(self, current, total):
        """Update progress bar with current download progress.

        Args:
            current: Number of items processed
            total: Total number of items to process
        """

        progress = (current / total) * 100 if total > 0 else 0
        self.progress_var.set(progress)
        self.root.update_idletasks()

    def start_download(self):
        """Initialize and begin download process.

        Validates inputs, creates TikTokDownloader instance, and starts
        download thread. Disables start button and enables stop button.
        """
        if not self.schema_path_var.get():
            messagebox.showerror("Error", "Please select a schema file first")
            return

        try:
            workers = int(self.workers_var.get())
            batch_size = int(self.batch_size_var.get())
        except ValueError:
            messagebox.showerror(
                "Error", "Workers and batch size must be valid numbers")
            return

        # Reset stop event
        self.stop_event.clear()

        self.downloader = TikTokDownloader(
            self.schema_path_var.get(),
            max_workers=workers,
            gui_callback=self.update_progress,
            stop_event=self.stop_event
        )

        self.is_downloading = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        self.download_thread = threading.Thread(
            target=self.run_download,
            args=(batch_size,)
        )
        # Make thread daemon so it exits when main thread exits
        self.download_thread.daemon = True
        self.download_thread.start()

    def on_closing(self):
        """Handle window closing event"""
        if self.is_downloading:
            if messagebox.askokcancel("Quit", "A download is in progress. Do you want to stop it and quit?"):
                self.stop_download()
                # Wait briefly for downloads to stop
                time.sleep(0.5)
                self.root.destroy()
        else:
            self.root.destroy()

    def stop_download(self):
        """Stop ongoing download process.

        Signals threads to stop, cancels pending downloads, and resets UI state.
        Waits for current operations to finish before complete stop.
        """
        if self.is_downloading:
            logger.info(
                "Stopping download... Please wait for current operations to finish.")
            self.stop_event.set()  # Signal threads to stop
            self.is_downloading = False
            self.stop_button.config(state=tk.DISABLED)

            # Cancel all pending tasks
            if self.downloader and self.downloader.current_executor:
                try:
                    self.downloader.current_executor.shutdown(wait=False)
                except Exception as e:
                    logger.error(f"Error shutting down executor: {e}")

            if self.download_thread and self.download_thread.is_alive():
                try:
                    # Wait for thread to finish
                    self.download_thread.join(timeout=1.0)
                except Exception as e:
                    logger.error(f"Error joining download thread: {e}")

            # Clean up downloader if it exists
            if self.downloader:
                try:
                    self.downloader.cleanup()
                except Exception as e:
                    logger.error(f"Error during cleanup: {e}")

            # Reset UI
            self.start_button.config(state=tk.NORMAL)
            self.progress_var.set(0)
            logger.info("Download stopped.")

    def run_download(self, batch_size):
        """Execute download process in separate thread.

        Args:
            batch_size: Number of videos to process in each batch

        Handles the main download workflow including schema loading,
        parallel downloads, and cleanup.
        """
        try:
            schema_data = self.downloader.load_schema()
            videos = self.downloader.get_video_links(schema_data)

            if not videos:
                logger.warning("No videos found in schema")
                return

            successful_downloads = self.downloader.parallel_download_videos(
                videos,
                batch_size=batch_size,
                stop_event=lambda: not self.is_downloading
            )

            if successful_downloads:
                self.downloader.create_zip()
                logger.info(
                    f"Process completed successfully! {len(successful_downloads)} videos processed")
            else:
                logger.error("No videos were successfully downloaded")

        except Exception as e:
            logger.error(f"Process failed: {e}")
        finally:
            self.downloader.cleanup()
            self.is_downloading = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.progress_var.set(0)


class TikTokDownloader:
    """Core downloader implementation with parallel processing capability.

    Handles actual video downloading, batch processing, and file management.

    Args:
        schema_path: Path to TikTok data export schema file
        max_workers: Maximum number of parallel download threads
        gui_callback: Function to call for progress updates
        stop_event: Threading event to signal stop request
    """
    def __init__(self, schema_path, max_workers=4, gui_callback=None, stop_event=None):
        self.schema_path = schema_path
        import sys
        if getattr(sys, 'frozen', False):
            # If the application is bundled by PyInstaller
            application_path = os.path.dirname(sys.executable)
        else:
            # If running from a Python interpreter
            application_path = os.path.dirname(os.path.abspath(__file__))

        # Create saves directory path relative to application location
        self.download_dir = os.path.join(application_path, "saves")
        logger.info(f"Setting download directory to: {self.download_dir}")

        self.max_workers = max_workers
        self.gui_callback = gui_callback
        self.stop_event = stop_event
        self.current_executor = None  # Store reference to current executor
        self.ensure_directories()

        atexit.register(self.emergency_cleanup)

    def ensure_directories(self):
        """Create necessary download directories if they don't exist."""
        os.makedirs(self.download_dir, exist_ok=True)

    def load_schema(self):
        """Load and parse TikTok data export schema file."""
        try:
            with open(self.schema_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            raise

    def get_video_links(self, data):
        """Extract video URLs and metadata from schema."""
        videos = []
        processed_urls = set()

        def add_video(video, video_type, is_personal):
            if not video.get('Link'):
                return
            urls = video['Link'].split('\n')
            for url in urls:
                url = url.strip()
                if not url or url in processed_urls:
                    continue
                processed_urls.add(url)
                videos.append({
                    'url': url,
                    'date': video.get('Date', ''),
                    'type': video_type,
                    'is_personal': is_personal
                })

        if 'Video' in data and 'Videos' in data['Video']:
            for video in data['Video']['Videos'].get('VideoList', []):
                add_video(video, 'posted', True)

        videos.sort(key=lambda x: x['date'], reverse=True)

        for video in videos:
            video_logger.info(
                f"Type: {video['type']}, Personal: {video['is_personal']}, "
                f"Date: {video['date']}, URL: {video['url']}"
            )

        personal_count = sum(1 for v in videos if v['is_personal'])
        logger.info(
            f"Found {len(videos)} unique videos to download ({personal_count} personal, "
            f"{len(videos) - personal_count} other)"
        )

        return videos

    def download_video(self, video_info):
        """Download single video file with retry logic."""

        # Check stop event before starting download
        if self.stop_event and self.stop_event.is_set():
            return None

        try:
            url = video_info['url']
            date_str = video_info['date'].split(
            )[0] if video_info['date'] else 'unknown_date'
            video_type = video_info['type']
            is_personal = video_info['is_personal']

            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            prefix = "personal" if is_personal else "other"

            is_image = any(ext in url.lower()
                           for ext in ['.jpg', '.jpeg', '.png', '.webp'])
            extension = '.jpg' if is_image else '.mp4'

            filename = f"{prefix}_{date_str}_{video_type}_{url_hash}{extension}"
            filepath = os.path.join(self.download_dir, filename)

            if os.path.exists(filepath):
                existing_size = os.path.getsize(filepath)
                logger.info(
                    f"File already exists: {filepath} ({existing_size / 1024:.2f}KB)")
                return filepath

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, stream=True, timeout=30)
                    response.raise_for_status()

                    total_size = 0
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                total_size += len(chunk)
                                f.write(chunk)

                    return filepath

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {url}: {e}. Retrying...")
                        time.sleep(2)
                    else:
                        logger.error(f"All attempts failed for {url}: {e}")
                        video_logger.error(
                            f"Failed to download: {url}, Error: {str(e)}")
                        raise

        except Exception as e:
            logger.error(
                f"Error downloading media from {video_info['url']}: {e}")
            return None

    def parallel_download_videos(self, videos: List[Dict], batch_size=100, stop_event=None) -> List[str]:
        """Execute parallel video downloads with batch processing.

        Args:
            videos: List of video information dictionaries
            batch_size: Number of videos to process in each batch
            stop_event: Threading event to signal stop request

        Returns:
            list: Paths of successfully downloaded files
        """
        all_successful_downloads = []
        all_failed_downloads = []
        processed_urls = set()

        total_videos = len(videos)
        videos_processed = 0

        for i in range(0, len(videos), batch_size):
            if stop_event and stop_event():
                logger.info("Download stopped by user")
                break

            batch = videos[i:i + batch_size]
            logger.info(
                f"\nProcessing batch {(i//batch_size) + 1} "
                f"({i+1} to {min(i+batch_size, total_videos)} of {total_videos} videos)"
            )

            successful_downloads = []
            failed_downloads = []

            self.current_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers)
            try:
                future_to_video = {
                    self.current_executor.submit(self.download_video, video): video
                    for video in batch
                }

                for future in concurrent.futures.as_completed(future_to_video):
                    if self.stop_event and self.stop_event.is_set():
                        # Cancel all pending futures
                        for f in future_to_video:
                            f.cancel()
                        self.current_executor.shutdown(wait=False)
                        logger.info("Cancelling remaining downloads...")
                        return all_successful_downloads

                    video = future_to_video[future]
                    url = video['url']

                    if url in processed_urls:
                        logger.warning(f"Skipping duplicate URL: {url}")
                        continue

                    processed_urls.add(url)
                    videos_processed += 1

                    try:
                        result = future.result()
                        if result:
                            if isinstance(result, str):
                                if os.path.exists(result) and os.path.getsize(result) > 0:
                                    successful_downloads.append(result)
                                    logger.info(
                                        f"Verified successful download: {result} "
                                        f"(Size: {os.path.getsize(result) / 1024:.2f}KB)"
                                    )
                                else:
                                    logger.error(
                                        f"Download reported success but file is invalid: {result}")
                                    failed_downloads.append(url)
                            else:
                                successful_downloads.append(result)
                                logger.info(f"Processed directory: {result}")
                        else:
                            failed_downloads.append(url)
                            logger.error(f"Failed to process video: {url}")
                    except Exception as e:
                        failed_downloads.append(url)
                        logger.error(f"Exception while processing {url}: {e}")
                        video_logger.error(
                            f"Failed to download: {url}, Error: {str(e)}")

                    # Update progress in GUI
                    if self.gui_callback:
                        self.gui_callback(videos_processed, total_videos)
            finally:
                self.current_executor.shutdown(wait=True)
                self.current_executor = None

                video = future_to_video[future]
                url = video['url']

                if url in processed_urls:
                    logger.warning(f"Skipping duplicate URL: {url}")
                    continue

                processed_urls.add(url)
                videos_processed += 1

                try:
                    result = future.result()
                    if result:
                        if isinstance(result, str):
                            if os.path.exists(result) and os.path.getsize(result) > 0:
                                successful_downloads.append(result)
                                logger.info(
                                    f"Verified successful download: {result} "
                                    f"(Size: {os.path.getsize(result) / 1024:.2f}KB)"
                                )
                            else:
                                logger.error(f"Download reported success but file is invalid: {result}")
                                failed_downloads.append(url)
                        else:
                            successful_downloads.append(result)
                            logger.info(f"Processed directory: {result}")
                    else:
                        failed_downloads.append(url)
                        logger.error(f"Failed to process video: {url}")
                except Exception as e:
                    failed_downloads.append(url)
                    logger.error(f"Exception while processing {url}: {e}")
                    video_logger.error(f"Failed to download: {url}, Error: {str(e)}")

                # Update progress in GUI
                if self.gui_callback:
                    self.gui_callback(videos_processed, total_videos)

            # Add batch results to overall totals
            all_successful_downloads.extend(successful_downloads)
            all_failed_downloads.extend(failed_downloads)

            # Log batch summary
            logger.info(f"\nBatch {(i//batch_size) + 1} Summary:")
            logger.info(
                f"Successful downloads in this batch: {len(successful_downloads)}")
            logger.info(
                f"Failed downloads in this batch: {len(failed_downloads)}")

            # Calculate and log batch size
            batch_size_bytes = sum(os.path.getsize(path)
                                   for path in successful_downloads if os.path.isfile(path))
            batch_size_mb = batch_size_bytes / (1024*1024)
            logger.info(f"Batch download size: {batch_size_mb:.2f}MB")

        # Log overall final summary
        logger.info("\nOverall Download Summary:")
        logger.info(f"Total unique URLs processed: {len(processed_urls)}")
        logger.info(
            f"Total successful downloads: {len(all_successful_downloads)}")
        logger.info(f"Total failed downloads: {len(all_failed_downloads)}")

        # Log all successful files and their sizes
        logger.info("\nAll successfully downloaded files:")
        total_size = 0
        for path in all_successful_downloads:
            if os.path.isfile(path):
                size = os.path.getsize(path)
                total_size += size
                logger.info(f"- {path}: {size / 1024:.2f}KB")
            elif os.path.isdir(path):
                dir_size = sum(os.path.getsize(os.path.join(root, name))
                               for root, _, files in os.walk(path)
                               for name in files)
                total_size += dir_size
                logger.info(f"- {path} (directory): {dir_size / 1024:.2f}KB")

        logger.info(
            f"\nTotal downloaded size: {total_size / (1024*1024):.2f}MB")

        return all_successful_downloads

    def create_zip(self):
        """Create final zip archive"""
        try:
            zip_name = "videos.zip"
            if os.path.exists(zip_name):
                os.remove(zip_name)
            cmd = ['zip', '-r', zip_name, self.download_dir]
            subprocess.run(cmd, check=True)
            logger.info(f"Created zip archive: {zip_name}")
        except Exception as e:
            logger.error(f"Error creating zip: {e}")
            raise

    def cleanup(self):
        """Clean up temporary directories and resources"""
        try:
            # Stop all active downloads
            if self.current_executor:
                try:
                    self.current_executor.shutdown(wait=False)
                except Exception as e:
                    logger.error(f"Error shutting down executor: {e}")

            # Clean up download directory
            if os.path.exists(self.download_dir):
                try:
                    subprocess.run(
                        ['rm', '-rf', self.download_dir], check=True)
                    logger.info("Cleaned up temporary directories")
                except Exception as e:
                    logger.error(f"Error cleaning directories: {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def emergency_cleanup(self):
        """Emergency cleanup for unexpected termination"""
        try:
            logger.info("Performing emergency cleanup...")
            if self.current_executor:
                self.current_executor.shutdown(wait=False)
            if os.path.exists(self.download_dir):
                subprocess.run(['rm', '-rf', self.download_dir], check=False)
        except Exception as e:
            # Don't log during emergency cleanup as logging might not be available
            print(f"Emergency cleanup error: {e}")

def signal_handler(signum, frame):
    """
    Handles signal communication between all threads to stop downloads
    """
    for thread in threading.enumerate():
        if thread != threading.current_thread():
            try:
                if hasattr(thread, '_stop'):
                    thread._stop()
            except Exception:
                pass


def main():
    """Initialize and start GUI application.

    Creates root window and starts Tkinter main loop.
    """
    try:
        root = tk.Tk()
        app = TikTokGUI(root)

        if platform.system() == 'Darwin':  # macOS
            root.bind('<Command-w>', lambda e: app.on_closing())
            root.bind('<Command-q>', lambda e: app.on_closing())
        else:  # Windows/Linux
            root.bind('<Alt-F4>', lambda e: app.on_closing())
            root.bind('<Control-w>', lambda e: app.on_closing())

        # Use the class's on_closing method for the window close button
        root.protocol("WM_DELETE_WINDOW", app.on_closing)

        # Set up signal handlers after creating the app
        def handle_signal(signum, frame):
            app.on_closing()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        root.mainloop()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        try:
            root.destroy()
        except:
            pass

if __name__ == "__main__":
    main()
