# Video Downloader Web App

A simple web application that allows users to download high-quality videos using yt-dlp.

## Features

- Clean and modern user interface
- Downloads highest quality video available
- Supports multiple video platforms
- Real-time download status updates
- Automatic file naming

## Setup

1. Install Python 3.7 or higher
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. Start the Flask server:
   ```bash
   python app.py
   ```
2. Open your web browser and navigate to `http://localhost:5000`

## Usage

1. Enter the URL of the video you want to download
2. Click the "Download" button
3. Wait for the download to complete
4. The video will be automatically saved to your downloads folder

## Supported Platforms

This application supports all platforms that yt-dlp supports, including:
- YouTube
- Vimeo
- Dailymotion
- And many more

## Note

Please ensure you have the right to download the videos you're accessing and comply with the terms of service of the respective platforms. 