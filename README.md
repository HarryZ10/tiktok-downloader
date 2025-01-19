# TikTok Video Downloader with GUI
Note: This application provides a user-friendly interface for downloading TikTok videos from your data export.

## Overview
This Python application provides a graphical interface for downloading and archiving TikTok videos from a structured data export file JSON. It features parallel processing, progress tracking, batch downloading, and automatic retry mechanisms for failed downloads.

### Key Features
- GUI interface with real-time progress tracking
- Parallel download with configurable worker threads
- Batch processing with progress monitoring
- Automatic retry on failed downloads
- File format detection and proper naming
- Real-time logging in GUI and to files
- ZIP archive creation of downloaded content
- Duplicate URL detection and skipping

## Requirements
- Python 3.x
- pip (Python package manager)
- tkinter (usually comes with Python, required for GUI)
- Required Python packages:
  - requests
  - concurrent.futures (part of Python standard library)
  - logging (part of Python standard library)

## Installation

1. Ensure Python 3.x is installed on your system
2. Install the required Python packages:
   ```bash
   pip3 install requests
   pip3 install urllib3
   pip3 install pyinstaller
   ```
3. On Linux/macOS systems, ensure tkinter is installed:
   ```bash
   # For Ubuntu/Debian
   sudo apt-get install python3-tk
   
   # For macOS (using Homebrew)
   brew install python-tk
   ```

## Usage

### Starting the Application

Double click the TikTokDownloader Unix EXE. THIS will bring up
a GUI and a terminal. You ignore the terminal.

OR

You can open terminal and run it by command.

### Using the GUI
1. Click "Browse" to select your JSON file (from TikTok data export)
2. Configure settings:
   - Workers: Number of parallel download threads (default: 2)
   - Batch Size: Videos to process in each batch (default: 100)
3. Click "Start Download" to begin the process
4. Monitor progress through:
   - Progress bar
   - Real-time log display
   - Status messages

### Control Options
- Start Download: Begin the download process
- Stop: Safely stop ongoing downloads
- Close Window: Safely exit the application

## Output Files and Directories

### Generated Files
- `downloads/`: Directory containing downloaded videos
- `videos.zip`: Final archive of all downloaded content
- `errors.log`: Error messages and exceptions
- `videos.log`: Processing log with video metadata

### File Naming Convention
Downloaded files follow the pattern:
`[type]_[date]_[category]_[unique_hash].[extension]`
- type: "personal" or "other"
- date: Video date
- category: Video category
- hash: Unique identifier
- extension: .mp4 for videos, .jpg/.jpeg/.png/.webp for images

## Error Handling and Recovery
- Automatic retry for failed downloads (up to 3 attempts)
- Duplicate file detection and skipping
- Safe cleanup on unexpected termination
- Detailed logging for troubleshooting

## Notes
- The application requires a valid TikTok data export JSON file
- Download speed depends on your internet connection and number of workers
- Large numbers of workers may impact system performance
- Progress is saved between batches
- The application safely handles interruptions and cleanup

## Copyright and License
Copyright (c) 2024 Harry Zhu. Licensed under a permissive license that allows use and modification with attribution.

## Troubleshooting
1. Check `errors.log` for detailed error messages
2. Ensure stable internet connection
3. Verify your JSON format and content
4. Adjust worker count if downloads are unstable
5. Check system resources if processing large batches

For any issues or contributions, please file an issue or contact the repository maintainers.