# Asterisk Tournament System

A tournament management and live streaming system built for esports events. Handles team registration, match scheduling, live scoring, and HLS streaming with interactive overlays.

## Features

- Tournament bracket management
- Live match streaming with custom overlays
- Real-time match scoring and updates
- Team registration and management
- Pause screen with team statistics
- WhatsApp notifications integration
- MongoDB and SQLite data persistence


## Screenshots

### Tournament Control Panel
![Tournament Control](screenshots/Screenshot 2025-10-24 005142.png)

### Live Stream with Overlay
![Live Stream](screenshots/Screenshot 2025-10-24 005210.png)


## System Requirements

- Python 3.8+
- FFmpeg for streaming
- MongoDB database
- Node.js (for WhatsApp service)

## Setup

1. Clone the repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```bash
   cp sample.env .env
   # Edit .env with your configuration
   ```
4. Start the WhatsApp notification service:
   ```bash
   cd notification-whatsapp
   go run main.go
   ```
5. Run the main server:
   ```bash
   python app.py
   ```
6. Start the HLS stream server:
   ```bash
   python live.py
   ```

## Architecture

- Main server (`app.py`): Tournament logic, API endpoints
- Stream server (`live.py`): HLS video streaming
- WhatsApp service: Real-time notifications
- Frontend: HTML/JS for control panels and overlays

## Screenshots

### Tournament Control Panel
![Tournament Control](screenshots/control.jpg)

### Live Stream with Overlay
![Live Stream](screenshots/live.jpg)

## License

MIT

## Acknowledgments

- ACM AJCE for project support
- All participating teams and organizers