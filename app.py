from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import uuid
import subprocess
import sys
import logging
import re
import shutil
import requests
import zipfile
import io
import json
from datetime import datetime
from urllib.parse import urlparse

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create issues directory if it doesn't exist
ISSUES_DIR = 'issues'
if not os.path.exists(ISSUES_DIR):
    os.makedirs(ISSUES_DIR)

def sanitize_filename(filename):
    logger.debug(f"Original filename: {filename}")
    
    # Remove any existing extension
    filename = re.sub(r'\.[^.]+$', '', filename)
    logger.debug(f"After removing extension: {filename}")
    
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    logger.debug(f"After removing invalid chars: {filename}")
    
    # Replace special characters with spaces
    filename = re.sub(r'[^\w\s-]', ' ', filename)
    logger.debug(f"After replacing special chars: {filename}")
    
    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)
    logger.debug(f"After replacing multiple spaces: {filename}")
    
    # Remove leading/trailing spaces and underscores
    filename = filename.strip(' _')
    logger.debug(f"After stripping: {filename}")
    
    # If filename is empty after cleaning, use a default name
    if not filename:
        filename = 'youtube_video'
    
    # Limit length to 100 characters
    filename = filename[:100]
    logger.debug(f"After length limit: {filename}")
    
    # Remove any trailing spaces or underscores again
    filename = filename.rstrip(' _')
    logger.debug(f"Final cleaned filename: {filename}")
    
    return filename

def update_ytdlp():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        return True
    except subprocess.CalledProcessError:
        return False

def install_ffmpeg():
    """Download and install ffmpeg on Windows"""
    try:
        # Create ffmpeg directory in the current working directory
        ffmpeg_dir = os.path.join(os.getcwd(), 'ffmpeg')
        os.makedirs(ffmpeg_dir, exist_ok=True)
        
        # Download ffmpeg
        logger.info("Downloading ffmpeg...")
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        response = requests.get(url)
        response.raise_for_status()
        
        # Extract the zip file
        logger.info("Extracting ffmpeg...")
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(ffmpeg_dir)
        
        # Find the extracted ffmpeg.exe
        for root, dirs, files in os.walk(ffmpeg_dir):
            if 'ffmpeg.exe' in files:
                ffmpeg_path = os.path.join(root, 'ffmpeg.exe')
                # Copy ffmpeg.exe to the current directory
                shutil.copy2(ffmpeg_path, os.getcwd())
                logger.info("ffmpeg installed successfully!")
                return True
        
        logger.error("Could not find ffmpeg.exe in the downloaded files")
        return False
        
    except Exception as e:
        logger.error(f"Failed to install ffmpeg: {str(e)}")
        return False

def check_ffmpeg():
    """Check if ffmpeg is installed and install it if not"""
    try:
        # First try to run ffmpeg from the current directory
        ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg.exe')
        if os.path.exists(ffmpeg_path):
            subprocess.run([ffmpeg_path, '-version'], capture_output=True, check=True)
            return True
            
        # Then try to run ffmpeg from PATH
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("ffmpeg not found, attempting to install...")
        return install_ffmpeg()

def debug_formats(url):
    """Debug function to list available formats"""
    try:
        with yt_dlp.YoutubeDL({'listformats': True, 'quiet': False}) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"Error debugging formats: {e}")
        return None

class MyLogger:
    def debug(self, msg):
        logger.debug(msg)
    def warning(self, msg):
        logger.warning(msg)
    def error(self, msg):
        logger.error(msg)

@app.route('/')
def index():
    return render_template('index.html')

def get_platform_specific_options(url):
    """Get platform-specific yt-dlp options"""
    options = {
        'format': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',  # Default format for highest quality
        'referer': 'https://www.youtube.com/',  # Default referer
        'extract_flat': False,
        'quiet': False,
        'no_warnings': False,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'extractor_retries': 3,
        'socket_timeout': 30,
        'retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
        'keepvideo': False,
        'writethumbnail': False,
        'writesubtitles': False,
        'writeautomaticsub': False,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'postprocessors': [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            },
            {
                'key': 'FFmpegMetadata',
            }
        ],
        'logger': MyLogger(),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
        }
    }

    # Platform-specific configurations
    if 'youtube.com' in url or 'youtu.be' in url:
        options.update({
            'format': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
            'referer': 'https://www.youtube.com/',
        })
    elif 'instagram.com' in url:
        options.update({
            'format': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
            'referer': 'https://www.instagram.com/',
            'extract_flat': False,
            'noplaylist': True,
            'extract_flat_playlist': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Referer': 'https://www.instagram.com/',
                'Cookie': 'ig_did=1; ig_nrcb=1; ds_user_id=1; sessionid=1; csrftoken=1',
                'X-IG-App-ID': '936619743392459',
                'X-Requested-With': 'XMLHttpRequest',
                'X-Instagram-AJAX': '1',
                'X-ASBD-ID': '198387',
            },
            'extractor_args': {
                'instagram': {
                    'login': None,
                    'password': None,
                    'client_id': '936619743392459',
                    'client_secret': '1c2d3e4f5g6h7i8j9k0l',
                    'extract_flat': False,
                    'extract_flat_playlist': False,
                }
            }
        })
    elif 'twitter.com' in url or 'x.com' in url:
        options.update({
            'format': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
            'referer': 'https://twitter.com/',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Referer': 'https://twitter.com/',
            }
        })

    return options

@app.route('/download', methods=['POST'])
def download_video():
    temp_dir = None
    try:
        # The application now relies on system-installed ffmpeg

        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Please provide a URL'}), 400

        # Check if the URL is a YouTube URL and return an error if it is
        if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
            logger.warning(f"Attempted YouTube download for URL: {url}")
            return jsonify({'error': 'Downloading from YouTube is currently not supported due to platform restrictions.'}), 400

        logger.info(f"Attempting to download video from URL: {url}")

        # Create a temporary directory for downloads
        temp_dir = tempfile.mkdtemp()
        logger.debug(f"Created temp directory: {temp_dir}")
        
        # Get platform-specific options
        ydl_opts = get_platform_specific_options(url)
        ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(id)s.%(ext)s')
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Get video info first
                logger.info("Extracting video information...")
                info = ydl.extract_info(url, download=False)
                
                # Validate info object
                if not info:
                    logger.error("No video information extracted")
                    return jsonify({'error': 'Could not extract video information. The URL might be invalid or the video might be private.'}), 400
                
                if not isinstance(info, dict):
                    logger.error(f"Info object is not a dictionary, got: {type(info)}")
                    return jsonify({'error': 'Invalid video information format'}), 400

                # Debug available formats
                if 'formats' in info:
                    # Log available formats
                    formats = info['formats']
                    logger.info(f"Available formats: {len(formats)}")
                    for fmt in formats[:5]:  # Log first 5 formats
                        logger.info(f"Format: {fmt.get('format_id')} - {fmt.get('ext')} - {fmt.get('resolution')} - {fmt.get('vcodec')} - {fmt.get('acodec')}")

                # Extract basic video information safely
                video_id = info.get('id', str(uuid.uuid4())[:8])
                
                # Try to get the caption/description first, fall back to title if not available
                raw_caption = info.get('description', '') or info.get('caption', '') or info.get('title', f'video_{video_id}')
                
                # Clean up the caption more aggressively
                video_caption = sanitize_filename(raw_caption)
                if not video_caption:
                    video_caption = f'video_{video_id}'
                
                logger.info(f"Raw caption: {raw_caption}")
                logger.info(f"Cleaned caption: {video_caption}")
                logger.info(f"Video ID: {video_id}")
                
                # Download the video
                logger.info("Starting video download...")
                with yt_dlp.YoutubeDL(ydl_opts) as download_ydl:
                    download_info = download_ydl.extract_info(url, download=True)
                
                if not download_info or not isinstance(download_info, dict):
                    logger.error(f"Invalid download info: {type(download_info)}")
                    return jsonify({'error': 'Failed to download video'}), 500

                # Find the downloaded file
                downloaded_files = [f for f in os.listdir(temp_dir) 
                                  if os.path.isfile(os.path.join(temp_dir, f)) and (f.endswith('.mp4') or f.endswith('.m4v') or f.endswith('.mov'))]
                
                if not downloaded_files:
                    logger.error(f"No downloaded files found in {temp_dir}")
                    all_files = os.listdir(temp_dir)
                    logger.error(f"All files in temp dir: {all_files}")
                    
                    # For Instagram, try to find any video file
                    if 'instagram.com' in url:
                        all_files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
                        logger.info(f"All files in temp dir for Instagram: {all_files}")
                        if all_files:
                            downloaded_file_path = os.path.join(temp_dir, all_files[0])
                            logger.info(f"Using first available file: {all_files[0]}")
                        else:
                            return jsonify({'error': 'Video downloaded but file not found. The post might be private or not contain a video.'}), 500
                    else:
                        return jsonify({'error': 'Video downloaded but file not found'}), 500
                else:
                    # Get the downloaded file
                    downloaded_file_path = os.path.join(temp_dir, downloaded_files[0])
                    logger.info(f"Using file: {downloaded_files[0]}")
                
                # Verify the file has audio streams
                try:
                    ffprobe_cmd = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a', downloaded_file_path]
                    result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout.strip():
                        logger.info("Audio stream detected in downloaded file")
                    else:
                        logger.warning("No audio stream detected in downloaded file")
                except Exception as e:
                    logger.warning(f"Could not verify audio stream: {e}")
                
                # Create a response with the file
                response = send_file(
                    downloaded_file_path,
                    as_attachment=True,
                    download_name=f"{video_caption}.mp4",
                    mimetype='video/mp4'
                )
                
                # Set the Content-Disposition header directly
                safe_filename = f"{video_caption}.mp4".replace('"', '\\"')  # Escape quotes
                response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}'
                
                # Add cleanup callback to the response
                @response.call_on_close
                def cleanup():
                    try:
                        if temp_dir and os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                            logger.info(f"Cleaned up temporary directory: {temp_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp directory: {e}")
                
                return response

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.error(f"yt-dlp Download error: {error_msg}")
                
                # Check for specific errors
                if "Unable to download API page" in error_msg:
                    return jsonify({'error': 'API access failed. The video might be region-blocked or private.'}), 400
                elif "getaddrinfo failed" in error_msg:
                    return jsonify({'error': 'Network connection error. Please check your internet connection.'}), 500
                elif "Private video" in error_msg:
                    return jsonify({'error': 'This video is private and cannot be downloaded.'}), 400
                elif "Video unavailable" in error_msg:
                    return jsonify({'error': 'This video is unavailable or has been removed.'}), 400
                else:
                    return jsonify({'error': f'Download failed: {error_msg}'}), 500
                    
            except Exception as e:
                logger.error(f"Unexpected error during download: {str(e)}")
                return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Top-level error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Video downloader is running'})

@app.route('/debug-formats', methods=['POST'])
def debug_video_formats():
    """Debug endpoint to check available formats for a URL"""
    try:
        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Please provide a URL'}), 400
        
        info = debug_formats(url)
        if info and 'formats' in info:
            formats = []
            for fmt in info['formats']:
                formats.append({
                    'format_id': fmt.get('format_id'),
                    'ext': fmt.get('ext'),
                    'resolution': fmt.get('resolution'),
                    'vcodec': fmt.get('vcodec'),
                    'acodec': fmt.get('acodec'),
                    'filesize': fmt.get('filesize'),
                    'tbr': fmt.get('tbr')
                })
            return jsonify({'formats': formats})
        else:
            return jsonify({'error': 'Could not extract format information'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Debug error: {str(e)}'}), 500

@app.route('/report-issue', methods=['POST'])
def report_issue():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['type', 'url', 'description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create issue object
        issue = {
            'id': datetime.now().strftime('%Y%m%d%H%M%S'),
            'timestamp': datetime.now().isoformat(),
            'type': data['type'],
            'url': data['url'],
            'description': data['description'],
            'status': 'new'
        }
        
        # Save issue to JSON file
        issue_file = os.path.join(ISSUES_DIR, f'issue_{issue["id"]}.json')
        with open(issue_file, 'w') as f:
            json.dump(issue, f, indent=2)
        
        logger.info(f'New issue reported: {issue["id"]}')
        return jsonify({'message': 'Issue reported successfully', 'id': issue['id']}), 200
        
    except Exception as e:
        logger.error(f'Error reporting issue: {str(e)}')
        return jsonify({'error': 'Failed to report issue'}), 500

if __name__ == '__main__':
    # Determine debug mode based on environment variable
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['1', 'true']
    app.run(debug=debug_mode)