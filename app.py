# app.py - Updated with Phone/MPIN Authentication
import os
import traceback
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from dotenv import load_dotenv
from agents.orchestrator import Orchestrator
from auth import AuthService

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))
CORS(app, supports_credentials=True)

orchestrator = Orchestrator()
auth_service = AuthService()

# ========================================
# STATIC PAGES
# ========================================

@app.route("/")
def serve_home():
    """Serve login page"""
    return send_from_directory("static", "login.html")

@app.route("/chat_page")
def serve_chat():
    """Serve chat interface"""
    return send_from_directory("static", "chat.html")


# ========================================
# AUTHENTICATION ENDPOINTS
# ========================================

@app.route("/login", methods=["POST"])
def login():
    """
    Login with phone number and MPIN
    Body: { "phone": "+15551234567", "mpin": "0000" }
    """
    try:
        data = request.get_json() or {}
        phone = data.get("phone", "").strip()
        mpin = data.get("mpin", "").strip()
        
        if not phone or not mpin:
            return jsonify({
                "success": False,
                "error": "Phone number and MPIN are required"
            }), 400
        
        # Authenticate
        result = auth_service.authenticate(phone, mpin)
        
        if not result["success"]:
            return jsonify(result), 401
        
        # Create session
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        session_id = auth_service.create_session(
            result["phone"], 
            ip_address, 
            user_agent
        )
        
        if not session_id:
            return jsonify({
                "success": False,
                "error": "Failed to create session"
            }), 500
        
        # Get user accounts
        accounts = auth_service.get_user_accounts(result["phone"])
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "phone": result["phone"],
            "name": result["name"],
            "accounts": accounts,
            "message": result["message"]
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": "login_failed",
            "exception": str(e),
            "trace": tb
        }), 500


@app.route("/logout", methods=["POST"])
def logout():
    """Logout and destroy session"""
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")
        
        if session_id:
            auth_service.logout(session_id)
        
        return jsonify({"success": True, "message": "Logged out successfully"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/verify_session", methods=["POST"])
def verify_session():
    """Verify if session is still valid"""
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")
        
        if not session_id:
            return jsonify({"valid": False, "error": "session_id required"}), 400
        
        result = auth_service.verify_session(session_id)
        
        if result["valid"]:
            return jsonify(result)
        else:
            return jsonify(result), 401
            
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500


# ========================================
# CHAT ENDPOINT
# ========================================

@app.route("/chat", methods=["POST"])
def chat():
    """
    Multi-agent chatbot with session-based authentication
    Body: { "session_id": "...", "message": "..." }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")
        message = data.get("message")
        
        if not session_id or not message:
            return jsonify({
                "success": False,
                "error": "session_id and message required"
            }), 400
        
        # Verify session
        session_data = auth_service.verify_session(session_id)
        
        if not session_data["valid"]:
            return jsonify({
                "success": False,
                "error": "Invalid or expired session",
                "session_expired": True
            }), 401
        
        phone = session_data["phone"]
        
        # Process with orchestrator using phone number
        result = orchestrator.process_query(phone, message, session_id)
        
        return jsonify(result)
        
    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": "chat_failed",
            "exception": str(e),
            "trace": tb
        }), 500


@app.route("/get_user_context", methods=["POST"])
def get_user_context():
    """
    Get user financial context (for debugging)
    Body: { "session_id": "..." }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")
        
        if not session_id:
            return jsonify({"error": "session_id required"}), 400
        
        # Verify session
        session_data = auth_service.verify_session(session_id)
        
        if not session_data["valid"]:
            return jsonify({"error": "Invalid session"}), 401
        
        # Get context from database tools
        from tools.database_tools import DatabaseTools
        db_tools = DatabaseTools()
        context = db_tools.get_user_context(session_data["phone"])
        
        return jsonify(context)
        
    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({
            "error": "context_fetch_failed",
            "exception": str(e),
            "trace": tb
        }), 500


@app.route("/clear_conversation", methods=["POST"])
def clear_conversation():
    """Clear conversation history for a session"""
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")
        
        if not session_id:
            return jsonify({"error": "session_id required"}), 400
        
        # Verify session first
        session_data = auth_service.verify_session(session_id)
        
        if not session_data["valid"]:
            return jsonify({"error": "Invalid session"}), 401
        
        orchestrator.clear_conversation(session_id)
        
        return jsonify({"success": True, "message": "Conversation cleared"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========================================
# HEALTH CHECK
# ========================================

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "auth_type": "phone_mpin",
        "database": os.getenv("SQL_DATABASE")
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)