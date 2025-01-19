# TikTok Video Downloader and Compressor

Note: This is intended to be used by linux wizards.

## Overview

This script is designed to download, compress, and archive TikTok videos from a structured data export file, `schema.json`. It supports downloading personal videos, as well as videos from your favorites and browsing history, with multithreaded downloading for efficiency.

## Requirements

- Python 3.x
- pip (Python package manager)
- `requests` package
- `argparse` package (part of Python 3.x standard library)
- `concurrent.futures` package (part of Python 3.x standard library)

## Installation

1. Ensure you have Python 3.x installed on your system.
2. Install the required Python package by running:
   ```bash
    pip3 install requests
    ```

## Usage

Place `schema.json` in the same directory as main.py. This file should contain the structured data export from TikTok.

Run the script using the following command from the terminal:

```
python main.py [OPTIONS]

Available options are:

--workers N: Set number of parallel download workers (default is 2). Adjust based on your system's resources.
--batch-size N: Specify the number of videos to process before asking for user confirmation to proceed (default is 100).
```

### Example Commands

To download videos with 4 concurrent download threads:
`python main.py --workers 4`

Output

- Downloaded Videos: Videos will be downloaded to the downloads directory.
- Archive: A videos.zip file will be created containing all the processed videos.

Logs
- errors.log: Captures all error messages and exceptions.
- videos.log: Logs all video links processed, along with their metadata.

## Cleanup

The script automatically cleans up temporary files and directories after execution. If you encounter issues during execution, review logs for more information.

## Notes

Ensure `schema.json` is correctly formatted and includes the necessary fields.

The script assumes you have permission to download the videos in schema.json.

Modify `main.py` and `schema.json` paths if not running from the same directory.

For any issues or contribution requests, please file an issue or reach out via the repository's contact information.

This `README.md` provides clear instructions for setting up and using the program, along with options for customization and handling outputs. Adjust paths and instructions based on your specific environment or setup as needed.
