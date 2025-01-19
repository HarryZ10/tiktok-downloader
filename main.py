#!/usr/bin/env python3
import json
import os
import subprocess
import argparse
from datetime import datetime
import requests
import logging
import concurrent.futures
from typing import List, Dict
import time

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

class TikTokDownloader:
    def __init__(self, schema_path, max_workers=4):
        self.schema_path = schema_path
        self.download_dir = "downloads"
        self.max_workers = max_workers
        self.ensure_directories()

    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        os.makedirs(self.download_dir, exist_ok=True)

    def load_schema(self):
        """Load the TikTok schema from JSON file"""
        try:
            with open(self.schema_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            raise

    def get_video_links(self, data):
        """Extract all video links from the schema based on settings"""
        videos = []
        processed_urls = set()  # Track unique URLs at the extraction level

        def add_video(video, video_type, is_personal):
            if not video.get('Link'):
                return
            # Split URLs in case of multi-media posts
            urls = video['Link'].split('\n')
            for url in urls:
                url = url.strip()
                if not url or url in processed_urls:
                    continue
                processed_urls.add(url)
                videos.append({
                    'url': url,  # Store single URL instead of potentially multiple
                    'date': video.get('Date', ''),
                    'type': video_type,
                    'is_personal': is_personal
                })

        # Process personal videos
        if 'Video' in data and 'Videos' in data['Video']:
            for video in data['Video']['Videos'].get('VideoList', []):
                add_video(video, 'posted', True)

        # Sort videos by date (newest first)
        videos.sort(key=lambda x: x['date'], reverse=True)

        # Log all video links with their metadata
        for video in videos:
            video_logger.info(
                f"Type: {video['type']}, Personal: {video['is_personal']}, "
                f"Date: {video['date']}, URL: {video['url']}"
            )

        # Log summary of videos found
        personal_count = sum(1 for v in videos if v['is_personal'])
        logger.info(
            f"Found {len(videos)} unique videos to download ({personal_count} personal, {len(videos) - personal_count} other)")

        return videos


    def download_video(self, video_info):
        """Download a single video"""
        try:
            url = video_info['url']  # Now handling single URL
            date_str = video_info['date'].split(
            )[0] if video_info['date'] else 'unknown_date'
            video_type = video_info['type']
            is_personal = video_info['is_personal']

            # Create unique filename using URL hash
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            prefix = "personal" if is_personal else "other"

            # Determine file extension based on URL
            is_image = any(ext in url.lower()
                        for ext in ['.jpg', '.jpeg', '.png', '.webp'])
            extension = '.jpg' if is_image else '.mp4'

            filename = f"{prefix}_{date_str}_{video_type}_{url_hash}{extension}"
            filepath = os.path.join(self.download_dir, filename)

            # Skip if file already exists with matching size
            if os.path.exists(filepath):
                existing_size = os.path.getsize(filepath)
                logger.info(
                    f"File already exists: {filepath} ({existing_size / 1024:.2f}KB)")
                return filepath

            # Download with retry logic
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

            return None

        except Exception as e:
            logger.error(f"Error downloading media from {video_info['url']}: {e}")
            return None

    def parallel_download_videos(self, videos: List[Dict], batch_size=100) -> List[str]:
        """Download videos in parallel using ThreadPoolExecutor, processing in batches"""
        all_successful_downloads = []
        all_failed_downloads = []
        processed_urls = set()  # Track unique URLs we've processed

        # Process videos in batches
        for i in range(0, len(videos), batch_size):
            batch = videos[i:i + batch_size]
            logger.info(
                f"\nProcessing batch {(i//batch_size) + 1} ({i+1} to {min(i+batch_size, len(videos))} of {len(videos)} videos)")

            # Ask for confirmation before proceeding
            if i > 0:  # Don't ask for first batch
                response = input("\nContinue with next batch? [y/N]: ").lower()
                if response != 'y':
                    logger.info("Stopping at user request")
                    break

            successful_downloads = []
            failed_downloads = []

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit batch of download tasks
                future_to_video = {executor.submit(
                    self.download_video, video): video for video in batch}

                # Process completed downloads
                for future in concurrent.futures.as_completed(future_to_video):
                    video = future_to_video[future]
                    url = video['url']

                    # Skip if we've already processed this URL
                    if url in processed_urls:
                        logger.warning(f"Skipping duplicate URL: {url}")
                        continue

                    processed_urls.add(url)

                    try:
                        result = future.result()
                        if result:
                            # Verify the file exists and has content
                            if isinstance(result, str):  # Single file
                                if os.path.exists(result) and os.path.getsize(result) > 0:
                                    successful_downloads.append(result)
                                    logger.info(
                                        f"Verified successful download: {result} (Size: {os.path.getsize(result) / 1024:.2f}KB)")
                                else:
                                    logger.error(
                                        f"Download reported success but file is invalid: {result}")
                                    failed_downloads.append(url)
                            else:  # Directory with multiple files
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
            batch_size_bytes = sum(os.path.getsize(
                path) for path in successful_downloads if os.path.isfile(path))
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
        """Clean up temporary directories"""
        try:
            subprocess.run(['rm', '-rf', self.download_dir], check=True)
            logger.info("Cleaned up temporary directories")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Download TikTok videos from data export')
    parser.add_argument('--workers', type=int, default=2,
                        help='Number of parallel download workers (default: 2)')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Number of videos to process before asking to continue (default: 100)')
    args = parser.parse_args()

    # Initialize downloader
    downloader = TikTokDownloader(
        'schema.json',
        max_workers=args.workers
    )

    try:
        # Load schema and get video links
        schema_data = downloader.load_schema()
        videos = downloader.get_video_links(schema_data)

        if not videos:
            logger.warning("No videos found in schema")
            return

        # Download videos in parallel with batch processing
        successful_downloads = downloader.parallel_download_videos(
            videos, batch_size=args.batch_size)

        if not successful_downloads:
            logger.error("No videos were successfully downloaded")
            return

        downloader.create_zip()
        downloader.cleanup()

        logger.info(
            f"Process completed successfully! {len(successful_downloads)} videos processed")

    except Exception as e:
        logger.error(f"Process failed: {e}")
    finally:
        try:
            downloader.cleanup()
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")


if __name__ == "__main__":
    main()
