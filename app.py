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
import time

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
        filename = 'tiktok_video'
    
    # Limit length to 100 characters
    filename = filename[:100]
    logger.debug(f"After length limit: {filename}")
    
    # Remove any trailing spaces or underscores again
    filename = filename.rstrip(' _')
    logger.debug(f"Final cleaned filename: {filename}")
    
    return filename

def update_ytdlp():
    """Update yt-dlp to the latest version"""
    try:
        # Try to update to nightly build first (most up-to-date)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default]", "--force-reinstall"])
        logger.info("Successfully updated yt-dlp")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to update yt-dlp: {e}")
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
        logger.error("System ffmpeg not found in PATH!")
        return False

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

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/how-to-use')
def how_to_use():
    return render_template('how_to_use.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/supported-platforms')
def supported_platforms():
    return render_template('supported_platforms.html')

@app.route('/video-quality-guide')
def video_quality_guide():
    return render_template('video_quality_guide.html')

@app.route('/ads.txt')
def ads_txt():
    return send_file('ads.txt', mimetype='text/plain')

def get_tiktok_options(url):
    """Get TikTok-specific yt-dlp options with improved headers and settings"""
    options = {
        'format': 'best[height<=2160]/best',
        'extract_flat': False,
        'quiet': False,
        'no_warnings': False,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'extractor_retries': 5,
        'socket_timeout': 60,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'keepvideo': False,
        'writethumbnail': False,
        'writesubtitles': False,
        'writeautomaticsub': False,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'logger': MyLogger(),
        
        # Enhanced headers to mimic a real browser
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        },
        
        # Add some delay between requests to avoid rate limiting
        'sleep_interval': 2,
        'max_sleep_interval': 5,
        
        # Postprocessors for better format handling
        'postprocessors': [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            },
            {
                'key': 'FFmpegMetadata',
            }
        ],
    }
    
    return options

@app.route('/download', methods=['POST'])
def download_video():
    temp_dir = None
    try:
        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Please provide a URL'}), 400

        # Check if it's a TikTok URL
        if not ('tiktok.com' in url.lower() or 'tiktokv.com' in url.lower()):
            return jsonify({'error': 'This endpoint is specifically for TikTok videos. Please provide a valid TikTok URL.'}), 400

        logger.info(f"Attempting to download TikTok video from URL: {url}")

        # Check system requirements first
        ffmpeg_available = check_ffmpeg()
        logger.info(f"FFmpeg available: {ffmpeg_available}")
        
        # Optionally update yt-dlp (disabled by default for performance). Enable by setting AUTO_UPDATE_YTDLP=true
        if os.environ.get('AUTO_UPDATE_YTDLP', 'false').lower() in ['1', 'true', 'yes']:
            logger.info("Updating yt-dlp to latest version...")
            update_ytdlp()

        # Create a temporary directory for downloads
        temp_dir = tempfile.mkdtemp()
        logger.debug(f"Created temp directory: {temp_dir}")
        
        # Get TikTok-specific options
        ydl_opts = get_tiktok_options(url)
        ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(id)s.%(ext)s')

        # Harden headers and avoid brittle extractor overrides
        ydl_opts.pop('extractor_args', None)
        headers = ydl_opts.get('http_headers', {})
        headers.setdefault('Referer', 'https://www.tiktok.com/')
        headers.setdefault('Origin', 'https://www.tiktok.com')
        ydl_opts['http_headers'] = headers

        # Ensure ffmpeg is available; if not, attempt install and then gracefully degrade
        if not check_ffmpeg():
            try:
                install_ffmpeg()
            except Exception:
                pass
        
        # If ffmpeg.exe exists in current dir, point yt-dlp to it
        ffmpeg_exe_path = os.path.join(os.getcwd(), 'ffmpeg.exe')
        if os.path.exists(ffmpeg_exe_path):
            ydl_opts['ffmpeg_location'] = ffmpeg_exe_path
        
        # Also detect system ffmpeg/ffprobe via PATH
        ffmpeg_system_path = shutil.which('ffmpeg')
        ffprobe_system_path = shutil.which('ffprobe')
        if ffmpeg_system_path and not ydl_opts.get('ffmpeg_location'):
            # Provide directory so yt-dlp can find both ffmpeg and ffprobe
            ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_system_path)
        
        # If ffprobe is not available, avoid postprocessing/merging that requires it
        ffprobe_local_exe = os.path.join(os.getcwd(), 'ffprobe.exe')
        if not (ffprobe_system_path or os.path.exists(ffprobe_local_exe)):
            ydl_opts.pop('postprocessors', None)
            ydl_opts.pop('merge_output_format', None)
            ydl_opts['format'] = 'best[ext=mp4][protocol!=m3u8]/best[protocol!=m3u8]/best'
        
        # Add some delay before making requests
        time.sleep(1)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Get video info first with retry logic
                logger.info("Extracting video information...")
                max_retries = 4
                info = None
                
                for attempt in range(max_retries):
                    try:
                        info = ydl.extract_info(url, download=False)
                        break
                    except yt_dlp.utils.DownloadError as e:
                        error_msg = str(e).lower()
                        if "unable to extract" in error_msg and "json" in error_msg:
                            logger.warning(f"Attempt {attempt + 1} failed: JSON extraction error. Retrying...")
                            if attempt < max_retries - 1:
                                time.sleep(5 * (attempt + 1))  # Exponential backoff
                                continue
                        raise e
                
                # Validate info object
                if not info:
                    logger.error("No video information extracted")
                    return jsonify({'error': 'Could not extract video information. The TikTok video might be private, deleted, or region-locked.'}), 400
                
                if not isinstance(info, dict):
                    logger.error(f"Info object is not a dictionary, got: {type(info)}")
                    return jsonify({'error': 'Invalid video information format'}), 400

                # Debug available formats
                if 'formats' in info:
                    formats = info['formats']
                    logger.info(f"Available formats: {len(formats)}")
                    for fmt in formats[:3]:  # Log first 3 formats
                        logger.info(f"Format: {fmt.get('format_id')} - {fmt.get('ext')} - {fmt.get('resolution')} - {fmt.get('vcodec')} - {fmt.get('acodec')}")

                # Extract basic video information safely
                video_id = info.get('id', str(uuid.uuid4())[:8])
                
                # Try to get the description/title for filename
                raw_title = info.get('title', '') or info.get('description', '') or f'tiktok_{video_id}'
                video_title = sanitize_filename(raw_title)
                if not video_title:
                    video_title = f'tiktok_{video_id}'
                
                logger.info(f"Raw title: {raw_title}")
                logger.info(f"Cleaned title: {video_title}")
                logger.info(f"Video ID: {video_id}")
                
                # Download the video with retry logic
                logger.info("Starting video download...")
                download_success = False
                
                for attempt in range(max_retries):
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as download_ydl:
                            download_info = download_ydl.extract_info(url, download=True)
                        download_success = True
                        break
                    except yt_dlp.utils.DownloadError as e:
                        error_msg = str(e).lower()
                        if ("unable to extract" in error_msg or "postprocessing: ffmpeg not found" in error_msg) and attempt < max_retries - 1:
                            logger.warning(f"Download attempt {attempt + 1} failed. Retrying...")
                            time.sleep(5 * (attempt + 1))
                            continue
                        raise e
                
                if not download_success:
                    return jsonify({'error': 'Failed to download video after multiple attempts'}), 500
                
                if not download_info or not isinstance(download_info, dict):
                    logger.error(f"Invalid download info: {type(download_info)}")
                    # As a fallback, attempt bestaudio+bestvideo merge or direct URL
                    try:
                        with yt_dlp.YoutubeDL({**ydl_opts, 'format': 'bv*+ba/b'}) as fallback_ydl:
                            download_info = fallback_ydl.extract_info(url, download=True)
                    except Exception as _:
                        return jsonify({'error': 'Failed to download video'}), 500

                # Find the downloaded file
                downloaded_files = [f for f in os.listdir(temp_dir) 
                                  if os.path.isfile(os.path.join(temp_dir, f)) and 
                                  (f.endswith('.mp4') or f.endswith('.m4v') or f.endswith('.mov') or f.endswith('.webm'))]
                
                if not downloaded_files:
                    logger.error(f"No downloaded files found in {temp_dir}")
                    all_files = os.listdir(temp_dir)
                    logger.error(f"All files in temp dir: {all_files}")
                    return jsonify({'error': 'Video downloaded but file not found. The video might be private or unavailable.'}), 500
                
                # Get the downloaded file
                downloaded_file_path = os.path.join(temp_dir, downloaded_files[0])
                logger.info(f"Using file: {downloaded_files[0]}")
                
                # Verify file size
                file_size = os.path.getsize(downloaded_file_path)
                if file_size < 1024:  # Less than 1KB
                    logger.error(f"Downloaded file is too small: {file_size} bytes")
                    return jsonify({'error': 'Downloaded file appears to be corrupted or empty'}), 500
                
                logger.info(f"Downloaded file size: {file_size} bytes")
                
                # Determine actual extension and MIME type
                actual_ext = os.path.splitext(downloaded_files[0])[1].lstrip('.').lower()
                mime_map = {
                    'mp4': 'video/mp4',
                    'm4v': 'video/x-m4v',
                    'mov': 'video/quicktime',
                    'webm': 'video/webm'
                }
                chosen_mime = mime_map.get(actual_ext, 'application/octet-stream')
                
                # Create a response with the file
                response = send_file(
                    downloaded_file_path,
                    as_attachment=True,
                    download_name=f"{video_title}.{actual_ext}",
                    mimetype=chosen_mime
                )
                
                # Set the Content-Disposition header directly
                safe_filename = f"{video_title}.{actual_ext}".replace('"', '\\"')  # Escape quotes
                response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}"; filename*=UTF-8''{safe_filename}'
                
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
                
                # Check for specific TikTok errors
                if "Unable to extract" in error_msg and "json" in error_msg.lower():
                    return jsonify({'error': 'TikTok blocked the request. This may be due to rate limiting or anti-bot measures. Please try again later or check if the video is publicly accessible.'}), 429
                elif "Private video" in error_msg or "private" in error_msg.lower():
                    return jsonify({'error': 'This TikTok video is private and cannot be downloaded.'}), 400
                elif "Video unavailable" in error_msg or "unavailable" in error_msg.lower():
                    return jsonify({'error': 'This TikTok video is unavailable or has been removed.'}), 400
                elif "getaddrinfo failed" in error_msg or "name or service not known" in error_msg.lower():
                    return jsonify({'error': 'Network connection error. Please check your internet connection.'}), 500
                elif "403" in error_msg or "http error 403" in error_msg.lower():
                    return jsonify({'error': 'TikTok is blocking requests (HTTP 403). Please try again later.'}), 429
                elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    return jsonify({'error': 'Request timed out. TikTok may be rate-limiting. Please try again shortly.'}), 408
                else:
                    return jsonify({'error': f'TikTok download failed: {error_msg}'}), 500
                    
            except Exception as e:
                logger.error(f"Unexpected error during download: {str(e)}")
                return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

    except Exception as e:
        import traceback
        logger.error(f"Top-level error: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500
    finally:
        # Cleanup temp directory if it still exists
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    ffmpeg_status = check_ffmpeg()
    return jsonify({
        'status': 'ok', 
        'message': 'TikTok downloader is running',
        'ffmpeg_available': ffmpeg_status,
        'python_version': sys.version
    })

@app.route('/debug-formats', methods=['POST'])
def debug_video_formats():
    """Debug endpoint to check available formats for a URL"""
    try:
        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Please provide a URL'}), 400
        
        # Update yt-dlp first
        update_ytdlp()
        
        opts = get_tiktok_options(url)
        opts['listformats'] = True
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
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
            return jsonify({'formats': formats, 'title': info.get('title', 'Unknown')})
        else:
            return jsonify({'error': 'Could not extract format information'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Debug error: {str(e)}'}), 500

@app.route('/update-ytdlp', methods=['POST'])
def update_ytdlp_endpoint():
    """Endpoint to manually update yt-dlp"""
    try:
        success = update_ytdlp()
        if success:
            return jsonify({'message': 'yt-dlp updated successfully'})
        else:
            return jsonify({'error': 'Failed to update yt-dlp'}), 500
    except Exception as e:
        return jsonify({'error': f'Update error: {str(e)}'}), 500

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
    app.run(debug=debug_mode, port=5000, host='0.0.0.0')