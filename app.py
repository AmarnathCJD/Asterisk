import asyncio
import json
import logging
import os
import random
import re
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Any

import aiohttp
from aiohttp import web
import aiohttp_cors
from aiofiles import open as aio_open
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import errors as pymongo_errors
from bson import ObjectId

log_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

file_handler = logging.FileHandler('astrisk_app.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)

http_logger = logging.getLogger('astrisk.http')
http_formatter = logging.Formatter(
    '%(asctime)s - HTTP - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
http_file_handler = logging.FileHandler('astrisk_http.log', encoding='utf-8')
http_file_handler.setLevel(logging.INFO)
http_file_handler.setFormatter(http_formatter)
http_logger.addHandler(http_file_handler)
http_logger.addHandler(console_handler)
http_logger.setLevel(logging.INFO)
http_logger.propagate = False

logger.info("=" * 80)
logger.info("ASTRISK Tournament System - Starting Up")
logger.info("=" * 80)

MONGO_URI = os.environ.get(
    "MONGODB_URL", ""
)
DB_NAME = "astrisk_tournament"
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DB_NAME]
registrations = db.registrations
matches_collection = db.matches

SQLITE_DB = "registrations_backup.db"
MASTER_PASSWORD = "0022"
RATE_LIMIT_STORAGE = {}

sse_clients: List[asyncio.Queue] = []

def serialize_datetime(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(serialize_datetime(item) for item in obj)
    else:
        return obj

def init_sqlite():
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id TEXT UNIQUE NOT NULL,
            team_name TEXT UNIQUE NOT NULL,
            college_name TEXT,
            lead_name TEXT NOT NULL,
            lead_email TEXT NOT NULL,
            lead_contact TEXT NOT NULL,
            members TEXT NOT NULL,
            substitute TEXT,
            ip_address TEXT,
            timestamp TEXT NOT NULL,
            payment_status TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_team_name ON registrations(team_name)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_payment_status ON registrations(payment_status)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_registration_id ON registrations(registration_id)
    """
    )

    conn.commit()
    conn.close()
    logger.info("SQLite backup database initialized")


def save_to_sqlite(registration_data: Dict) -> bool:
    try:
        conn = sqlite3.connect(SQLITE_DB)
        cursor = conn.cursor()

        members_json = json.dumps(registration_data["members"])
        substitute_json = json.dumps(registration_data.get("substitute", {}))

        cursor.execute(
            """
            INSERT INTO registrations 
            (registration_id, team_name, college_name, lead_name, lead_email, lead_contact, 
             members, substitute, ip_address, timestamp, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                registration_data["registration_id"],
                registration_data["team_name"],
                registration_data.get("college_name", ""),
                registration_data["lead"]["name"],
                registration_data["lead"]["email"],
                registration_data["lead"]["contact"],
                members_json,
                substitute_json,
                registration_data.get("ip_address", ""),
                (
                    registration_data["timestamp"].isoformat()
                    if isinstance(registration_data["timestamp"], datetime)
                    else str(registration_data["timestamp"])
                ),
                registration_data["payment_status"],
            ),
        )

        conn.commit()
        conn.close()
        logger.info(
            f"Registration backed up to SQLite: {registration_data['team_name']}"
        )
        return True
    except sqlite3.IntegrityError as e:
        logger.warning(f"SQLite backup failed (duplicate): {str(e)}")
        return False
    except Exception as e:
        logger.error(f"SQLite backup error: {str(e)}")
        return False


def update_payment_sqlite(team_name: str, new_status: str) -> bool:
    try:
        conn = sqlite3.connect(SQLITE_DB)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE registrations 
            SET payment_status = ?
            WHERE team_name = ?
        """,
            (new_status, team_name),
        )

        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()

        if rows_affected > 0:
            logger.info(f"SQLite backup updated: {team_name} -> {new_status}")
            return True
        return False
    except Exception as e:
        logger.error(f"SQLite update error: {str(e)}")
        return False


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    """Validate Indian phone number"""
    pattern = r"^[6-9]\d{9}$"
    return re.match(pattern, phone) is not None


def validate_team_name(team_name: str) -> bool:
    """Validate team name"""
    if len(team_name) < 3 or len(team_name) > 50:
        return False
    pattern = r"^[a-zA-Z0-9\s\-_\.]+$"
    return re.match(pattern, team_name) is not None


async def send_whatsapp(to_number: str, content: str) -> bool:
    """Send a WhatsApp message via a local service"""
    try:
        if not to_number:
            logger.warning("send_whatsapp called without phone number")
            return False

        payload = {"phnnumber": to_number, "content": content}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://127.0.0.1:4005/send-message", 
                json=payload, 
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"WhatsApp message sent to {to_number}")
                    return True
                else:
                    logger.warning(f"WhatsApp service returned {resp.status}: {await resp.text()}")
                    return False
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message to {to_number}: {e}")
        return False


def build_whatsapp_message(event: str, **kwargs) -> str:
    """Build human-friendly WhatsApp messages for different events"""
    def wrap_message(body_text):
        header = "*ASTERISK | ACM AJCE*\n\n"
        footer = "\n\nRegards ~ ACM AJCE"
        return header + body_text + footer

    try:
        if event == "registration_success":
            body = (
                "✅ *Registration — Confirmation*\n\n"
                f"*Team:* {kwargs.get('team_name')}\n"
                f"*Registration ID:* {kwargs.get('registration_id','N/A')}\n"
                f"*Team Auth Code:* {kwargs.get('auth_code')}\n"
                f"*Amount Due:* ₹{kwargs.get('amount', 600)}\n\n"
                "Dear Team Lead,\n\n"
                "Your team has been successfully registered for ASTRISK 2025."
                " Please retain the Team Auth Code securely; it is required to manage your team and respond to join requests via the dashboard.\n\n"
                "Access your team dashboard here: https://astrisk.vercel.app/team.html\n\n"
                "If you have any questions, reply to this message or contact the event organisers."
            )
            return wrap_message(body)

        if event == "open_team_created":
            body = (
                "🔓 *Open Team — Notification*\n\n"
                f"*Team:* {kwargs.get('team_name')}\n"
                f"*Team Auth Code:* {kwargs.get('auth_code')}\n\n"
                "Your team is now marked as *open* and may receive join requests from other participants."
                " Please review incoming requests promptly and accept only those you trust.\n\n"
                "Manage requests via: https://astrisk.vercel.app/team.html"
            )
            return wrap_message(body)

        if event == "join_request_received":
            body = (
                "📨 *Join Request Received*\n\n"
                f"*Team:* {kwargs.get('team_name')}\n\n"
                "Requester details:\n"
                f"• Name: {kwargs.get('name')}\n"
                f"• Email: {kwargs.get('email')}\n"
                f"• Phone: {kwargs.get('contact')}\n"
                f"• Riot ID: {kwargs.get('riot_id')}\n\n"
                "Please review this request in your team dashboard and respond at your earliest convenience."
            )
            return wrap_message(body)

        if event == "join_request_accepted":
            body = (
                "🎉 *Join Request — Accepted*\n\n"
                f"Dear {kwargs.get('name')},\n\n"
                f"Your request to join *{kwargs.get('team_name')}* has been accepted."
                " You have been added to the team roster.\n\n"
                "Please check the team dashboard for further details and follow any onboarding instructions provided by the team lead."
            )
            return wrap_message(body)

        if event == "join_request_declined":
            body = (
                "ℹ️ *Join Request — Declined*\n\n"
                f"Dear {kwargs.get('name')},\n\n"
                f"We regret to inform you that your request to join *{kwargs.get('team_name')}* has been declined by the team lead.\n\n"
                "You may explore other open teams or contact the team lead for clarification."
            )
            return wrap_message(body)

        if event == "payment_completed":
            body = (
                "✅ *Payment Received — Confirmation*\n\n"
                f"*Team:* {kwargs.get('team_name')}\n"
                f"*Registration ID:* {kwargs.get('registration_id','N/A')}\n"
                f"*Amount Paid:* ₹{kwargs.get('amount',600)}\n\n"
                "Thank you. We confirm receipt of your payment and your team is now fully registered for ASTRISK 2025."
                " A confirmation will be reflected on your team dashboard shortly.\n\n"
                "We look forward to your participation."
            )
            return wrap_message(body)

        generic = kwargs.get('content', '')
        if generic:
            return wrap_message(generic)
        return ''
    except Exception as e:
        logger.error(f"Error building whatsapp message for {event}: {e}")
        return kwargs.get('content', '')


async def check_duplicate_emails(emails: List[str]) -> tuple:
    """Check if any email is already registered"""
    for email in emails:
        doc = await registrations.find_one(
            {
                "$or": [{"members.email": email}, {"substitute.email": email}],
                "payment_status": "completed",
            }
        )
        if doc:
            return True, email
    return False, None


def get_client_ip(request: web.Request) -> str:
    """Get client IP address from request"""
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.remote or '127.0.0.1'


# ============================================================================
# SSE (Server-Sent Events) for Real-time Updates
# ============================================================================

async def broadcast_sse_event(event_type: str, data: Dict):
    """Broadcast an event to all connected SSE clients"""
    event_data = json.dumps({"type": event_type, "data": data})
    dead_clients = []
    
    for i, client_queue in enumerate(sse_clients):
        try:
            await client_queue.put(event_data)
        except:
            dead_clients.append(i)
    
    # Remove dead clients
    for i in reversed(dead_clients):
        sse_clients.pop(i)
    
    logger.info(f"Broadcasted SSE event '{event_type}' to {len(sse_clients)} clients")


# ============================================================================
# UTILITY FUNCTIONS FOR TOURNAMENT LOGIC
# ============================================================================

async def calculate_best_loser() -> Optional[Dict[str, Any]]:
    """
    Calculate the best loser from Round of 18 matches.
    Returns the losing team with the highest score.
    """
    try:
        # Get all completed Round of 18 matches
        matches = await matches_collection.find({
            "round": "Round of 18",
            "status": "completed"
        }).to_list(None)
        
        if not matches:
            return None
        
        best_loser = None
        highest_score = -1
        
        for match in matches:
            # Determine the loser and their score
            winner = match.get("winner")
            team1 = match.get("team1")
            team2 = match.get("team2")
            team1_score = match.get("team1_score", 0)
            team2_score = match.get("team2_score", 0)
            
            if not winner:
                continue
                
            # Find the losing team and their score
            if winner == team1:
                loser = team2
                loser_score = team2_score
                loser_seed = match.get("team2_seed")
            else:
                loser = team1
                loser_score = team1_score
                loser_seed = match.get("team1_seed")
            
            # Update best loser if this loser has a higher score
            if loser_score > highest_score:
                highest_score = loser_score
                best_loser = {
                    "team": loser,
                    "score": loser_score,
                    "seed": loser_seed,
                    "match_id": str(match.get("_id")),
                    "match_number": match.get("match_number")
                }
        
        return best_loser
    except Exception as e:
        logger.error(f"Error calculating best loser: {e}")
        return None


async def get_tournament_advancement_status() -> Dict[str, Any]:
    """
    Get current tournament advancement status:
    - Winners from Round of 18
    - Best loser
    - Teams advancing to quarterfinals
    """
    try:
        # Get all Round of 18 matches
        matches = await matches_collection.find({
            "round": "Round of 18"
        }).to_list(None)
        
        winners = []
        completed_count = 0
        
        for match in matches:
            if match.get("status") == "completed" and match.get("winner"):
                winners.append({
                    "team": match.get("winner"),
                    "match_number": match.get("match_number"),
                    "seed": match.get("team1_seed") if match.get("winner") == match.get("team1") else match.get("team2_seed")
                })
                completed_count += 1
        
        # Calculate best loser
        best_loser = await calculate_best_loser()
        
        # Determine teams advancing
        advancing_teams = winners.copy()
        if best_loser and completed_count == 9:  # All matches completed
            advancing_teams.append({
                "team": best_loser["team"],
                "match_number": best_loser["match_number"],
                "seed": best_loser["seed"],
                "is_best_loser": True
            })
        
        return {
            "total_matches": len(matches),
            "completed_matches": completed_count,
            "winners": winners,
            "best_loser": best_loser,
            "advancing_teams": advancing_teams,
            "ready_for_quarterfinals": completed_count == 9 and len(advancing_teams) == 10
        }
    except Exception as e:
        logger.error(f"Error getting advancement status: {e}")
        return {
            "error": str(e),
            "total_matches": 0,
            "completed_matches": 0,
            "winners": [],
            "best_loser": None,
            "advancing_teams": [],
            "ready_for_quarterfinals": False
        }


async def sse_handler(request: web.Request) -> web.StreamResponse:
    """Server-Sent Events endpoint for real-time match updates"""
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    
    await response.prepare(request)
    
    # Create a queue for this client
    client_queue = asyncio.Queue()
    sse_clients.append(client_queue)
    
    logger.info(f"New SSE client connected. Total clients: {len(sse_clients)}")
    
    try:
        # Send initial connection confirmation
        await response.write(b'data: {"type":"connected","message":"SSE connection established"}\n\n')
        
        # Keep sending events from the queue
        while True:
            event_data = await client_queue.get()
            await response.write(f'data: {event_data}\n\n'.encode('utf-8'))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"SSE error: {e}")
    finally:
        if client_queue in sse_clients:
            sse_clients.remove(client_queue)
        logger.info(f"SSE client disconnected. Remaining clients: {len(sse_clients)}")
    
    return response


# ============================================================================
# MATCH MANAGEMENT ENDPOINTS
# ============================================================================

async def get_matches(request: web.Request) -> web.Response:
    """Get all matches"""
    try:
        matches = []
        async for match in matches_collection.find().sort("round", 1).sort("match_number", 1):
            match['_id'] = str(match['_id'])
            matches.append(match)
        
        # Serialize datetime objects
        matches = serialize_datetime(matches)
        
        return web.json_response({
            "success": True,
            "matches": matches
        })
    except Exception as e:
        logger.error(f"Get matches error: {e}")
        return web.json_response({
            "success": False,
            "message": "Error fetching matches"
        }, status=500)


async def create_match(request: web.Request) -> web.Response:
    """Create a new match (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        
        match_data = {
            "round": data.get("round"),  # "Round of 16", "Quarterfinals", etc.
            "match_number": data.get("match_number"),
            "team1": data.get("team1"),
            "team2": data.get("team2"),
            "team1_seed": data.get("team1_seed"),
            "team2_seed": data.get("team2_seed"),
            "winner": data.get("winner"),  # null until match is completed
            "status": data.get("status", "upcoming"),  # "upcoming", "live", "completed"
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await matches_collection.insert_one(match_data)
        match_data['_id'] = str(result.inserted_id)
        
        match_data = serialize_datetime(match_data)
        
        await broadcast_sse_event("match_created", match_data)
        
        return web.json_response({
            "success": True,
            "message": "Match created",
            "match": match_data
        })
    except Exception as e:
        logger.error(f"Create match error: {e}")
        return web.json_response({
            "success": False,
            "message": "Error creating match"
        }, status=500)


async def update_match(request: web.Request) -> web.Response:
    """Update a match (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        match_id_str = request.match_info['match_id']
        data = await request.json()
        
        # Convert string ID to ObjectId
        try:
            match_id = ObjectId(match_id_str)
        except Exception:
            return web.json_response({
                "success": False,
                "message": "Invalid match ID format"
            }, status=400)
        
        update_data = {
            "updated_at": datetime.utcnow()
        }
        
        # Only update provided fields
        for field in ["round", "match_number", "team1", "team2", "team1_seed", "team2_seed", "winner", "status"]:
            if field in data:
                update_data[field] = data[field]
        
        result = await matches_collection.update_one(
            {"_id": match_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return web.json_response({
                "success": False,
                "message": "Match not found"
            }, status=404)
        
        updated_match = await matches_collection.find_one({"_id": match_id})
        if updated_match is None:
            return web.json_response({
                "success": False,
                "message": "Match not found after update"
            }, status=404)
            
        updated_match['_id'] = str(updated_match['_id'])
        
        updated_match = serialize_datetime(updated_match)
        
        await broadcast_sse_event("match_updated", updated_match)
        
        return web.json_response({
            "success": True,
            "message": "Match updated",
            "match": updated_match
        })
    except Exception as e:
        logger.error(f"Update match error: {e}")
        return web.json_response({
            "success": False,
            "message": "Error updating match"
        }, status=500)


async def delete_match(request: web.Request) -> web.Response:
    """Delete a match (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        match_id_str = request.match_info['match_id']
        
        # Convert string ID to ObjectId
        try:
            match_id = ObjectId(match_id_str)
        except Exception:
            return web.json_response({
                "success": False,
                "message": "Invalid match ID format"
            }, status=400)
        
        result = await matches_collection.delete_one({"_id": match_id})
        
        if result.deleted_count == 0:
            return web.json_response({
                "success": False,
                "message": "Match not found"
            }, status=404)
        
        # Broadcast to SSE clients
        await broadcast_sse_event("match_deleted", {"match_id": match_id_str})
        
        return web.json_response({
            "success": True,
            "message": "Match deleted"
        })
    except Exception as e:
        logger.error(f"Delete match error: {e}")
        return web.json_response({
            "success": False,
            "message": "Error deleting match"
        }, status=500)


# ============================================================================
# TOURNAMENT CONTROL PANEL ENDPOINTS
# ============================================================================

async def initialize_tournament_bracket(request: web.Request) -> web.Response:
    """Initialize the tournament bracket with baseline data from matchlineup.html"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        # Clear existing matches
        await matches_collection.delete_many({})
        
        # Baseline data - Round of 16 (9 matches)
        baseline_matches = [
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 1,
                "team1": "Go Lose Fast",
                "team2": "Gods Own Country",
                "team1_seed": 1,
                "team2_seed": 16,
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 2,
                "team1": "EXODUS",
                "team2": "Domain 5",
                "team1_seed": 8,
                "team2_seed": 9,
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 3,
                "team1": "Targaryens",
                "team2": "Hestia",
                "team1_seed": 4,
                "team2_seed": 13,
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 4,
                "team1": "Renegades",
                "team2": "Spike Rushers",
                "team1_seed": 5,
                "team2_seed": 12,
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 5,
                "team1": "BLACKLISTED",
                "team2": "Log Bait",
                "team1_seed": 2,
                "team2_seed": 15,
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 6,
                "team1": "BINARY LEGION",
                "team2": "Vitality",
                "team1_seed": 7,
                "team2_seed": 10,
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 7,
                "team1": "Hardstuck",
                "team2": "XLr8",
                "team1_seed": 3,
                "team2_seed": 14,
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 8,
                "team1": "LavaLoon",
                "team2": "ULTF4",
                "team1_seed": 6,
                "team2_seed": 11,
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "round": "Round of 16",
                "round_number": 1,
                "match_number": 9,
                "team1": "LABWUBWU",
                "team2": "Esports Division NITC Alpha",
                "team1_seed": "TBD",
                "team2_seed": "TBD",
                "winner": None,
                "team1_score": 0,
                "team2_score": 0,
                "status": "pending",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        # Insert baseline matches
        result = await matches_collection.insert_many(baseline_matches)
        
        logger.info(f"Tournament bracket initialized with {len(result.inserted_ids)} matches")
        
        # Broadcast to SSE clients
        await broadcast_sse_event("bracket_initialized", {
            "matches_count": len(result.inserted_ids)
        })
        
        return web.json_response({
            "success": True,
            "message": "Tournament bracket initialized",
            "matches_created": len(result.inserted_ids)
        })
    except Exception as e:
        logger.error(f"Initialize bracket error: {e}")
        return web.json_response({
            "success": False,
            "message": f"Error initializing bracket: {str(e)}"
        }, status=500)


async def set_active_match(request: web.Request) -> web.Response:
    """Set a specific match as active (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        match_id_str = data.get("match_id")
        
        if not match_id_str:
            return web.json_response({
                "success": False,
                "message": "Match ID required"
            }, status=400)
        
        # Convert string ID to ObjectId
        try:
            match_id = ObjectId(match_id_str)
        except Exception:
            return web.json_response({
                "success": False,
                "message": "Invalid match ID format"
            }, status=400)
        
        # Deactivate all other matches
        await matches_collection.update_many(
            {},
            {"$set": {"is_active": False}}
        )
        
        # Activate the specified match and set to live
        result = await matches_collection.update_one(
            {"_id": match_id},
            {
                "$set": {
                    "is_active": True,
                    "status": "live",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            return web.json_response({
                "success": False,
                "message": "Match not found"
            }, status=404)
        
        active_match = await matches_collection.find_one({"_id": match_id})
        if active_match is None:
            return web.json_response({
                "success": False,
                "message": "Match not found after activation"
            }, status=404)
            
        active_match['_id'] = str(active_match['_id'])
        
        active_match = serialize_datetime(active_match)
        
        await broadcast_sse_event("active_match_changed", active_match)
        
        logger.info(f"Match {match_id_str} set as active")
        
        return web.json_response({
            "success": True,
            "message": "Match activated",
            "match": active_match
        })
    except Exception as e:
        logger.error(f"Set active match error: {e}")
        return web.json_response({
            "success": False,
            "message": f"Error setting active match: {str(e)}"
        }, status=500)


async def advance_winners(request: web.Request) -> web.Response:
    """Advance winners from one round to the next (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        from_round_number = data.get("from_round_number")
        
        if from_round_number is None:
            return web.json_response({
                "success": False,
                "message": "from_round_number required"
            }, status=400)
        
        # Get all completed matches from the specified round
        completed_matches = []
        async for match in matches_collection.find({
            "round_number": from_round_number,
            "status": "completed",
            "winner": {"$ne": None}
        }).sort("match_number", 1):
            completed_matches.append(match)
        
        if not completed_matches:
            return web.json_response({
                "success": False,
                "message": f"No completed matches found in round {from_round_number}"
            }, status=400)
        
        # Determine next round details
        round_names = {
            1: ("Round of 16", "Quarterfinals"),
            2: ("Quarterfinals", "Semifinals"),
            3: ("Semifinals", "Finals"),
            4: ("Finals", "Champion")
        }
        
        if from_round_number not in round_names:
            return web.json_response({
                "success": False,
                "message": "Invalid round number"
            }, status=400)
        
        next_round_name = round_names[from_round_number][1]
        next_round_number = from_round_number + 1
        
        # Create next round matches by pairing winners
        new_matches = []
        for i in range(0, len(completed_matches), 2):
            if i + 1 < len(completed_matches):
                match1 = completed_matches[i]
                match2 = completed_matches[i + 1]
                
                new_match = {
                    "round": next_round_name,
                    "round_number": next_round_number,
                    "match_number": (i // 2) + 1,
                    "team1": match1.get("winner"),
                    "team2": match2.get("winner"),
                    "team1_seed": match1.get("winner_seed"),
                    "team2_seed": match2.get("winner_seed"),
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                new_matches.append(new_match)
        
        if new_matches:
            result = await matches_collection.insert_many(new_matches)
            
            # Broadcast to SSE clients
            await broadcast_sse_event("winners_advanced", {
                "from_round": from_round_number,
                "to_round": next_round_number,
                "matches_created": len(result.inserted_ids)
            })
            
            logger.info(f"Advanced {len(new_matches)} winners from round {from_round_number} to {next_round_number}")
            
            return web.json_response({
                "success": True,
                "message": f"Winners advanced to {next_round_name}",
                "matches_created": len(result.inserted_ids),
                "new_matches": [str(mid) for mid in result.inserted_ids]
            })
        else:
            return web.json_response({
                "success": False,
                "message": "Not enough completed matches to create next round"
            }, status=400)
            
    except Exception as e:
        logger.error(f"Advance winners error: {e}")
        return web.json_response({
            "success": False,
            "message": f"Error advancing winners: {str(e)}"
        }, status=500)


async def set_match_winner(request: web.Request) -> web.Response:
    """Set the winner of a match and update scores (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        match_id_str = data.get("match_id")
        winner = data.get("winner")  # "team1" or "team2"
        team1_score = data.get("team1_score", 0)
        team2_score = data.get("team2_score", 0)
        
        if not match_id_str or not winner:
            return web.json_response({
                "success": False,
                "message": "match_id and winner required"
            }, status=400)
        
        # Convert string ID to ObjectId
        try:
            match_id = ObjectId(match_id_str)
        except Exception:
            return web.json_response({
                "success": False,
                "message": "Invalid match ID format"
            }, status=400)
        
        # Get the match
        match = await matches_collection.find_one({"_id": match_id})
        if not match:
            return web.json_response({
                "success": False,
                "message": "Match not found"
            }, status=404)
        
        # Determine winner name and seed
        winner_name = match[winner]
        winner_seed = match.get(f"{winner}_seed")
        
        # Update match with winner and scores
        update_data = {
            "winner": winner_name,
            "winner_seed": winner_seed,
            "winner_team": winner,  # "team1" or "team2"
            "team1_score": team1_score,
            "team2_score": team2_score,
            "status": "completed",
            "is_active": False,
            "updated_at": datetime.utcnow()
        }
        
        await matches_collection.update_one(
            {"_id": match_id},
            {"$set": update_data}
        )
        
        updated_match = await matches_collection.find_one({"_id": match_id})
        if updated_match is None:
            return web.json_response({
                "success": False,
                "message": "Match not found after completion"
            }, status=404)
            
        updated_match['_id'] = str(updated_match['_id'])
        
        updated_match = serialize_datetime(updated_match)
        
        await broadcast_sse_event("match_completed", updated_match)
        
        logger.info(f"Match {match_id_str} completed - Winner: {winner_name}")
        
        return web.json_response({
            "success": True,
            "message": "Match winner set",
            "match": updated_match
        })
    except Exception as e:
        logger.error(f"Set match winner error: {e}")
        return web.json_response({
            "success": False,
            "message": f"Error setting match winner: {str(e)}"
        }, status=500)


async def get_tournament_stats(request: web.Request) -> web.Response:
    """Get tournament statistics"""
    try:
        total_matches = await matches_collection.count_documents({})
        active_matches = await matches_collection.count_documents({"status": "live"})
        completed_matches = await matches_collection.count_documents({"status": "completed"})
        pending_matches = await matches_collection.count_documents({"status": "pending"})
        
        # Get all unique teams
        all_teams = set()
        eliminated_teams = set()
        
        async for match in matches_collection.find():
            if match.get("team1"):
                all_teams.add(match["team1"])
            if match.get("team2"):
                all_teams.add(match["team2"])
            
            # If match is completed, the loser is eliminated
            if match.get("status") == "completed" and match.get("winner"):
                loser = match["team2"] if match["winner"] == match["team1"] else match["team1"]
                eliminated_teams.add(loser)
        
        return web.json_response({
            "success": True,
            "stats": {
                "total_matches": total_matches,
                "active_matches": active_matches,
                "completed_matches": completed_matches,
                "pending_matches": pending_matches,
                "total_teams": len(all_teams),
                "eliminated_teams": len(eliminated_teams),
                "remaining_teams": len(all_teams) - len(eliminated_teams)
            }
        })
    except Exception as e:
        logger.error(f"Get tournament stats error: {e}")
        return web.json_response({
            "success": False,
            "message": f"Error getting stats: {str(e)}"
        }, status=500)


async def get_advancement_status(request: web.Request) -> web.Response:
    """Get tournament advancement status including best loser calculation"""
    try:
        status = await get_tournament_advancement_status()
        return web.json_response({
            "success": True,
            "advancement": status
        })
    except Exception as e:
        logger.error(f"Get advancement status error: {e}")
        return web.json_response({
            "success": False,
            "message": f"Error getting advancement status: {str(e)}"
        }, status=500)


async def get_best_loser(request: web.Request) -> web.Response:
    """Get the best loser (losing team with highest score) from Round of 18"""
    try:
        best_loser = await calculate_best_loser()
        
        if not best_loser:
            return web.json_response({
                "success": True,
                "best_loser": None,
                "message": "No completed matches yet or unable to calculate best loser"
            })
        
        return web.json_response({
            "success": True,
            "best_loser": best_loser
        })
    except Exception as e:
        logger.error(f"Get best loser error: {e}")
        return web.json_response({
            "success": False,
            "message": f"Error getting best loser: {str(e)}"
        }, status=500)


async def advance_team_to_round(request: web.Request) -> web.Response:
    """Advance a specific team to the next round (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        match_id_str = data.get("match_id")
        team_name = data.get("team_name")
        target_round = data.get("target_round", "Quarterfinals")
        
        if not match_id_str or not team_name:
            return web.json_response({
                "success": False,
                "message": "match_id and team_name required"
            }, status=400)
        
        # Convert string ID to ObjectId
        try:
            match_id = ObjectId(match_id_str)
        except Exception:
            return web.json_response({
                "success": False,
                "message": "Invalid match ID format"
            }, status=400)
        
        # Get the source match
        source_match = await matches_collection.find_one({"_id": match_id})
        
        if not source_match:
            return web.json_response({
                "success": False,
                "message": "Match not found"
            }, status=404)
        
        # Determine team seed
        team_seed = None
        if source_match.get("team1") == team_name:
            team_seed = source_match.get("team1_seed")
        elif source_match.get("team2") == team_name:
            team_seed = source_match.get("team2_seed")
        
        return web.json_response({
            "success": True,
            "message": f"Team {team_name} ready to advance to {target_round}",
            "team": {
                "name": team_name,
                "seed": team_seed,
                "from_match": match_id_str
            },
            "note": "Use advance_winners endpoint to create quarterfinal matches"
        })
        
    except Exception as e:
        logger.error(f"Advance team error: {e}")
        return web.json_response({
            "success": False,
            "message": f"Error advancing team: {str(e)}"
        }, status=500)


# ============================================================================
# LIVE STREAMING ENDPOINTS
# ============================================================================

# Store live stream state
stream_state = {
    "team1": {
        "name": "TEAM ALPHA",
        "score": 0,
        "subtitle": "Attackers"
    },
    "team2": {
        "name": "TEAM OMEGA",
        "score": 0,
        "subtitle": "Defenders"
    },
    "map": "HAVEN",
    "round": "1/24",
    "bestOf": "BO3",
    "matchTitle": "Grand Finals — ASTERISK 2025",
    "ingress_server": ""  # HLS stream source URL
}

# Store viewer count (SSE clients for streaming)
stream_viewers = []


async def broadcast_stream_event(event_type: str, data: Dict):
    """Broadcast event to all stream viewers via SSE"""
    if not stream_viewers:
        return
    
    event_message = f'event: {event_type}\ndata: {json.dumps(data)}'
    
    for viewer_queue in stream_viewers[:]:  # Copy list to avoid modification during iteration
        try:
            await viewer_queue.put(event_message)
        except Exception as e:
            logger.error(f"Error broadcasting to stream viewer: {e}")
            try:
                stream_viewers.remove(viewer_queue)
            except ValueError:
                pass
    
    logger.info(f"Broadcasted stream event '{event_type}' to {len(stream_viewers)} viewers")


async def get_stream_state(request: web.Request) -> web.Response:
    """Get current stream/match state"""
    try:
        return web.json_response(stream_state)
    except Exception as e:
        logger.error(f"Get stream state error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


async def update_stream_score(request: web.Request) -> web.Response:
    """Update team scores"""
    try:
        data = await request.json()
        team = data.get("team")
        score = data.get("score")
        
        if team in [1, 2] and score is not None:
            stream_state[f"team{team}"]["score"] = score
            
            # Broadcast update to all stream viewers
            await broadcast_stream_event("score_updated", {
                "team": team,
                "score": score,
                "state": stream_state
            })
            
            return web.json_response({"success": True, "state": stream_state})
        
        return web.json_response({
            "success": False,
            "message": "Invalid data"
        }, status=400)
    except Exception as e:
        logger.error(f"Update stream score error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=400)


async def update_stream_teams(request: web.Request) -> web.Response:
    """Update team names and info"""
    try:
        data = await request.json()
        
        if "team1" in data:
            if "name" in data["team1"]:
                stream_state["team1"]["name"] = data["team1"]["name"]
            if "subtitle" in data["team1"]:
                stream_state["team1"]["subtitle"] = data["team1"]["subtitle"]
        
        if "team2" in data:
            if "name" in data["team2"]:
                stream_state["team2"]["name"] = data["team2"]["name"]
            if "subtitle" in data["team2"]:
                stream_state["team2"]["subtitle"] = data["team2"]["subtitle"]
        
        # Broadcast update to all stream viewers
        await broadcast_stream_event("teams_updated", {"state": stream_state})
        
        return web.json_response({"success": True, "state": stream_state})
    except Exception as e:
        logger.error(f"Update stream teams error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=400)


async def update_stream_match_info(request: web.Request) -> web.Response:
    """Update match information"""
    try:
        data = await request.json()
        
        if "map" in data:
            stream_state["map"] = data["map"]
        if "round" in data:
            stream_state["round"] = data["round"]
        if "bestOf" in data:
            stream_state["bestOf"] = data["bestOf"]
        if "matchTitle" in data:
            stream_state["matchTitle"] = data["matchTitle"]
        
        # Broadcast update to all stream viewers
        await broadcast_stream_event("match_info_updated", {"state": stream_state})
        
        return web.json_response({"success": True, "state": stream_state})
    except Exception as e:
        logger.error(f"Update stream match info error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=400)


async def reset_stream_match(request: web.Request) -> web.Response:
    """Reset stream match to initial state"""
    global stream_state
    stream_state = {
        "team1": {
            "name": "TEAM ALPHA",
            "score": 0,
            "subtitle": "Attackers"
        },
        "team2": {
            "name": "TEAM OMEGA",
            "score": 0,
            "subtitle": "Defenders"
        },
        "map": "HAVEN",
        "round": "1/24",
        "bestOf": "BO3",
        "matchTitle": "Grand Finals — ASTERISK 2025",
        "ingress_server": stream_state.get("ingress_server", "")  # Keep ingress server
    }
    
    # Broadcast update to all stream viewers
    await broadcast_stream_event("match_reset", {"state": stream_state})
    
    return web.json_response({"success": True, "state": stream_state})


async def trigger_match_start(request: web.Request) -> web.Response:
    """Trigger match start animation for all viewers"""
    try:
        team1_data = {
            "name": stream_state["team1"]["name"],
            "subtitle": stream_state["team1"]["subtitle"],
            "icon": "game-icons:fire-shield"
        }
        
        team2_data = {
            "name": stream_state["team2"]["name"],
            "subtitle": stream_state["team2"]["subtitle"],
            "icon": "game-icons:lightning-shield"
        }
        
        # Broadcast to all stream viewers
        await broadcast_stream_event("matchStart", {
            "team1": team1_data,
            "team2": team2_data
        })
        
        return web.json_response({
            "success": True,
            "message": "Match start animation triggered"
        })
    except Exception as e:
        logger.error(f"Trigger match start error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


async def trigger_match_end(request: web.Request) -> web.Response:
    """Trigger match ended overlay for all viewers"""
    try:
        data = await request.json() if request.can_read_body else {}
        winner = data.get("winner") if data else None
        
        team1_data = {
            "name": stream_state["team1"]["name"],
            "score": stream_state["team1"]["score"]
        }
        
        team2_data = {
            "name": stream_state["team2"]["name"],
            "score": stream_state["team2"]["score"]
        }
        
        # Broadcast to all stream viewers
        await broadcast_stream_event("matchEnd", {
            "team1": team1_data,
            "team2": team2_data,
            "winner": winner,
            "matchTitle": stream_state["matchTitle"]
        })
        
        return web.json_response({
            "success": True,
            "message": "Match ended overlay triggered"
        })
    except Exception as e:
        logger.error(f"Trigger match end error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


async def show_pause_screen(request: web.Request) -> web.Response:
    """Show pause screen to all viewers"""
    try:
        # Broadcast to all stream viewers
        await broadcast_stream_event("showPause", {
            "action": "show",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info("Pause screen shown to all viewers")
        
        return web.json_response({
            "success": True,
            "message": "Pause screen shown"
        })
    except Exception as e:
        logger.error(f"Show pause screen error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


async def hide_pause_screen(request: web.Request) -> web.Response:
    """Hide pause screen from all viewers"""
    try:
        # Broadcast to all stream viewers
        await broadcast_stream_event("hidePause", {
            "action": "hide",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info("Pause screen hidden from all viewers")
        
        return web.json_response({
            "success": True,
            "message": "Pause screen hidden"
        })
    except Exception as e:
        logger.error(f"Hide pause screen error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


async def stream_sse_handler(request: web.Request) -> web.StreamResponse:
    """SSE endpoint for live stream viewers"""
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    
    await response.prepare(request)
    
    # Create a queue for this viewer
    viewer_queue = asyncio.Queue()
    stream_viewers.append(viewer_queue)
    viewer_id = id(viewer_queue)
    
    logger.info(f"New stream viewer connected. Total viewers: {len(stream_viewers)}")
    
    try:
        # Send initial connection confirmation
        await response.write(f'event: connected\ndata: {json.dumps({"viewerId": viewer_id})}\n\n'.encode('utf-8'))
        
        # Send viewer count
        await response.write(f'event: viewerCount\ndata: {json.dumps({"count": len(stream_viewers)})}\n\n'.encode('utf-8'))
        
        # Keep sending events from the queue
        while True:
            event_data = await viewer_queue.get()
            await response.write(f'{event_data}\n\n'.encode('utf-8'))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Stream SSE error: {e}")
    finally:
        if viewer_queue in stream_viewers:
            stream_viewers.remove(viewer_queue)
        logger.info(f"Stream viewer disconnected. Remaining viewers: {len(stream_viewers)}")
        
        # Broadcast updated viewer count
        for viewer in stream_viewers:
            try:
                await viewer.put(f'event: viewerCount\ndata: {json.dumps({"count": len(stream_viewers)})}')
            except:
                pass
    
    return response


async def send_stream_chat(request: web.Request) -> web.Response:
    """Handle chat message submission for live stream"""
    try:
        data = await request.json()
        message = data.get('message', '').strip()
        viewer_id = data.get('viewerId', 'Unknown')
        
        if not message:
            return web.json_response({
                'status': 'error',
                'message': 'Empty message'
            }, status=400)
        
        # Broadcast to all viewers
        username = f"Viewer-{str(viewer_id)[:8]}"
        
        for viewer in stream_viewers:
            try:
                await viewer.put(f'event: chatMessage\ndata: {json.dumps({"message": message, "username": username, "timestamp": str(id(message))})}')
            except:
                pass
        
        return web.json_response({'status': 'ok'})
    except Exception as e:
        logger.error(f"Send stream chat error: {e}")
        return web.json_response({
            'status': 'error',
            'message': str(e)
        }, status=400)


async def get_stream_viewer_count(request: web.Request) -> web.Response:
    """Get current viewer count"""
    return web.json_response({'count': len(stream_viewers)})


async def update_ingress_server(request: web.Request) -> web.Response:
    """Update ingress server URL (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        ingress_url = data.get("ingress_server", "").strip()
        
        if not ingress_url:
            return web.json_response({
                "success": False,
                "message": "Ingress server URL required"
            }, status=400)
        
        # Update in memory
        stream_state["ingress_server"] = ingress_url
        
        # Store in database for persistence (using global db object)
        try:
            config_collection = db.config
            await config_collection.update_one(
                {"key": "ingress_server"},
                {"$set": {"value": ingress_url, "updated_at": datetime.utcnow()}},
                upsert=True
            )
        except Exception as db_error:
            logger.warning(f"Failed to save ingress server to DB: {db_error}")
        
        logger.info(f"Ingress server updated: {ingress_url}")
        
        return web.json_response({
            "success": True,
            "ingress_server": ingress_url
        })
    except Exception as e:
        logger.error(f"Update ingress server error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


async def get_ingress_server(request: web.Request) -> web.Response:
    """Get current ingress server URL"""
    try:
        # Try to get from database first (using global db object)
        if not stream_state.get("ingress_server"):
            try:
                config_collection = db.config
                config = await config_collection.find_one({"key": "ingress_server"})
                if config:
                    stream_state["ingress_server"] = config.get("value", "")
            except Exception as db_error:
                logger.warning(f"Failed to load ingress server from DB: {db_error}")
        
        return web.json_response({
            "success": True,
            "ingress_server": stream_state.get("ingress_server", "")
        })
    except Exception as e:
        logger.error(f"Get ingress server error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


# ============================================================================
# TEAM STATS & PAUSE SCREEN
# ============================================================================

async def get_team_stats(request: web.Request) -> web.Response:
    """Get all team stats for pause screen"""
    try:
        team_stats = await db.team_stats.find().sort("points", -1).to_list(length=None)
        
        # Convert ObjectId to string
        for team in team_stats:
            team['_id'] = str(team['_id'])
        
        return web.json_response({
            "success": True,
            "teams": team_stats
        })
    except Exception as e:
        logger.error(f"Get team stats error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e),
            "teams": []
        }, status=500)


async def update_team_stats(request: web.Request) -> web.Response:
    """Update team stats (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        team_name = data.get("team_name", "").strip()
        wins = int(data.get("wins", 0))
        losses = int(data.get("losses", 0))
        points = int(data.get("points", 0))
        status = data.get("status", "competing")  # competing, qualified, eliminated
        
        if not team_name:
            return web.json_response({
                "success": False,
                "message": "Team name required"
            }, status=400)
        
        if status not in ["competing", "qualified", "eliminated"]:
            return web.json_response({
                "success": False,
                "message": "Invalid status. Must be: competing, qualified, or eliminated"
            }, status=400)
        
        # Update or insert team stats (using global db object)
        team_stats_collection = db.team_stats
        result = await team_stats_collection.update_one(
            {"team_name": team_name},
            {
                "$set": {
                    "wins": wins,
                    "losses": losses,
                    "points": points,
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        logger.info(f"Team stats updated: {team_name} - W:{wins} L:{losses} P:{points} Status:{status}")
        
        return web.json_response({
            "success": True,
            "team_name": team_name,
            "wins": wins,
            "losses": losses,
            "points": points,
            "status": status
        })
    except ValueError as ve:
        return web.json_response({
            "success": False,
            "message": "Invalid number format for wins/losses/points"
        }, status=400)
    except Exception as e:
        logger.error(f"Update team stats error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


async def delete_team_stats(request: web.Request) -> web.Response:
    """Delete team stats (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        team_name = data.get("team_name", "").strip()
        
        if not team_name:
            return web.json_response({
                "success": False,
                "message": "Team name required"
            }, status=400)
        
        # Delete team stats (using global db object)
        team_stats_collection = db.team_stats
        result = await team_stats_collection.delete_one({"team_name": team_name})
        
        if result.deleted_count > 0:
            logger.info(f"Team stats deleted: {team_name}")
            return web.json_response({
                "success": True,
                "message": f"Team stats deleted for {team_name}"
            })
        else:
            return web.json_response({
                "success": False,
                "message": f"Team not found: {team_name}"
            }, status=404)
    except Exception as e:
        logger.error(f"Delete team stats error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


async def toggle_pause_screen(request: web.Request) -> web.Response:
    """Toggle pause screen visibility (admin only)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        action = data.get("action", "show")  # show or hide
        
        if action not in ["show", "hide"]:
            return web.json_response({
                "success": False,
                "message": "Invalid action. Must be 'show' or 'hide'"
            }, status=400)
        
        # Broadcast pause screen event to all viewers
        event_data = {
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await broadcast_sse_event("pause_screen", event_data)
        if action == "show":
            await broadcast_stream_event("showPause", event_data)
        else:
            await broadcast_stream_event("hidePause", event_data)
        
        logger.info(f"Pause screen {action} triggered")
        
        return web.json_response({
            "success": True,
            "action": action
        })
    except Exception as e:
        logger.error(f"Toggle pause screen error: {e}")
        return web.json_response({
            "success": False,
            "message": str(e)
        }, status=500)


# ============================================================================
# TEMPLATE SERVING
# ============================================================================

async def serve_template(request: web.Request, template_name: str) -> web.Response:
    """Serve HTML templates"""
    try:
        file_path = os.path.join('templates', template_name)
        async with aio_open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        return web.Response(text=content, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="Page not found", status=404)
    except Exception as e:
        logger.error(f"Error serving template {template_name}: {e}")
        return web.Response(text="Internal server error", status=500)


async def index(request: web.Request) -> web.Response:
    return await serve_template(request, 'index.html')


async def registration_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'reg.html')


async def team_dashboard_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'team.html')


async def teams_list_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'teams.html')


async def matchlineup_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'matchlineup.html')


async def dash_control_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'dash-control.html')


async def game_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'game.html')

async def live_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'live.html')

async def control_panel_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'control.html')

async def stream_control_page(request: web.Request) -> web.Response:
    return await serve_template(request, 'stream-control.html')


# ============================================================================
# REGISTRATION ENDPOINTS (Preserved from Flask version)
# ============================================================================

async def register_team(request: web.Request) -> web.Response:
    """Register a team - exact behavior from Flask version"""
    try:
        data = await request.json()

        required_fields = ["team_name", "lead", "members"]
        for field in required_fields:
            if field not in data:
                return web.json_response(
                    {
                        "success": False,
                        "message": f"Missing required field: {field}",
                    },
                    status=400,
                )

        team_name = data["team_name"].strip()
        college_name = data.get("college_name", "").strip()
        lead = data["lead"]
        members = data["members"]
        substitute = data.get("substitute", {})

        if not validate_team_name(team_name):
            return web.json_response(
                {
                    "success": False,
                    "message": "Invalid team name. Only alphanumeric characters, spaces, hyphens, underscores, and dots are allowed (3-50 characters).",
                },
                status=400,
            )

        existing_team = await registrations.find_one(
            {"team_name": team_name, "payment_status": "completed"}
        )
        if existing_team:
            return web.json_response(
                {
                    "success": False,
                    "message": "Team name already taken. Please choose a different name.",
                },
                status=400,
            )

        if not all([lead.get("name"), lead.get("email"), lead.get("contact")]):
            return web.json_response(
                {"success": False, "message": "All team lead fields are required"},
                status=400,
            )

        if not validate_email(lead["email"]):
            return web.json_response(
                {"success": False, "message": "Invalid team lead email format"},
                status=400,
            )

        if not validate_phone(lead["contact"]):
            return web.json_response(
                {
                    "success": False,
                    "message": "Invalid team lead phone number. Must be a valid 10-digit Indian number.",
                },
                status=400,
            )

        if len(members) < 4:
            return web.json_response(
                {
                    "success": False,
                    "message": "Minimum 4 team members required (excluding team lead and substitute)",
                },
                status=400,
            )

        if len(members) > 5:
            return web.json_response(
                {
                    "success": False,
                    "message": "Maximum 5 team members allowed (4 required + 1 optional substitute in separate field)",
                },
                status=400,
            )

        all_emails = [lead["email"]]
        member_emails = []

        for i, member in enumerate(members, 1):
            if not all(
                [member.get("name"), member.get("email"), member.get("contact")]
            ):
                return web.json_response(
                    {
                        "success": False,
                        "message": f"All fields for team member {i} are required",
                    },
                    status=400,
                )

            if not validate_email(member["email"]):
                return web.json_response(
                    {
                        "success": False,
                        "message": f"Invalid email format for team member {i}",
                    },
                    status=400,
                )

            if not validate_phone(member["contact"]):
                return web.json_response(
                    {
                        "success": False,
                        "message": f"Invalid phone number for team member {i}. Must be a valid 10-digit Indian number.",
                    },
                    status=400,
                )

            all_emails.append(member["email"])
            member_emails.append(member["email"])

        if substitute and any(
            [substitute.get("name"), substitute.get("email"), substitute.get("contact")]
        ):
            if not all(
                [
                    substitute.get("name"),
                    substitute.get("email"),
                    substitute.get("contact"),
                ]
            ):
                return web.json_response(
                    {
                        "success": False,
                        "message": "All substitute fields must be filled if any are provided",
                    },
                    status=400,
                )

            if not validate_email(substitute["email"]):
                return web.json_response(
                    {"success": False, "message": "Invalid substitute email format"},
                    status=400,
                )

            if not validate_phone(substitute["contact"]):
                return web.json_response(
                    {
                        "success": False,
                        "message": "Invalid substitute phone number. Must be a valid 10-digit Indian number.",
                    },
                    status=400,
                )

            all_emails.append(substitute["email"])

        is_duplicate, duplicate_email = await check_duplicate_emails(all_emails)
        if is_duplicate:
            return web.json_response(
                {
                    "success": False,
                    "message": f"Email {duplicate_email} is already registered in another team",
                },
                status=400,
            )

        all_contacts = [lead["contact"]] + [m["contact"] for m in members]
        if substitute and substitute.get("contact"):
            all_contacts.append(substitute["contact"])

        if len(all_contacts) != len(set(all_contacts)):
            return web.json_response(
                {
                    "success": False,
                    "message": "Duplicate phone numbers found. Each team member must have a unique phone number.",
                },
                status=400,
            )

        # Generate unique 4-digit team auth code
        team_auth_code = None
        max_attempts = 100
        for _ in range(max_attempts):
            candidate_code = f"{random.randint(0,9999):04d}"
            existing = await registrations.find_one({"team_auth_code": candidate_code})
            if not existing:
                team_auth_code = candidate_code
                break

        if team_auth_code is None:
            logger.error("Failed to generate unique team auth code after 100 attempts")
            return web.json_response(
                {
                    "success": False,
                    "message": "Unable to generate team code. Please try again.",
                },
                status=500,
            )

        registration_data = {
            "team_name": team_name,
            "college_name": college_name,
            "lead": {
                "name": lead["name"].strip(),
                "email": lead["email"].lower().strip(),
                "contact": lead["contact"].strip(),
            },
            "members": [
                {
                    "name": member["name"].strip(),
                    "email": member["email"].lower().strip(),
                    "contact": member["contact"].strip(),
                }
                for member in members
            ],
            "substitute": (
                {
                    "name": substitute.get("name", "").strip(),
                    "email": substitute.get("email", "").lower().strip(),
                    "contact": substitute.get("contact", "").strip(),
                }
                if substitute and substitute.get("name")
                else {}
            ),
            "ip_address": get_client_ip(request),
            "timestamp": datetime.utcnow(),
            "payment_status": "pending",
            "registration_id": f"AST{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}",
            "team_auth_code": team_auth_code,
        }

        try:
            await registrations.insert_one(registration_data)
            logger.info(f"New registration: {team_name} from IP {get_client_ip(request)}")
            
            # Send WhatsApp notification
            try:
                lead_phone = registration_data["lead"].get("contact")
                message = build_whatsapp_message(
                    "registration_success",
                    team_name=team_name,
                    auth_code=registration_data.get("team_auth_code"),
                    registration_id=registration_data.get("registration_id"),
                    amount=600,
                )
                await send_whatsapp(lead_phone, message)
            except Exception as e:
                logger.error(f"Failed to send WhatsApp on registration: {e}")
        except pymongo_errors.DuplicateKeyError:
            logger.error(f"Duplicate key error for team: {team_name}")
            return web.json_response(
                {
                    "success": False,
                    "message": "This team name or email is already registered. Please use a different team name or check your email addresses.",
                },
                status=400,
            )
        except Exception as mongo_error:
            logger.error(f"MongoDB error: {str(mongo_error)}")
            return web.json_response(
                {
                    "success": False,
                    "message": "Unable to complete registration due to a server issue. Please try again in a few moments. If the problem persists, contact support.",
                },
                status=500,
            )

        # Save to SQLite backup
        save_to_sqlite(registration_data)

        return web.json_response(
            {
                "success": True,
                "message": "Registration successful! Proceeding to payment...",
                "registration_id": registration_data["registration_id"],
                "team_name": team_name,
                "team_auth_code": registration_data["team_auth_code"],
                "total_members": len(members)
                + 1
                + (1 if registration_data["substitute"] else 0),
                "amount": 600,
            },
            status=200,
        )

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "message": "Something went wrong while processing your registration. Please check your information and try again. If the problem continues, contact support.",
            },
            status=500,
        )


# I'll continue with more endpoints in follow-up messages due to token limits
# This is a comprehensive start with the most critical components


async def get_teams(request: web.Request) -> web.Response:
    """Get all teams - exact behavior from Flask version"""
    try:
        auth_header = request.headers.get("X-Auth-Token", "")
        is_authenticated = auth_header == MASTER_PASSWORD
        team_auth_token = request.headers.get("X-Team-Auth", "")

        teams = []
        cursor = registrations.find(
            {},
            {
                "_id": 0,
                "team_name": 1,
                "college_name": 1,
                "lead.name": 1,
                "lead.contact": 1,
                "lead.email": 1,
                "members.name": 1,
                "members.contact": 1,
                "members.email": 1,
                "substitute.name": 1,
                "substitute.contact": 1,
                "substitute.email": 1,
                "payment_status": 1,
                "is_open": 1,
                "open_slots": 1,
                "join_requests": 1,
                "team_auth_code": 1,
            },
        ).sort("timestamp", -1)

        async for reg in cursor:
            is_team_lead_view = False
            try:
                is_team_lead_view = bool(
                    team_auth_token
                    and reg.get("team_auth_code")
                    and team_auth_token == reg.get("team_auth_code")
                )
            except Exception:
                is_team_lead_view = False

            def mask_phone(phone):
                if not phone:
                    return ""
                if is_authenticated or is_team_lead_view:
                    return phone
                return "••••••••••"

            def mask_name(name):
                if not name:
                    return ""
                if is_authenticated or is_team_lead_view:
                    return name
                return "••••••••"

            def mask_email(email):
                if not email:
                    return ""
                if is_authenticated or is_team_lead_view:
                    return email
                return "••••••••"

            substitute_data = reg.get("substitute", {})
            substitute = None
            if substitute_data and substitute_data.get("name"):
                substitute = {
                    "name": mask_name(substitute_data.get("name")),
                    "email": mask_email(substitute_data.get("email")),
                    "contact": mask_phone(substitute_data.get("contact")),
                }

            current_members_count = len(reg.get("members", []))
            calculated_open_slots = max(0, 5 - 1 - current_members_count)
           
            # Get join_requests (will be serialized later)
            join_requests_data = reg.get("join_requests", [])
           
            team_info = {
                "team_name": reg.get("team_name"),
                "college_name": reg.get("college_name"),
                "lead": {
                    "name": (
                        reg.get("lead", {}).get("name")
                        if reg.get("is_open")
                        else mask_name(reg.get("lead", {}).get("name"))
                    ),
                    "email": (
                        reg.get("lead", {}).get("email")
                        if reg.get("is_open")
                        else mask_email(reg.get("lead", {}).get("email"))
                    ),
                    "contact": mask_phone(reg.get("lead", {}).get("contact")),
                },
                "members": [
                    {
                        "name": mask_name(m.get("name")),
                        "email": mask_email(m.get("email")),
                        "contact": mask_phone(m.get("contact")),
                    }
                    for m in reg.get("members", [])
                ],
                "substitute": substitute,
                "payment_status": reg.get("payment_status"),
                "is_open": reg.get("is_open", False),
                "open_slots": calculated_open_slots,
                "pending_requests": (
                    len(
                        [
                            r
                            for r in join_requests_data
                            if r.get("status") == "pending"
                        ]
                    )
                    if join_requests_data
                    else 0
                ),
                "join_requests": (
                    join_requests_data
                    if (
                        is_authenticated
                        or (
                            team_auth_token
                            and reg.get("team_auth_code")
                            and team_auth_token == reg.get("team_auth_code")
                        )
                    )
                    else None
                ),
            }
            teams.append(team_info)
        
        # Serialize all datetime objects in the teams list
        teams = serialize_datetime(teams)
        
        return web.json_response({"success": True, "teams": teams}, status=200)
    except Exception as e:
        logger.error(f"Teams fetch error: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "message": "Unable to load teams at this moment. Please refresh the page or try again later.",
            },
            status=500,
        )


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint"""
    return web.json_response({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


# ============================================================================
# OPEN TEAM & JOIN REQUEST ENDPOINTS
# ============================================================================

async def create_open_team(request: web.Request) -> web.Response:
    """Create a team that is allowed to accept join requests (incomplete/open team)"""
    try:
        data = await request.json()
        if not data:
            return web.json_response({"success": False, "message": "Invalid payload"}, status=400)

        team_name = data.get("team_name", "").strip()
        lead = data.get("lead", {})
        members = data.get("members", []) or []

        if not team_name or not lead or not lead.get("name") or not lead.get("email") or not lead.get("contact"):
            return web.json_response(
                {
                    "success": False,
                    "message": "team_name and complete lead info are required",
                },
                status=400,
            )

        if not validate_team_name(team_name):
            return web.json_response({"success": False, "message": "Invalid team name"}, status=400)

        # Prevent duplicate team names for already completed teams
        if await registrations.find_one({"team_name": team_name, "payment_status": "completed"}):
            return web.json_response({"success": False, "message": "Team name already taken"}, status=400)

        # Basic validations
        if not validate_email(lead["email"]) or not validate_phone(lead["contact"]):
            return web.json_response({"success": False, "message": "Invalid lead contact/email"}, status=400)

        # Check duplicate emails across completed teams
        all_emails = [lead["email"]] + [m.get("email") for m in members if m.get("email")]
        is_dup, dup_email = await check_duplicate_emails(all_emails)
        if is_dup:
            return web.json_response(
                {
                    "success": False,
                    "message": f"Email {dup_email} already registered in another team",
                },
                status=400,
            )

        # Generate unique 4-digit team auth code
        team_auth_code = None
        max_attempts = 100
        for _ in range(max_attempts):
            candidate_code = f"{random.randint(0,9999):04d}"
            if not await registrations.find_one({"team_auth_code": candidate_code}):
                team_auth_code = candidate_code
                break

        if team_auth_code is None:
            logger.error("Failed to generate unique team auth code after 100 attempts")
            return web.json_response(
                {
                    "success": False,
                    "message": "Unable to generate team code. Please try again.",
                },
                status=500,
            )

        registration_data = {
            "team_name": team_name,
            "college_name": data.get("college_name", "").strip(),
            "lead": {
                "name": lead["name"].strip(),
                "email": lead["email"].lower().strip(),
                "contact": lead["contact"].strip(),
            },
            "members": [
                {
                    "name": m.get("name", "").strip(),
                    "email": m.get("email", "").lower().strip(),
                    "contact": m.get("contact", "").strip(),
                }
                for m in members
            ],
            "substitute": {},
            "ip_address": request.remote,
            "timestamp": datetime.utcnow(),
            "payment_status": "pending",
            "registration_id": f"AST{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}",
            "is_open": True,
            "team_auth_code": team_auth_code,
            "join_requests": [],
        }

        await registrations.insert_one(registration_data)
        await asyncio.get_event_loop().run_in_executor(None, save_to_sqlite, registration_data)
        logger.info(f"Open team created: {team_name}")

        # Notify team lead via WhatsApp
        try:
            lead_phone = registration_data["lead"].get("contact")
            message = build_whatsapp_message(
                "open_team_created",
                team_name=team_name,
                auth_code=registration_data.get("team_auth_code"),
            )
            await send_whatsapp(lead_phone, message)
        except Exception as e:
            logger.error(f"Failed to send WhatsApp on open team creation: {e}")

        # Calculate open slots
        open_slots = max(0, 5 - 1 - len(registration_data["members"]))

        return web.json_response(
            {
                "success": True,
                "message": "Team created and marked open",
                "team_name": team_name,
                "open_slots": open_slots,
                "team_auth_code": registration_data["team_auth_code"],
            },
            status=201,
        )
    except Exception as e:
        logger.error(f"create_open_team error: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "message": "Unable to create team at this moment. Please try again or contact support if the issue continues.",
            },
            status=500,
        )


async def submit_join_request(request: web.Request) -> web.Response:
    """Allow a user to request joining an open team"""
    try:
        data = await request.json()
        team_name = data.get("team_name", "").strip()
        requester = data.get("requester", {})

        if (
            not team_name
            or not requester
            or not requester.get("name")
            or not requester.get("email")
            or not requester.get("contact")
            or not requester.get("riot_id")
        ):
            return web.json_response(
                {
                    "success": False,
                    "message": "team_name and requester (name, email, contact, riot_id) are required",
                },
                status=400,
            )

        if not validate_email(requester["email"]) or not validate_phone(requester["contact"]):
            return web.json_response({"success": False, "message": "Invalid requester contact/email"}, status=400)

        team = await registrations.find_one({"team_name": team_name})
        if not team:
            return web.json_response({"success": False, "message": "Team not found"}, status=404)

        if not team.get("is_open"):
            return web.json_response({"success": False, "message": "Team is not open for join requests"}, status=400)

        # Check if team has space
        current_members = team.get("members", []) or []
        if len(current_members) >= 4:
            return web.json_response({"success": False, "message": "No open slots available"}, status=400)

        # Prevent duplicate registrations across completed teams
        dup, dup_email = await check_duplicate_emails([requester["email"]])
        if dup:
            return web.json_response(
                {
                    "success": False,
                    "message": f"Email {dup_email} already registered in another team",
                },
                status=400,
            )

        # Prevent duplicate requests or if already a member
        existing_members = [m.get("email") for m in team.get("members", [])]
        if (
            requester["email"].lower() in [e.lower() for e in existing_members]
            or requester["email"].lower() == team.get("lead", {}).get("email", "").lower()
        ):
            return web.json_response(
                {
                    "success": False,
                    "message": "Requester is already part of the team",
                },
                status=400,
            )

        for r in team.get("join_requests", []):
            if r.get("email", "").lower() == requester["email"].lower() and r.get("status") == "pending":
                return web.json_response(
                    {
                        "success": False,
                        "message": "You already have a pending request for this team",
                    },
                    status=400,
                )

        join_req = {
            "name": requester["name"].strip(),
            "email": requester["email"].lower().strip(),
            "contact": requester["contact"].strip(),
            "riot_id": requester["riot_id"].strip(),
            "timestamp": datetime.utcnow(),
            "status": "pending",
        }

        await registrations.update_one(
            {"team_name": team_name}, {"$push": {"join_requests": join_req}}
        )

        # Notify team lead via WhatsApp
        try:
            lead = team.get("lead", {})
            lead_phone = lead.get("contact")
            message = build_whatsapp_message(
                "join_request_received",
                team_name=team_name,
                name=join_req.get("name"),
                email=join_req.get("email"),
                contact=join_req.get("contact"),
                riot_id=join_req.get("riot_id"),
            )
            await send_whatsapp(lead_phone, message)
        except Exception as e:
            logger.error(f"Failed to send WhatsApp for join request: {e}")

        return web.json_response({"success": True, "message": "Join request submitted"}, status=200)
    except Exception as e:
        logger.error(f"submit_join_request error: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "message": "Unable to submit join request. Please try again or contact the team lead directly.",
            },
            status=500,
        )


async def respond_join_request(request: web.Request) -> web.Response:
    """Team lead or admin can accept/decline a join request"""
    try:
        data = await request.json()
        team_name = data.get("team_name", "").strip()
        requester_email = data.get("requester_email", "").strip().lower()
        action = data.get("action", "").strip().lower()
        lead_email = data.get("lead_email", "").strip().lower()

        if action not in ["accept", "decline"]:
            return web.json_response({"success": False, "message": "Invalid action"}, status=400)

        team = await registrations.find_one({"team_name": team_name})
        if not team:
            return web.json_response({"success": False, "message": "Team not found"}, status=404)

        # Authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        team_auth_header = request.headers.get("X-Team-Auth", "").strip()
        MASTER_PASSWORD = "0022"
        is_admin = auth_header == MASTER_PASSWORD
        is_lead = lead_email and lead_email == team.get("lead", {}).get("email", "").lower()
        is_team_auth = bool(team_auth_header and team_auth_header == team.get("team_auth_code"))

        if not (is_admin or is_lead or is_team_auth):
            return web.json_response(
                {
                    "success": False,
                    "message": "Unauthorized. Provide lead_email, team auth code, or admin token.",
                },
                status=401,
            )

        join_requests = team.get("join_requests", []) or []
        matched = None
        for jr in join_requests:
            if jr.get("email", "").lower() == requester_email:
                matched = jr
                break

        if not matched:
            return web.json_response({"success": False, "message": "Join request not found"}, status=404)

        if matched.get("status") != "pending":
            return web.json_response(
                {
                    "success": False,
                    "message": f'Request already {matched.get("status")}',
                },
                status=400,
            )

        # If accept: ensure slots available
        if action == "accept":
            current_members = team.get("members", []) or []
            if len(current_members) >= 4:
                return web.json_response({"success": False, "message": "No open slots available"}, status=400)

            # Add member
            new_member = {
                "name": matched.get("name"),
                "email": matched.get("email"),
                "contact": matched.get("contact"),
            }

            team["members"].append(new_member)
            # Close team if now full
            if len(team["members"]) >= 4:
                team["is_open"] = False

            # Update the matched request status
            for r in team["join_requests"]:
                if r.get("email", "").lower() == requester_email:
                    r["status"] = "accepted"
                    r["responded_at"] = datetime.utcnow()
                    break

            # Persist changes
            await registrations.update_one(
                {"team_name": team_name},
                {
                    "$set": {
                        "members": team["members"],
                        "is_open": team.get("is_open", False),
                        "join_requests": team["join_requests"],
                    }
                },
            )
            logger.info(f"Join request for {requester_email} accepted into {team_name}")
            
            # Notify requester via WhatsApp
            try:
                requester_phone = matched.get("contact")
                msg = build_whatsapp_message(
                    "join_request_accepted",
                    team_name=team_name,
                    name=matched.get("name"),
                )
                await send_whatsapp(requester_phone, msg)
            except Exception as e:
                logger.error(f"Failed to send WhatsApp to requester on accept: {e}")
            
            return web.json_response({"success": True, "message": "Request accepted"}, status=200)

        else:  # decline
            for r in team["join_requests"]:
                if r.get("email", "").lower() == requester_email:
                    r["status"] = "declined"
                    r["responded_at"] = datetime.utcnow()
                    break
            
            await registrations.update_one(
                {"team_name": team_name},
                {"$set": {"join_requests": team["join_requests"]}},
            )
            logger.info(f"Join request for {requester_email} declined for {team_name}")
            
            # Notify requester via WhatsApp
            try:
                requester_phone = matched.get("contact")
                msg = build_whatsapp_message(
                    "join_request_declined",
                    team_name=team_name,
                    name=matched.get("name"),
                )
                await send_whatsapp(requester_phone, msg)
            except Exception as e:
                logger.error(f"Failed to send WhatsApp to requester on decline: {e}")
            
            return web.json_response({"success": True, "message": "Request declined"}, status=200)

    except Exception as e:
        logger.error(f"respond_join_request error: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "message": "Unable to process join request response. Please refresh the page and try again.",
            },
            status=500,
        )


# ============================================================================
# TEAM AUTHENTICATION & MANAGEMENT ENDPOINTS
# ============================================================================

async def verify_key(request: web.Request) -> web.Response:
    """Verify master password for teams page access"""
    try:
        data = await request.json()
        password = data.get("password", "")

        MASTER_PASSWORD = "0022"

        if password == MASTER_PASSWORD:
            return web.json_response(
                {
                    "success": True,
                    "message": "Authentication successful",
                    "token": password,
                },
                status=200,
            )
        else:
            return web.json_response({"success": False, "message": "Invalid password"}, status=401)
    except Exception as e:
        logger.error(f"Key verification error: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "message": "Unable to verify password. Please try again.",
            },
            status=500,
        )


async def broadcast_whatsapp_to_teams(request: web.Request) -> web.Response:
    """Broadcast a WhatsApp message to all team leads"""
    try:
        # Verify admin authentication
        auth_token = request.headers.get("X-Auth-Token", "")
        if auth_token != MASTER_PASSWORD:
            return web.json_response(
                {"success": False, "message": "Unauthorized"},
                status=401
            )
        
        data = await request.json()
        message = data.get("message", "").strip()
        
        if not message:
            return web.json_response(
                {"success": False, "message": "Message is required"},
                status=400
            )
        
        # Get all registered teams
        teams_cursor = registrations.find({}, {
            "team_name": 1,
            "lead.name": 1,
            "lead.contact": 1
        })
        
        success_count = 0
        failed_count = 0
        results = []
        
        async for team in teams_cursor:
            team_name = team.get("team_name", "Unknown Team")
            lead = team.get("lead", {})
            lead_name = lead.get("name", "Team Lead")
            lead_phone = lead.get("contact", "")
            
            if not lead_phone:
                failed_count += 1
                results.append({
                    "team": team_name,
                    "status": "failed",
                    "reason": "No phone number"
                })
                continue
            
            try:
                # Format the message with team-specific greeting
                formatted_message = f"🎮 *ASTERISK 2025 - Official Announcement* 🎮\n\n"
                formatted_message += f"Hello {lead_name} ({team_name})!\n\n"
                formatted_message += message
                formatted_message += f"\n\n━━━━━━━━━━━━━━━\n"
                formatted_message += f"*ACM AJCE*\n"
                formatted_message += f"_This is an automated official broadcast from the ASTERISK tournament organizers_"
                
                # Send WhatsApp message
                sent = await send_whatsapp(lead_phone, formatted_message)
                
                if sent:
                    success_count += 1
                    results.append({
                        "team": team_name,
                        "status": "sent",
                        "phone": lead_phone[-4:]  # Last 4 digits only
                    })
                else:
                    failed_count += 1
                    results.append({
                        "team": team_name,
                        "status": "failed",
                        "reason": "Send failed"
                    })
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to send WhatsApp to {team_name}: {e}")
                failed_count += 1
                results.append({
                    "team": team_name,
                    "status": "failed",
                    "reason": str(e)
                })
        
        return web.json_response({
            "success": True,
            "message": f"Broadcast completed: {success_count} sent, {failed_count} failed",
            "total_sent": success_count,
            "total_failed": failed_count,
            "results": results
        }, status=200)
        
    except Exception as e:
        logger.error(f"Broadcast WhatsApp error: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "message": f"Broadcast failed: {str(e)}"
            },
            status=500
        )


async def verify_team_key(request: web.Request) -> web.Response:
    """Verify a team's 4-digit code"""
    try:
        data = await request.json()
        team_name = data.get("team_name", "").strip()
        code = data.get("code", "").strip()

        if not team_name or not code:
            return web.json_response(
                {"success": False, "message": "team_name and code are required"},
                status=400,
            )

        team = await registrations.find_one({"team_name": team_name})
        if not team:
            return web.json_response({"success": False, "message": "Team not found"}, status=404)

        if str(team.get("team_auth_code", "")).strip() == str(code).strip():
            return web.json_response(
                {
                    "success": True,
                    "message": "Team authentication successful",
                    "token": str(code).strip(),
                },
                status=200,
            )
        return web.json_response({"success": False, "message": "Invalid team code"}, status=401)
    except Exception as e:
        logger.error(f"verify_team_key error: {str(e)}")
        return web.json_response(
            {
                "success": False,
                "message": "Unable to verify team code. Please check your code and try again.",
            },
            status=500,
        )


async def verify_team_by_code(request: web.Request) -> web.Response:
    """Verify a team's 4-digit code without requiring team_name"""
    try:
        code = ""
        if request.method == "POST":
            data = await request.json()
            code = str(data.get("code", "")).strip()
        else:
            # GET
            code = str(request.query.get("code", "")).strip()

        if not code:
            return web.json_response({"success": False, "message": "code is required"}, status=400)

        team = await registrations.find_one({"team_auth_code": code})
        if not team:
            return web.json_response({"success": False, "message": "Invalid team code"}, status=404)

        return web.json_response(
            {
                "success": True,
                "message": "Team found",
                "team_name": team.get("team_name"),
                "token": code,
            },
            status=200,
        )
    except Exception as e:
        logger.error(f"verify_team_by_code error: {str(e)}")
        return web.json_response({"success": False, "message": "Internal server error"}, status=500)


async def get_team(request: web.Request) -> web.Response:
    """Get single team data with full unmasked info when authenticated"""
    try:
        team_name = ""
        if request.method == "POST":
            data = await request.json()
            team_name = data.get("team_name", "").strip()
        else:
            team_name = request.query.get("team_name", "").strip()

        if not team_name:
            return web.json_response({"success": False, "message": "team_name is required"}, status=400)

        team = await registrations.find_one({"team_name": team_name})
        if not team:
            return web.json_response({"success": False, "message": "Team not found"}, status=404)

        # Check authentication
        team_auth_token = request.headers.get("X-Team-Auth", "").strip()
        is_authenticated = bool(
            team_auth_token
            and team.get("team_auth_code")
            and team_auth_token == team.get("team_auth_code")
        )

        if not is_authenticated:
            return web.json_response(
                {
                    "success": False,
                    "message": "Invalid or missing team authentication",
                },
                status=401,
            )

        # Return full unmasked data
        substitute_data = team.get("substitute", {})
        substitute = None
        if substitute_data and substitute_data.get("name"):
            substitute = {
                "name": substitute_data.get("name"),
                "email": substitute_data.get("email", ""),
                "contact": substitute_data.get("contact"),
            }

        team_info = {
            "team_name": team.get("team_name"),
            "college_name": team.get("college_name"),
            "lead": {
                "name": team.get("lead", {}).get("name"),
                "email": team.get("lead", {}).get("email", ""),
                "contact": team.get("lead", {}).get("contact"),
            },
            "members": [
                {
                    "name": m.get("name"),
                    "email": m.get("email", ""),
                    "contact": m.get("contact"),
                }
                for m in team.get("members", [])
            ],
            "substitute": substitute,
            "payment_status": team.get("payment_status"),
            "is_open": bool(team.get("is_open", False)),
            "open_slots": int(team.get("open_slots", 0)),
            "join_requests": team.get("join_requests", []),
        }

        # Serialize datetime objects
        team_info = serialize_datetime(team_info)

        return web.json_response({"success": True, "team": team_info}, status=200)
    except Exception as e:
        logger.error(f"get_team error: {str(e)}")
        return web.json_response({"success": False, "message": "Internal server error"}, status=500)


async def toggle_team_open(request: web.Request) -> web.Response:
    """Toggle team open/closed status for join requests"""
    try:
        data = await request.json()
        team_name = data.get("team_name", "").strip()
        is_open = data.get("is_open")

        if not team_name:
            return web.json_response({"success": False, "message": "Team name is required"}, status=400)

        if is_open is None:
            return web.json_response({"success": False, "message": "is_open status is required"}, status=400)

        # Verify authentication
        team_auth = request.headers.get("X-Team-Auth", "")
        team = await registrations.find_one({"team_name": team_name})

        if not team:
            return web.json_response({"success": False, "message": "Team not found"}, status=404)

        is_authenticated = (team_auth == team.get("team_auth_code")) or (
            request.headers.get("X-Auth-Token") == "0022"
        )

        if not is_authenticated:
            return web.json_response({"success": False, "message": "Unauthorized"}, status=401)

        # Update is_open status
        await registrations.update_one(
            {"team_name": team_name}, {"$set": {"is_open": bool(is_open)}}
        )

        # Update SQLite backup (if column exists)
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sqlite3.connect("registrations_backup.db").cursor().execute(
                    "UPDATE registrations SET is_open = ? WHERE team_name = ?",
                    (1 if is_open else 0, team_name),
                )
            )
        except sqlite3.OperationalError as e:
            # Column doesn't exist in SQLite, skip backup update
            logger.warning(f"SQLite backup update skipped: {str(e)}")

        status_text = "open for join requests" if is_open else "closed for join requests"
        return web.json_response(
            {
                "success": True,
                "message": f"Team {status_text}",
                "is_open": bool(is_open),
            },
            status=200,
        )

    except Exception as e:
        logger.error(f"Error toggling team status: {e}")
        return web.json_response({"success": False, "message": "Internal server error"}, status=500)


async def remove_team_member(request: web.Request) -> web.Response:
    """Remove a member from the team (requires team auth, locked after payment)"""
    try:
        data = await request.json()
        team_name = data.get("team_name", "").strip()
        member_email = data.get("member_email", "").strip().lower()

        if not team_name or not member_email:
            return web.json_response(
                {
                    "success": False,
                    "message": "Team name and member email are required",
                },
                status=400,
            )

        # Verify authentication
        team_auth = request.headers.get("X-Team-Auth", "")
        team = await registrations.find_one({"team_name": team_name})

        if not team:
            return web.json_response({"success": False, "message": "Team not found"}, status=404)

        is_authenticated = (team_auth == team.get("team_auth_code")) or (
            request.headers.get("X-Auth-Token") == "0022"
        )

        if not is_authenticated:
            return web.json_response({"success": False, "message": "Unauthorized"}, status=401)

        # Check if payment is completed
        if team.get("payment_status") == "completed":
            return web.json_response(
                {
                    "success": False,
                    "message": "Cannot remove members after payment is completed",
                },
                status=403,
            )

        # Find and remove the member
        members = team.get("members", [])
        original_count = len(members)
        members = [m for m in members if m.get("email", "").lower() != member_email]

        if len(members) == original_count:
            return web.json_response({"success": False, "message": "Member not found"}, status=404)

        # Update team
        await registrations.update_one(
            {"team_name": team_name}, {"$set": {"members": members}}
        )

        # Update SQLite backup
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: sqlite3.connect("registrations_backup.db").cursor().execute(
                "UPDATE registrations SET members = ? WHERE team_name = ?",
                (json.dumps(members), team_name),
            )
        )

        logger.info(f"Member {member_email} removed from team {team_name}")
        return web.json_response({"success": True, "message": "Member removed successfully"}, status=200)

    except Exception as e:
        logger.error(f"Error removing member: {str(e)}")
        return web.json_response({"success": False, "message": "Internal server error"}, status=500)


async def update_payment_status(request: web.Request) -> web.Response:
    """Update payment status of a team (requires authentication)"""
    try:
        # Check authentication
        auth_header = request.headers.get("X-Auth-Token", "")
        MASTER_PASSWORD = "0022"

        if auth_header != MASTER_PASSWORD:
            return web.json_response({"success": False, "message": "Unauthorized"}, status=401)

        data = await request.json()
        team_name = data.get("team_name", "").strip()
        new_status = data.get("status", "").strip()

        if not team_name:
            return web.json_response({"success": False, "message": "Team name is required"}, status=400)

        if new_status not in ["pending", "completed"]:
            return web.json_response(
                {
                    "success": False,
                    "message": 'Invalid status. Must be "pending" or "completed"',
                },
                status=400,
            )

        # Fetch current team record
        team = await registrations.find_one({"team_name": team_name})
        if not team:
            return web.json_response({"success": False, "message": "Team not found"}, status=404)

        previous_status = team.get("payment_status", "pending")

        # Update MongoDB
        result = await registrations.update_one(
            {"team_name": team_name}, {"$set": {"payment_status": new_status}}
        )

        # Update SQLite backup
        await asyncio.get_event_loop().run_in_executor(
            None, update_payment_sqlite, team_name, new_status
        )

        logger.info(f"Payment status updated for team '{team_name}' to '{new_status}' by admin")

        # If transitioned to completed, send payment confirmation
        try:
            if previous_status != "completed" and new_status == "completed":
                updated_team = await registrations.find_one({"team_name": team_name}) or team
                lead_phone = updated_team.get("lead", {}).get("contact")
                registration_id = updated_team.get("registration_id")
                amount = 600

                # Message to lead
                lead_msg = build_whatsapp_message(
                    "payment_completed",
                    team_name=team_name,
                    registration_id=registration_id,
                    amount=amount,
                )
                if lead_phone:
                    await send_whatsapp(lead_phone, lead_msg)

                # Notify all team members
                try:
                    members = updated_team.get("members", [])
                    for m in members:
                        mphone = m.get("contact")
                        if mphone:
                            member_msg = f"✅ Payment received for team '{team_name}'. Your team is now fully registered."
                            await send_whatsapp(mphone, member_msg)
                except Exception:
                    logger.exception("Failed sending member payment notifications")
        except Exception as e:
            logger.error(f"Failed to send payment confirmation whatsapp: {e}")

        if result.modified_count == 0:
            return web.json_response(
                {
                    "success": True,
                    "message": f'Payment status is already set to "{new_status}"',
                },
                status=200,
            )

        return web.json_response(
            {
                "success": True,
                "message": f'Payment status updated to "{new_status}" successfully',
            },
            status=200,
        )

    except Exception as e:
        logger.error(f"Payment update error: {str(e)}")
        return web.json_response({"success": False, "message": "Internal server error"}, status=500)


# ============================================================================
# MIDDLEWARE - REQUEST/RESPONSE LOGGING
# ============================================================================

@web.middleware
async def logging_middleware(request: web.Request, handler):
    """Middleware to log all HTTP requests and responses"""
    # Skip logging OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return await handler(request)
    
    # Skip logging for spammy endpoints (SSE, polling endpoints)
    spammy_paths = [
        '/api/sse',
        '/api/stream-events',
        '/api/match-state',
        '/api/stream-state',
        '/api/viewer-count',
        '/api/viewer-ping'
    ]
    if any(request.path.startswith(path) for path in spammy_paths):
        return await handler(request)
    
    # Get client IP address
    # Check for forwarded IP first (if behind proxy)
    client_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if not client_ip:
        client_ip = request.headers.get('X-Real-IP', '')
    if not client_ip:
        client_ip = request.remote or 'unknown'
    
    # Log request
    request_time = datetime.utcnow()
    method = request.method
    path = request.path
    query_string = f"?{request.query_string}" if request.query_string else ""
    user_agent = request.headers.get('User-Agent', 'unknown')
    
    # Log incoming request
    http_logger.info(
        f"→ {method} {path}{query_string} | IP: {client_ip} | User-Agent: {user_agent[:100]}"
    )
    
    # Call the handler and catch any errors
    try:
        response = await handler(request)
        status = response.status
        
        # Calculate request duration
        duration = (datetime.utcnow() - request_time).total_seconds() * 1000  # milliseconds
        
        # Log response
        http_logger.info(
            f"← {method} {path} | IP: {client_ip} | Status: {status} | Duration: {duration:.2f}ms"
        )
        
        return response
    except web.HTTPException as ex:
        # HTTP exceptions (like 404, 500)
        duration = (datetime.utcnow() - request_time).total_seconds() * 1000
        http_logger.warning(
            f"← {method} {path} | IP: {client_ip} | Status: {ex.status} | Duration: {duration:.2f}ms | Error: {ex.reason}"
        )
        raise
    except Exception as ex:
        # Unexpected errors
        duration = (datetime.utcnow() - request_time).total_seconds() * 1000
        http_logger.error(
            f"← {method} {path} | IP: {client_ip} | Status: 500 | Duration: {duration:.2f}ms | Error: {str(ex)}"
        )
        raise

lap_times = db.lap_times
def init_lap_times_sqlite():
    conn = sqlite3.connect('lap_times_backup.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lap_times (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            time REAL NOT NULL,
            place TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

async def get_lap_times(request: web.Request) -> web.Response:
    """Get all lap times sorted by time ascending"""
    try:
        laps = []
        async for lap in lap_times.find().sort("time", 1):
            lap['_id'] = str(lap['_id'])
            laps.append(lap)
        
        laps = serialize_datetime(laps)
        
        return web.json_response({
            "success": True,
            "lap_times": laps
        })
    except Exception as e:
        logger.error(f"Get lap times error: {e}")
        return web.json_response({
            "success": False,
            "message": "Error fetching lap times"
        }, status=500)

async def add_lap_time(request: web.Request) -> web.Response:
    """Add new lap time (admin only)"""
    try:
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        data = await request.json()
        name = data.get("name")
        time = data.get("time")
        place = data.get("place")
        
        if not name or time is None:
            return web.json_response({
                "success": False,
                "message": "name and time required"
            }, status=400)
        
        lap_data = {
            "name": name,
            "time": float(time),
            "place": place,
            "timestamp": datetime.utcnow()
        }
        
        result = await lap_times.insert_one(lap_data)
        lap_data['_id'] = str(result.inserted_id)
        
        lap_data = serialize_datetime(lap_data)
        
        # Backup to SQLite
        conn = sqlite3.connect('lap_times_backup.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO lap_times (name, time, place, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (name, float(time), place, lap_data['timestamp']))
        conn.commit()
        conn.close()
        
        # Broadcast to SSE clients
        await broadcast_sse_event("lap_updated", lap_data)
        
        return web.json_response({
            "success": True,
            "message": "Lap time added",
            "lap": lap_data
        })
    except Exception as e:
        logger.error(f"Add lap time error: {e}")
        return web.json_response({
            "success": False,
            "message": "Error adding lap time"
        }, status=500)

async def update_lap_time(request: web.Request) -> web.Response:
    """Update an existing lap time (admin only)"""
    try:
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        lap_id = request.match_info['id']
        data = await request.json()
        name = data.get("name")
        time = data.get("time")
        place = data.get("place")
        
        if not name or time is None:
            return web.json_response({
                "success": False,
                "message": "name and time required"
            }, status=400)
        
        update_data = {
            "name": name,
            "time": float(time),
            "place": place,
            "timestamp": datetime.utcnow()
        }
        
        result = await lap_times.update_one(
            {"_id": ObjectId(lap_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            return web.json_response({
                "success": False,
                "message": "Lap time not found or no changes made"
            }, status=404)
        
        # Update SQLite backup
        conn = sqlite3.connect('lap_times_backup.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE lap_times
            SET name = ?, time = ?, place = ?, timestamp = ?
            WHERE id = ?
        ''', (name, float(time), place, update_data['timestamp'].isoformat(), lap_id))
        conn.commit()
        conn.close()
        
        # Broadcast to SSE clients
        update_data['_id'] = lap_id
        update_data = serialize_datetime(update_data)
        await broadcast_sse_event("lap_updated", update_data)
        
        return web.json_response({
            "success": True,
            "message": "Lap time updated"
        })
    except Exception as e:
        logger.error(f"Update lap time error: {e}")
        return web.json_response({
            "success": False,
            "message": "Error updating lap time"
        }, status=500)

# Delete lap time
async def delete_lap_time(request: web.Request) -> web.Response:
    """Delete a lap time (admin only)"""
    try:
        auth_header = request.headers.get("X-Auth-Token", "")
        if auth_header != MASTER_PASSWORD:
            return web.json_response({
                "success": False,
                "message": "Unauthorized"
            }, status=401)
        
        lap_id = request.match_info['id']
        
        result = await lap_times.delete_one({"_id": ObjectId(lap_id)})
        
        if result.deleted_count == 0:
            return web.json_response({
                "success": False,
                "message": "Lap time not found"
            }, status=404)
        
        # Update SQLite backup
        conn = sqlite3.connect('lap_times_backup.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM lap_times WHERE id = ?', (lap_id,))
        conn.commit()
        conn.close()
        
        # Broadcast to SSE clients
        await broadcast_sse_event("lap_updated", {"id": lap_id})
        
        return web.json_response({
            "success": True,
            "message": "Lap time deleted"
        })
    except Exception as e:
        logger.error(f"Delete lap time error: {e}")
        return web.json_response({
            "success": False,
            "message": "Error deleting lap time"
        }, status=500)

# ============================================================================
# APPLICATION SETUP
# ============================================================================

async def init_app():
    """Initialize application"""
    logger.info("=" * 80)
    logger.info("Initializing Application Components")
    logger.info("=" * 80)
    
    logger.info("Initializing SQLite backup database...")
    init_sqlite()
    logger.info("✓ SQLite backup database ready")

    init_lap_times_sqlite()
    # Create index for lap_times
    await lap_times.create_index([("time", 1)])
    
    # Create indexes
    logger.info("Creating MongoDB indexes...")
    try:
        await registrations.create_index([("team_name", 1)], unique=True)
        await registrations.create_index([("team_auth_code", 1)], unique=True, sparse=True)
        await registrations.create_index([("members.email", 1)], unique=True, sparse=True)
        await registrations.create_index([("payment_status", 1)])
        await registrations.create_index([("is_open", 1)])
        await registrations.create_index([("timestamp", -1)])
        logger.info("✓ All MongoDB indexes created successfully")
    except Exception as e:
        logger.warning(f"⚠ Could not create some indexes: {e}")
    
    # Test MongoDB connection
    try:
        await registrations.find_one()
        logger.info("✓ MongoDB connection verified")
    except Exception as e:
        logger.error(f"✗ MongoDB connection failed: {e}")
    
    # Initialize matches if not present
    try:
        match_count = await matches_collection.count_documents({})
        if match_count == 0:
            logger.info("No matches found - initializing qualifier matches...")
            # Tournament Structure:
            # - Date: October 16, 2025 (Thursday PM)
            # - Round of 18: 18 teams, 9 matches
            # - Advancement: 9 winning teams + 1 losing team with highest score = 10 teams
            # - Quarterfinals: 10 teams → 5 matches
            baseline_matches = [
                # 9:00 PM Matches (Court A-E)
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 1,
                    "team1": "LavaLoon",
                    "team2": "Log Bait",
                    "team1_seed": 1,
                    "team2_seed": 2,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "A",
                    "time_slot": "9:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 2,
                    "team1": "XLr8",
                    "team2": "EXODUS",
                    "team1_seed": 3,
                    "team2_seed": 4,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "B",
                    "time_slot": "9:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 3,
                    "team1": "Hardstuck",
                    "team2": "GODS OWN COUNTRY",
                    "team1_seed": 5,
                    "team2_seed": 6,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "C",
                    "time_slot": "9:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 4,
                    "team1": "Hestia",
                    "team2": "ULTF4",
                    "team1_seed": 7,
                    "team2_seed": 8,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "D",
                    "time_slot": "9:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 5,
                    "team1": "BLACKLISTED",
                    "team2": "Spike Rushers",
                    "team1_seed": 9,
                    "team2_seed": 10,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "E",
                    "time_slot": "9:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                # 10:00 PM Matches (Court A-D)
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 6,
                    "team1": "Esports Division NITC Alpha",
                    "team2": "Go Lose Fast",
                    "team1_seed": 11,
                    "team2_seed": 12,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "A",
                    "time_slot": "10:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 7,
                    "team1": "LABWUBWU",
                    "team2": "Binary Legion",
                    "team1_seed": 13,
                    "team2_seed": 14,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "B",
                    "time_slot": "10:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 8,
                    "team1": "Targaryens",
                    "team2": "Renegades",
                    "team1_seed": 15,
                    "team2_seed": 16,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "C",
                    "time_slot": "10:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "round": "Round of 18",
                    "round_number": 1,
                    "match_number": 9,
                    "team1": "DNA",
                    "team2": "Vitality",
                    "team1_seed": 17,
                    "team2_seed": 18,
                    "winner": None,
                    "team1_score": 0,
                    "team2_score": 0,
                    "status": "pending",
                    "is_active": False,
                    "court": "D",
                    "time_slot": "10:00 PM",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            ]
            result = await matches_collection.insert_many(baseline_matches)
            logger.info(f"✓ Initialized {len(result.inserted_ids)} qualifier matches")
        else:
            logger.info(f"✓ Found {match_count} existing matches")
    except Exception as e:
        logger.warning(f"⚠ Could not initialize matches: {e}")
    
    logger.info("=" * 80)
    logger.info("Application Ready")
    logger.info("=" * 80)



def create_app() -> web.Application:
    """Create and configure the aiohttp application"""
    # Create app with logging middleware
    app = web.Application(middlewares=[logging_middleware])
    
    logger.info("Initializing aiohttp application...")
    
    # Setup CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    logger.info("CORS configured for all origins")
    
    # Add routes
    app.router.add_get('/', index)
    app.router.add_get('/reg.html', registration_page)
    app.router.add_get('/team.html', team_dashboard_page)
    app.router.add_get('/teams.html', teams_list_page)
    app.router.add_get('/matchlineup.html', matchlineup_page)
    app.router.add_get('/live.html', live_page)
    app.router.add_get('/stream-control.html', stream_control_page)
    app.router.add_get('/dash-control.html', dash_control_page)
    app.router.add_get('/game.html', game_page)
    
    app.router.add_post('/register', register_team)
    app.router.add_get('/teams', get_teams)
    app.router.add_get('/health', health_check)
    
    # SSE endpoint
    app.router.add_get('/api/sse', sse_handler)
    
    # Match management endpoints
    app.router.add_get('/api/matches', get_matches)
    app.router.add_post('/api/matches', create_match)
    app.router.add_put('/api/matches/{match_id}', update_match)
    app.router.add_delete('/api/matches/{match_id}', delete_match)
    
    # Tournament control panel endpoints
    app.router.add_post('/api/tournament/initialize', initialize_tournament_bracket)
    app.router.add_post('/api/tournament/set-active-match', set_active_match)
    app.router.add_post('/api/tournament/advance-winners', advance_winners)
    app.router.add_post('/api/tournament/advance-team', advance_team_to_round)
    app.router.add_post('/api/tournament/set-winner', set_match_winner)
    app.router.add_get('/api/tournament/stats', get_tournament_stats)
    app.router.add_get('/api/tournament/advancement', get_advancement_status)
    app.router.add_get('/api/tournament/best-loser', get_best_loser)
    app.router.add_get('/control.html', control_panel_page)
    
    # Live streaming endpoints
    app.router.add_get('/api/match-state', get_stream_state)
    app.router.add_get('/api/stream-state', get_stream_state)  # Alias
    app.router.add_post('/api/update-score', update_stream_score)
    app.router.add_post('/api/update-teams', update_stream_teams)
    app.router.add_post('/api/update-match-info', update_stream_match_info)
    app.router.add_post('/api/reset', reset_stream_match)
    app.router.add_post('/api/control/start-match', trigger_match_start)
    app.router.add_post('/api/control/end-match', trigger_match_end)
    app.router.add_post('/api/control/show-pause', show_pause_screen)
    app.router.add_post('/api/control/hide-pause', hide_pause_screen)
    app.router.add_get('/api/stream-events', stream_sse_handler)
    app.router.add_post('/api/send-chat', send_stream_chat)
    app.router.add_get('/api/viewer-count', get_stream_viewer_count)
    app.router.add_post('/api/ingress-server', update_ingress_server)
    app.router.add_get('/api/ingress-server', get_ingress_server)
    app.router.add_get('/api/lap-times', get_lap_times)
    app.router.add_post('/api/lap-times', add_lap_time)
    app.router.add_put('/api/lap-times/{id}', update_lap_time)
    app.router.add_delete('/api/lap-times/{id}', delete_lap_time)
    
    # Team Stats & Pause Screen routes
    app.router.add_get('/api/team-stats', get_team_stats)
    app.router.add_post('/api/team-stats', update_team_stats)
    app.router.add_delete('/api/team-stats', delete_team_stats)
    app.router.add_post('/api/pause-screen', toggle_pause_screen)
    
    # Open team & join request endpoints
    app.router.add_post('/create-team', create_open_team)
    app.router.add_post('/team/join-request', submit_join_request)
    app.router.add_post('/team/respond-join', respond_join_request)
    
    # Team authentication endpoints
    app.router.add_post('/key', verify_key)
    app.router.add_post('/team/key', verify_team_key)
    app.router.add_get('/team/verify-code', verify_team_by_code)
    app.router.add_post('/team/verify-code', verify_team_by_code)
    
    # Team management endpoints
    app.router.add_get('/get-team', get_team)
    app.router.add_post('/get-team', get_team)
    app.router.add_post('/team/toggle-open', toggle_team_open)
    app.router.add_post('/team/remove-member', remove_team_member)
    
    # Broadcast WhatsApp endpoint
    app.router.add_post('/api/broadcast-whatsapp', broadcast_whatsapp_to_teams)
    
    # Payment management endpoint
    app.router.add_post('/update-payment', update_payment_status)
    
    logger.info("Routes registered successfully")
    
    # Configure CORS on all routes
    for route in list(app.router.routes()):
        cors.add(route)
    
    # Count routes by method
    route_count = {}
    for route in app.router.routes():
        method = route.method
        route_count[method] = route_count.get(method, 0) + 1
    
    logger.info(f"Total routes configured: {sum(route_count.values())}")
    for method, count in sorted(route_count.items()):
        logger.info(f"  {method}: {count} routes")
    
    # Startup hook
    app.on_startup.append(lambda app: init_app())
    
    logger.info("Application initialization complete")
    
    return app


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("Starting ASTRISK Tournament System Server")
    logger.info("=" * 80)
    logger.info("Creating application instance...")
    
    app = create_app()
    
    logger.info("Server configuration:")
    logger.info("  Host: 0.0.0.0")
    logger.info("  Port: 5002")
    logger.info("  Database: MongoDB (async with motor)")
    logger.info("  Backup: SQLite (registrations_backup.db)")
    logger.info("  Logs: astrisk_app.log, astrisk_http.log")
    logger.info("=" * 80)
    logger.info("Server starting... Press Ctrl+C to stop")
    logger.info("=" * 80)
    
    try:
        web.run_app(app, host='0.0.0.0', port=5002, access_log=None)  # Disable default access log
    except KeyboardInterrupt:
        logger.info("=" * 80)
        logger.info("Server shutdown requested")
        logger.info("=" * 80)
    finally:
        logger.info("Server stopped")
