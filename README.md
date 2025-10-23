# ⚡ ASTERISK # 🎮 ASTERISK - Tournament Management Platform# 🎮 ASTERISK - Tournament Management Platform



> **Live Esports Tournament Platform** — Built for Aithra 2025  

> 🌐 [**astrisk.vercel.app**](https://astrisk.vercel.app)

> **Live Site:** [astrisk.vercel.app](https://astrisk.vercel.app)**ASTERISK** is a comprehensive esports tournament management system built for **Aithra Techfest 2025**, organized by the ACM Student Chapter at Amal Jyothi College of Engineering (AJCE). This platform powers the complete lifecycle of competitive gaming tournaments—from team registration and match scheduling to live streaming and real-time score updates.

A comprehensive real-time tournament management system for competitive Valorant esports, featuring live streaming, dynamic bracket management, team registration, and audience engagement tools.



---

**ASTERISK** is a comprehensive esports tournament management system built for **Aithra Techfest 2025**, organized by the ACM Student Chapter at Amal Jyothi College of Engineering (AJCE). This platform powers competitive gaming tournaments with team registration, live streaming, and real-time match management.---

## 🎯 Features

## 📸 Screenshots

### 🏆 Tournament Management

- **Real-Time Bracket System** — Dynamic tournament progression with automatic winner advancement### Landing Page & Event Information**Event Details:**

- **Live Match Control** — Set active matches, update scores, and broadcast results instantly

- **Best Loser Calculation** — Intelligent wildcard selection based on performance metrics![Landing Page](screenshots/landing.png)- **Host:** ACM Student Chapter, Amal Jyothi College of Engineering

- **Multi-Round Support** — Round of 16 → Quarterfinals → Semifinals → Finals

*Main event page with tournament details, countdown timer, and team qualifiers showcase*- **Festival:** Aithra Techfest 2025

### 👥 Team Registration

- **Smart Registration** — Email validation, duplicate detection, and SQLite backup- **Primary Game:** Valorant (The Reckoning Tournament)

- **Open Team System** — Allow players to request joining existing teams

- **WhatsApp Notifications** — Automated team updates and join request alerts### Team Registration & Dashboard- **Prize Pool:** ₹40,000+

- **Team Dashboard** — Manage roster, view match schedule, and respond to requests

![Team Registration](screenshots/registration.png)- **Format:** LAN Finals with live streaming

### 📺 Live Streaming

- **HLS Streaming** — FFmpeg-powered video delivery with adaptive bitrate*Secure team registration with validation and WhatsApp notifications*

- **Real-Time Overlays** — Match scoreboards, team info, and animated transitions

- **Pause Screen** — Display team statistics and tournament standings during breaks---

- **SSE Updates** — Server-Sent Events for instant UI synchronization across all viewers

![Team Dashboard](screenshots/dashboard.png)

### 🎮 Viewer Experience

- **Live Match Feed** — Real-time score updates and match progression*Manage team roster, accept join requests, and view match schedules*## ✨ Platform Features

- **Viewer Counter** — Track concurrent audience engagement

- **Interactive UI** — Responsive design with TailwindCSS and smooth animations



---### Live Tournament Bracket### 🎯 Team Registration & Management



## 🖼️ Screenshots![Tournament Bracket](screenshots/bracket.png)- **Team Registration** - Secure registration with unique team auth codes



### 🏠 Landing Page*Real-time tournament bracket with match status and advancement tracking*- **Team Dashboard** - Manage team members, view match schedules, payment status

![Landing Page](screenshots/landing.png)

*Tournament homepage with event details and registration call-to-action*- **Open Team System** - Allow incomplete teams to accept join requests from solo players



### 📝 Team Registration### Live Streaming & Controls- **Email & Phone Validation** - Prevent duplicate registrations

![Team Registration](screenshots/registration.png)

*Intuitive registration form with real-time validation and duplicate checks*![Live Stream](screenshots/livestream.png)- 



### 🎯 Live Match Dashboard**Payment Tracking** - MongoDB-backed payment status management

![Match Dashboard](screenshots/dashboard.png)

*Control panel for managing active matches, updating scores, and advancing rounds**Professional HLS live stream with dynamic overlays and real-time score updates*- **SQLite Backup** - Automatic fallback database for data redundancy



### 📺 Live Stream View- **WhatsApp Integration** - Automated notifications for registration, payment, and team updates

![Live Stream](screenshots/livestream.png)

*Viewer-facing stream page with real-time scoreboard overlays and match information**Admin control panel for managing stream overlays, scores, and match animations*### 📊 Tournament Bracket System



---- **Round of 16/18 Support** - Flexible bracket configuration with best loser advancement



## 🛠️ Tech Stack---- **Real-time Match Updates** - Live score tracking with SSE (Server-Sent Events)



**Backend**- **Dynamic Seeding** - Automatic seed calculation and match pairing

- Python 3.13+ with `aiohttp` (async web server)

- MongoDB Atlas with `Motor` (async ODM)## ✨ Key Features- **Multi-Court Management** - Schedule matches across multiple gaming stations

- SQLite (backup database)

- **Match Status Tracking** - Pending, Live, Completed states with timestamps

**Frontend**

- HTML5, CSS3, TailwindCSS### 🎯 Team Management- **Tournament Stats Dashboard** - View advancement status, team statistics, and eliminated teams

- Vanilla JavaScript with Server-Sent Events (SSE)

- HLS.js for video playback- **Secure Registration** - Unique team auth codes with email/phone validation



**Streaming**- **Team Dashboard** - Manage members, accept join requests, track payment status### 📺 Live Streaming Infrastructure

- FFmpeg for HLS encoding

- Custom live server (`live.py`) on port 5001- **Open Team System** - Solo players can request to join incomplete teams- **HLS Live Streaming** - Low-latency HTTP Live Streaming with FFmpeg integration



**Integrations**- **WhatsApp Integration** - Automated notifications for all team activities- **Real-time Score Overlays** - Dynamic team names, scores, map info, and round counters

- WhatsApp notifications via Go service (`whatsmeow`)

- Real-time event broadcasting with SSE- **Match Animations** - Professional match start/end transitions



**Deployment**### 📊 Tournament System- **Pause Screen** - Display team standings and tournament stats during breaks

- Vercel (frontend hosting)

- Custom backend server- **Flexible Brackets** - Support for Round of 16/18 with best loser advancement- **Viewer Chat** - Real-time chat with auto-hide for clean viewing experience



---- **Real-time Updates** - Live score tracking with Server-Sent Events (SSE)- **SSE Broadcasting** - Instant updates pushed to all connected viewers



## 🚀 Quick Start- **Multi-Court Management** - Schedule concurrent matches across gaming stations- **Mobile Responsive** - Touch-optimized controls with auto-hide UI



### Prerequisites- **Admin Controls** - Easy match management and winner selection

```bash

python 3.13+### 🎛️ Admin Control Panel

ffmpeg

go 1.18+ (for WhatsApp service)### 📺 Live Streaming- **Stream Control** - Update team info, scores, and match details in real-time

mongodb atlas account

```- **HLS Streaming** - Low-latency live streaming with FFmpeg- **Broadcast Triggers** - Launch match start/end animations for all viewers



### Installation- **Dynamic Overlays** - Real-time team names, scores, maps, and round info- **Team Stats Management** - Update win/loss records and tournament points



1. **Clone the repository**- **Professional Animations** - Match start/end transitions- **Ingress Server Config** - Configure HLS stream source dynamically

```bash

git clone <repository-url>- **Pause Screen** - Display tournament stats during breaks- **Multi-Match View** - Manage multiple concurrent matches across courts

cd Asterisk

```- **Mobile Optimized** - Touch controls with auto-hide UI



2. **Install Python dependencies**### 🔐 Security & Authentication

```bash

pip install -r requirements.txt---- **Master Password System** - Admin access control (default: `0022`)

```

- **Team Auth Codes** - 4-digit unique codes for team lead dashboard access

3. **Configure environment**

```bash## 🏗️ Technology Stack- **Rate Limiting** - Prevent abuse with request throttling

cp sample.env .env

# Edit .env with your MongoDB Atlas URI- **CORS Configuration** - Secure cross-origin resource sharing

```

**Backend:**- **Input Validation** - Comprehensive email, phone, and team name validation

4. **Build WhatsApp service** (optional)

```bash- Python 3.13+ (Flask & aiohttp)

cd notification-whatsapp

go build -o main.exe- MongoDB Atlas---

cd ..

```- Motor (Async MongoDB)



### Running the Application- SQLite (Backup)## 🏗️ Technology Stack



1. **Start the main server**

```bash

python app.py**Frontend:**### Backend

```

Server runs on `http://localhost:8080`- HTML5 + TailwindCSS- **Python 3.13+** - Core application runtime



2. **Start the HLS live server**- HLS.js- **Flask** - Traditional REST API server (`app.py`)

```bash

python live.py- Server-Sent Events- **aiohttp** - Async server with SSE support (`app_aiohttp.py`)

```

HLS server runs on `http://localhost:5001`- **MongoDB Atlas** - Primary database for registrations and matches



3. **Start WhatsApp service** (optional)**Infrastructure:**- **Motor** - Async MongoDB driver

```bash

cd notification-whatsapp- FFmpeg (Video encoding)- **SQLite** - Backup/fallback database

./main.exe

```- Go (WhatsApp service)- **WhatsApp API** - Notification service via WhatsApp Web (Go integration)

WhatsApp service runs on `http://localhost:4005`

- Vercel (Hosting)

### Access Points

- **Homepage**: `http://localhost:8080/`### Frontend

- **Registration**: `http://localhost:8080/registration.html`

- **Team Dashboard**: `http://localhost:8080/team.html`---- **HTML5 + TailwindCSS** - Modern, responsive UI

- **Match Control**: `http://localhost:8080/control.html`

- **Live Stream**: `http://localhost:8080/live.html`- **Valorant Font** - Official Riot Games typography

- **Stream Control**: `http://localhost:8080/stream-control.html`

## 🚀 Quick Start- **HLS.js** - JavaScript HLS player for live streams

---

- **SSE (EventSource)** - Real-time server-to-client updates

## 📁 Project Structure

### Prerequisites- **Iconify** - Vector icons for UI elements

```

Asterisk/

├── app.py                      # Main async web server (aiohttp)

├── live.py                     # HLS streaming server- Python 3.13+### Infrastructure

├── requirements.txt            # Python dependencies

├── sample.env                  # Environment template- FFmpeg- **FFmpeg** - Video encoding and HLS stream generation

├── ffmpeg/                     # FFmpeg binaries

├── templates/                  # HTML pages- MongoDB Atlas account- **Go (WhatsApp Service)** - WhatsApp message delivery (`main.go`)

│   ├── index.html             # Landing page

│   ├── reg.html               # Registration form- Go 1.18+ (optional, for WhatsApp)- **Vercel** - Production deployment platform

│   ├── team.html              # Team dashboard

│   ├── control.html           # Match control panel

│   ├── live.html              # Live stream viewer

│   └── stream-control.html    # Stream overlay controls### Installation---

├── notification-whatsapp/      # Go WhatsApp service

│   ├── main.go

│   └── go.mod

└── screenshots/                # Demo images```bash## 📁 Project Structure

```

# Clone repository

---

git clone <repository-url>```

## 🔐 Admin Authentication

cd AsteriskAsterisk/

Protected endpoints require the `X-Auth-Token` header:

```javascript├── app.py                      # Flask REST API server (team registration, payment)

headers: {

  'X-Auth-Token': 'YOUR_MASTER_PASSWORD'# Install dependencies├── app_aiohttp.py              # Async server (matches, SSE, live streaming)

}

```pip install -r requirements.txt├── live.py                     # HLS file server (serves .m3u8 and .ts files)



Set `MASTER_PASSWORD` in your environment (default: `0022`).├── main.go                     # WhatsApp notification service



---# Configure environment├── reset_matches.py            # Tournament bracket initialization utility



## 🌐 API Endpointscp sample.env .env├── requirements.txt            # Python dependencies



### Match Management# Edit .env with your MongoDB URI├── sample.env                  # Environment variables template

- `GET /api/matches` — Fetch all matches

- `POST /api/matches` — Create new match (admin)├── registrations_backup.db     # SQLite backup database

- `PUT /api/matches/{id}` — Update match (admin)

- `DELETE /api/matches/{id}` — Delete match (admin)# Initialize database├── RuleBook.pdf                # Official tournament rules

- `POST /api/matches/set-active` — Set active match (admin)

- `POST /api/matches/set-winner` — Declare match winner (admin)python reset_matches.py├── templates/                  # HTML templates



### Tournament Control```│   ├── index.html              # Landing page with event info

- `POST /api/tournament/initialize` — Reset bracket (admin)

- `POST /api/tournament/advance-winners` — Progress to next round (admin)│   ├── reg.html                # Team registration form

- `GET /api/tournament/stats` — Get tournament statistics

- `GET /api/tournament/advancement-status` — Check progression status### Running the Platform│   ├── team.html               # Team dashboard (manage roster)

- `GET /api/tournament/best-loser` — Calculate wildcard team

│   ├── teams.html              # Public team listing (admin view)

### Live Streaming

- `GET /api/stream/state` — Get current match state```bash│   ├── live.html               # Live stream viewer page

- `POST /api/stream/score` — Update scores

- `POST /api/stream/teams` — Update team names# Terminal 1: Main API server│   ├── control.html            # Stream control panel

- `POST /api/stream/match-info` — Update match details

- `POST /api/stream/match-start` — Trigger start animationpython app_aiohttp.py│   ├── stream-control-new.html # Enhanced admin controls

- `POST /api/stream/match-end` — Trigger end overlay

│   ├── matchlineup.html        # Tournament bracket visualization

### Real-Time Events

- `GET /events` — SSE for match updates# Terminal 2: HLS file server│   ├── game.html               # Game rules and guidelines

- `GET /stream/events` — SSE for stream viewers

python live.py│   └── lead.html               # Team lead management

---

└── notification-whatsapp/      # WhatsApp integration module

## 📊 Database Schema

# Terminal 3: WhatsApp service (optional)    └── main.go                 # Go WhatsApp service

### Registrations Collection

```javascript./main.exe```

{

  registration_id: String,```

  team_name: String (unique),

  college_name: String,---

  lead: { name, email, contact },

  members: [{ name, email, riot_id }],### Access Points

  substitute: { name, email, riot_id },

  payment_status: String,## 🚀 Quick Start

  timestamp: DateTime,

  ip_address: String- **Landing Page:** http://localhost:5002/

}

```- **Registration:** http://localhost:5002/reg.html### Prerequisites



### Matches Collection- **Team Dashboard:** http://localhost:5002/team.html

```javascript

{- **Admin Panel:** http://localhost:5002/teams.html- **Python 3.13+** - [Download Python](https://www.python.org/downloads/)

  round: String,

  round_number: Number,- **Live Stream:** http://localhost:5002/live.html- **FFmpeg** - For live streaming: `winget install Gyan.FFmpeg` (Windows)

  match_number: Number,

  team1: String,- **Stream Control:** http://localhost:5002/control.html- **Go 1.18+** - For WhatsApp service: [Download Go](https://go.dev/dl/)

  team2: String,

  team1_seed: Number,- **Bracket:** http://localhost:5002/matchlineup.html- **MongoDB Atlas Account** - Free tier sufficient

  team2_seed: Number,

  team1_score: Number,

  team2_score: Number,

  winner: String,---### Installation

  status: String, // "pending", "live", "completed"

  is_active: Boolean,

  created_at: DateTime,

  updated_at: DateTime## 🎯 Usage1. **Clone the repository**

}

```   ```bash



---### For Organizers   git clone <repository-url>



## 🎨 Customization   cd Asterisk



### Branding1. **Configure** - Set admin password in `app_aiohttp.py`   ```

Edit template files in `templates/` to customize:

- Tournament name and logo2. **Initialize** - Run `python reset_matches.py` with team lineup

- Color schemes (TailwindCSS classes)

- Overlay animations and styles3. **Launch** - Start all three services2. **Install Python dependencies**



### WhatsApp Messages4. **Manage** - Use control panel to update matches and stream   ```bash

Modify message templates in `app.py`:

```python   pip install -r requirements.txt

def build_whatsapp_message(event: str, **kwargs) -> str:

    # Customize notification content here### For Teams   ```

```



### Stream Overlays

Update stream state defaults in `app.py`:1. **Register** - Complete registration form3. **Configure environment variables**

```python

stream_state = {2. **Save Code** - Receive 4-digit auth code via WhatsApp   ```bash

    "matchTitle": "YOUR EVENT NAME",

    "map": "DEFAULT_MAP",3. **Dashboard** - Use code to access team management   cp sample.env .env

    # ... other defaults

}4. **Payment** - Complete registration fee   # Edit .env and add your MongoDB connection string

```

   ```

---

### For Viewers

## 🐛 Troubleshooting

4. **Initialize the database**

**MongoDB Connection Issues**

- Verify `MONGODB_URL` in `.env`1. **Watch** - Visit live stream during matches   ```bash

- Check network connectivity and firewall settings

- Ensure IP is whitelisted in MongoDB Atlas2. **Interact** - Use real-time chat   python reset_matches.py



**WhatsApp Service Not Working**3. **Mobile** - Tap to show/hide controls   ```

- Verify Go service is running on port 4005

- Check phone number format (must be Indian 10-digit)

- Review logs in `notification-whatsapp/` directory

---5. **Build WhatsApp service** (optional, for notifications)

**Stream Not Loading**

- Ensure FFmpeg is properly installed   ```bash

- Verify `live.py` is running on port 5001

- Check ingress server URL is configured correctly## 🔧 Configuration   cd notification-whatsapp



**Type Checking Errors**   go build -o ../main.exe main.go

- Project uses Python 3.13+ type hints

- Run `pip install --upgrade motor pymongo aiohttp`### Environment Variables   cd ..



---   ```



## 📜 License```env



This project is built for **Aithra 2025** by **ACM AJCE**.MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/### Running the Platform



---```



## 🤝 Contributing**Option 1: Full Stack (Production)**



This is a tournament-specific project. For feature requests or bug reports, please contact the event organizers.### Admin Password```bash



---# Terminal 1: Main API server



## 📞 SupportEdit `app_aiohttp.py`:python app_aiohttp.py



For technical issues or questions:```python

- **Event**: Aithra 2025

- **Organization**: ACM, Amal Jyothi College of EngineeringMASTER_PASSWORD = "0022"  # Change this# Terminal 2: HLS file server



---```python live.py



<div align="center">



**Built with ⚡ for competitive esports**### FFmpeg Streaming# Terminal 3: WhatsApp service (optional)



[Live Site](https://astrisk.vercel.app) • [Report Bug](#) • [Request Feature](#)./main.exe



</div>```bash```


ffmpeg -f gdigrab -framerate 60 -i desktop \

  -c:v libx264 -preset ultrafast -b:v 8000k \**Option 2: Development Mode**

  -c:a aac -b:a 192k -pix_fmt yuv420p \```bash

  -f hls -hls_time 2 -hls_list_size 6 \# Flask dev server (simpler, no SSE)

  -hls_flags delete_segments+append_list \python app.py

  -hls_segment_filename "hls/stream_%03d.ts" \```

  "hls/stream.m3u8"

```### Access Points



---- **Landing Page:** http://localhost:5002/

- **Team Registration:** http://localhost:5002/reg.html

## 🛡️ Security- **Team Dashboard:** http://localhost:5002/team.html

- **Admin Panel:** http://localhost:5002/teams.html

- Change default admin password before deployment- **Live Stream:** http://localhost:5002/live.html

- Use HTTPS in production (Vercel provides this)- **Stream Control:** http://localhost:5002/control.html

- Restrict CORS origins for production- **Tournament Bracket:** http://localhost:5002/matchlineup.html

- Backup MongoDB regularly

- Keep WhatsApp session secure---



---## 🎯 Usage Guide



## 🐛 Troubleshooting### For Tournament Organizers



**MongoDB Connection Issues:**1. **Set Admin Password** - Change `MASTER_PASSWORD = "0022"` in `app.py`/`app_aiohttp.py`

```bash2. **Initialize Bracket** - Run `python reset_matches.py` with your team lineup

python -c "from pymongo import MongoClient; MongoClient('your_uri').server_info()"3. **Start Servers** - Launch all three services (API, HLS, WhatsApp)

```4. **Open Stream Control** - Navigate to `/control.html` to manage live stream

5. **Update Matches** - Use `/matchlineup.html` to set active matches and record winners

**WhatsApp Not Working:**

- Ensure `main.exe` is running### For Teams

- Re-authenticate by deleting `examplestore.db`

- Check phone format: `91XXXXXXXXXX`1. **Register Team** - Visit `/reg.html` and complete registration form

2. **Save Auth Code** - Receive 4-digit code via WhatsApp (keep secure!)

**Stream Not Loading:**3. **Access Dashboard** - Use auth code on `/team.html` to manage roster

- Verify HLS files in `hls/` directory4. **Accept Join Requests** - Review and approve solo players joining your open team

- Check FFmpeg is generating segments5. **Complete Payment** - Pay registration fee (status updated by admin)

- Inspect browser console for errors

### For Viewers

---

1. **Visit Live Stream** - Go to `/live.html` during match times

## 🤝 Contributing2. **Enjoy Real-time Updates** - Scores and match info update automatically

3. **Participate in Chat** - Send messages visible to all viewers

Built for Aithra 2025 but adaptable for any esports tournament. Contributions welcome!4. **Mobile Viewing** - Tap screen to show/hide controls



1. Fork the repository---

2. Create feature branch

3. Commit changes## 🔧 Configuration

4. Push and open Pull Request

### Environment Variables (`.env`)

---

```env

## 📄 LicenseMONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/

```

MIT License - Free to use and modify with attribution.

### Admin Password

---

Edit `app.py` or `app_aiohttp.py`:

## 🎓 Credits```python

MASTER_PASSWORD = "0022"  # Change to your secure password

**Developed by:** ACM Student Chapter, Amal Jyothi College of Engineering  ```

**Event:** Aithra Techfest 2025  

**Technical Lead:** Amarnath  ### WhatsApp Configuration



**Special Thanks:**1. Run `main.exe` for first-time setup

- ACM AJCE Core Team2. Scan QR code with WhatsApp mobile app

- Aithra 2025 Organizing Committee3. Session persists in `examplestore.db`

- All participating teams

### FFmpeg HLS Streaming

---

```bash

## 📞 Support# Capture desktop (Windows)

ffmpeg -f gdigrab -framerate 60 -i desktop ^

- **Email:** acm@ajce.in  -c:v libx264 -preset ultrafast -b:v 8000k ^

- **Website:** [astrisk.vercel.app](https://astrisk.vercel.app)  -c:a aac -b:a 192k -pix_fmt yuv420p ^

  -f hls -hls_time 2 -hls_list_size 6 ^

---  -hls_flags delete_segments+append_list ^

  -hls_segment_filename "hls\stream_%03d.ts" ^

**Built with ❤️ for the gaming community at AJCE**  "hls\stream.m3u8"

```

---

## 📡 API Reference

### Registration Endpoints

- `POST /register` - Register new team
- `POST /create-team` - Create open team (incomplete roster)
- `POST /team/join-request` - Submit join request to open team
- `POST /team/respond-join` - Accept/decline join request
- `POST /update-payment` - Update payment status (admin)
- `GET /teams` - List all registered teams

### Match Management

- `GET /api/matches` - Get all tournament matches
- `POST /api/matches` - Create new match (admin)
- `PUT /api/matches/{id}` - Update match details (admin)
- `DELETE /api/matches/{id}` - Delete match (admin)
- `POST /api/matches/set-active` - Set currently broadcasting match
- `POST /api/matches/set-winner` - Record match result
- `POST /api/matches/advance-winners` - Generate next round bracket
- `GET /api/tournament/stats` - Tournament statistics
- `GET /api/tournament/advancement` - Advancement status with best loser

### Live Streaming

- `GET /api/stream/state` - Current match state
- `POST /api/stream/update-score` - Update team score
- `POST /api/stream/update-teams` - Update team names
- `POST /api/stream/update-match-info` - Update map/round info
- `POST /api/stream/trigger-start` - Broadcast match start animation
- `POST /api/stream/trigger-end` - Broadcast match end overlay
- `GET /api/stream/events` - SSE endpoint for real-time updates
- `POST /api/stream/send-chat` - Send chat message
- `GET /api/stream/viewer-count` - Active viewer count

### Team Stats

- `GET /api/team-stats` - Get all team statistics
- `POST /api/team-stats` - Update team stats (admin)
- `DELETE /api/team-stats` - Delete team stats (admin)
- `POST /api/pause-screen/toggle` - Show/hide pause screen

---

## 🛡️ Security Considerations

- Change default `MASTER_PASSWORD` before production deployment
- Use HTTPS in production (Vercel handles this automatically)
- Restrict CORS origins in production environment
- Regularly backup MongoDB database
- Keep WhatsApp session secure (`examplestore.db`)
- Validate and sanitize all user inputs (already implemented)

---

## 🐛 Troubleshooting

### MongoDB Connection Issues
```bash
# Test connection string
python -c "from pymongo import MongoClient; MongoClient('your_uri').server_info()"
```

### WhatsApp Not Sending Messages
- Ensure `main.exe` is running
- Re-authenticate by deleting `examplestore.db` and scanning QR again
- Check phone number format: should be `91XXXXXXXXXX` (India)

### Stream Not Loading
- Verify HLS files exist in `hls/` directory
- Check FFmpeg process is active and generating segments
- Inspect browser console for CORS or network errors

### Port Already in Use
```bash
# Change ports in respective files:
# app.py: port=5002
# live.py: port=5001
# main.go: ":4005"
```

---

## 📊 Database Schema

### Registrations Collection (MongoDB)
```javascript
{
  _id: ObjectId,
  team_name: String (unique),
  college_name: String,
  lead: {
    name: String,
    email: String (unique),
    contact: String (10 digits)
  },
  members: Array<{
    name: String,
    email: String (unique),
    contact: String
  }>,
  substitute: Object (optional),
  team_auth_code: String (4-digit, unique),
  registration_id: String,
  payment_status: "pending" | "completed",
  is_open: Boolean,
  join_requests: Array<{
    name: String,
    email: String,
    contact: String,
    riot_id: String,
    status: "pending" | "accepted" | "declined",
    timestamp: Date
  }>,
  timestamp: Date
}
```

### Matches Collection (MongoDB)
```javascript
{
  _id: ObjectId,
  round: String ("Round of 16", "Quarterfinals", etc.),
  round_number: Number,
  match_number: Number,
  team1: String,
  team2: String,
  team1_seed: Number,
  team2_seed: Number,
  team1_score: Number,
  team2_score: Number,
  winner: String (team name),
  winner_seed: Number,
  status: "pending" | "live" | "completed",
  is_active: Boolean,
  court: String (optional),
  time_slot: String (optional),
  created_at: Date,
  updated_at: Date
}
```

---

## 🤝 Contributing

ASTERISK was built for Aithra 2025 but can be adapted for any esports tournament. Contributions welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License. Free to use, modify, and distribute with attribution.

---

## 🎓 Credits & Acknowledgments

**Developed by:** ACM Student Chapter, Amal Jyothi College of Engineering  
**Event:** Aithra Techfest 2025  
**Technical Lead:** Amarnath  
**Organization:** Association for Computing Machinery (ACM) AJCE

**Technologies Used:**
- Python (Flask, aiohttp, Motor)
- MongoDB Atlas
- Go (WhatsApp Integration)
- FFmpeg (Live Streaming)
- TailwindCSS, HLS.js, Iconify
- Valorant by Riot Games (Game & Assets)

**Special Thanks:**
- ACM AJCE Core Team
- Aithra 2025 Organizing Committee
- All participating teams and players

---

## 📞 Support

For technical support or queries:
- **Email:** acm@ajce.in
- **Website:** https://astrisk.vercel.app
- **Event Portal:** https://ajce.in/aithra2025

---

**Built with ❤️ for the gaming community at AJCE**
