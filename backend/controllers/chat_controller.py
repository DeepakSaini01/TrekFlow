import os
import json
import re
from flask import Blueprint, request, jsonify
from backend.models import Trek, Status
from backend import db

chat_bp = Blueprint("chat_bp", __name__, url_prefix="/api")


def _read_site_settings():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    settings_path = os.path.join(base_dir, "site_settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "about_us": "TrekFlow connects passionate trekkers with professional trek leaders across India.",
        "contact_email": "support@trekflow.com",
        "contact_phone": "+91 98765 43210",
        "how_it_works": [
            {"step": 1, "title": "Browse Treks", "desc": "Explore open expeditions."},
            {"step": 2, "title": "Book & Pay", "desc": "Reserve your spot online."},
            {"step": 3, "title": "Trek & Conquer", "desc": "Join your group and summit!"}
        ]
    }


def _get_active_treks():
    treks = Trek.query.filter(Trek.status.in_([Status.Open, Status.Approved])).all()
    if not treks:
        treks = Trek.query.all()
    return [t.to_dict() for t in treks]


def _call_gemini_if_configured(prompt):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        if res.status_code == 200:
            data = res.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        pass
    return None


@chat_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"reply": "Please send a message to get started!", "recommended_treks": []}), 400

    low_msg = user_msg.lower()
    treks = _get_active_treks()
    settings = _read_site_settings()

    # Check if Gemini API key is present for smart AI response
    if os.getenv("GEMINI_API_KEY"):
        prompt = (
            f"You are the TrekFlow AI Guide for our trekking booking website. "
            f"Help the user politely and concisely based on our actual site data.\n\n"
            f"Active Treks Data:\n{json.dumps(treks, indent=2)}\n\n"
            f"Site Info:\n{json.dumps(settings, indent=2)}\n\n"
            f"User Question: {user_msg}\n\n"
            f"Provide a helpful, friendly, and structured reply. If recommending treks, mention their names, prices, difficulty, and available slots."
        )
        ai_reply = _call_gemini_if_configured(prompt)
        if ai_reply:
            # Match treks mentioned in AI reply for cards
            matched = [t for t in treks if t["name"].lower() in ai_reply.lower()]
            return jsonify({"reply": ai_reply, "recommended_treks": matched[:3]}), 200

    # Smart Rule-Based Engine (Instant, Offline, Zero API keys needed)
    recommended = []

    # 1. Greetings
    if re.search(r"\b(hi|hello|hey|namaste|greetings|hola)\b", low_msg) and len(low_msg.split()) <= 4:
        reply = (
            f"👋 Hello! Welcome to **TrekFlow**! I can help you find the perfect trek, "
            f"check prices, dates, difficulty levels, or guide you on how to book.\n\n"
            f"What kind of trek are you looking for today?"
        )
        return jsonify({"reply": reply, "recommended_treks": treks[:3]}), 200

    # 2. How to book / Booking process
    if any(k in low_msg for k in ["how to book", "booking process", "book a trek", "how does it work", "how it works"]):
        steps = settings.get("how_it_works", [])
        steps_text = "\n".join([f"**Step {s.get('step')}: {s.get('title')}** - {s.get('desc')}" for s in steps])
        reply = (
            f"Here is how simple it is to book on TrekFlow:\n\n{steps_text}\n\n"
            f"💡 *Tip: Make sure you have created a Trekker account and are logged in before clicking 'Book Now'!*"
        )
        return jsonify({"reply": reply, "recommended_treks": []}), 200

    # 3. Contact / Support
    if any(k in low_msg for k in ["contact", "phone", "email", "support", "call", "address", "location"]):
        email = settings.get("contact_email", "support@trekflow.com")
        phone = settings.get("contact_phone", "+91 98765 43210")
        address = settings.get("contact_address", "TrekFlow Base Camp")
        reply = (
            f"You can reach the TrekFlow team anytime:\n"
            f"- 📧 **Email:** {email}\n"
            f"- 📞 **Phone:** {phone}\n"
            f"- 📍 **Address:** {address}\n\n"
            f"We are here to assist you with trek preparation, gear, and booking questions!"
        )
        return jsonify({"reply": reply, "recommended_treks": []}), 200

    # 4. Price & Budget queries
    budget_match = re.search(r"(under|below|less than|budget|cheap|affordable)\s*(?:rs\.?|inr|₹)?\s*(\d+)", low_msg)
    if budget_match or any(k in low_msg for k in ["cheap", "budget", "cost", "price", "affordable", "least expensive"]):
        max_price = float(budget_match.group(2)) if budget_match and budget_match.group(2) else None
        if max_price:
            matched = [t for t in treks if (t.get("price") or 0) <= max_price]
            if matched:
                reply = f"Here are the treks available under **₹{int(max_price):,}**:"
                recommended = matched
            else:
                cheapest = sorted(treks, key=lambda x: x.get("price") or 0)[:2]
                reply = f"We don't have open treks under ₹{int(max_price):,}, but here are our most affordable options:"
                recommended = cheapest
        else:
            sorted_treks = sorted(treks, key=lambda x: x.get("price") or 0)
            recommended = sorted_treks[:3]
            reply = "Here are our most budget-friendly expeditions:"
        return jsonify({"reply": reply, "recommended_treks": recommended}), 200

    # 5. Difficulty level matching (Easy / Moderate / Hard)
    if "easy" in low_msg or "beginner" in low_msg:
        recommended = [t for t in treks if str(t.get("difficulty", "")).lower() == "easy"]
        reply = "Here are our **Easy / Beginner-friendly** treks perfect for starting your trekking journey:" if recommended else "Currently all open treks are Moderate or Hard. Check them out:"
        if not recommended:
            recommended = treks[:2]
        return jsonify({"reply": reply, "recommended_treks": recommended}), 200

    if "hard" in low_msg or "difficult" in low_msg or "challenging" in low_msg:
        recommended = [t for t in treks if str(t.get("difficulty", "")).lower() == "hard"]
        reply = "Here are our **Challenging / High-Altitude** treks for experienced trekkers:" if recommended else "Here are our available treks:"
        if not recommended:
            recommended = treks[:2]
        return jsonify({"reply": reply, "recommended_treks": recommended}), 200

    if "moderate" in low_msg:
        recommended = [t for t in treks if str(t.get("difficulty", "")).lower() == "moderate"]
        reply = "Here are our **Moderate difficulty** treks offering a balanced thrill:" if recommended else "Here are our available treks:"
        if not recommended:
            recommended = treks[:2]
        return jsonify({"reply": reply, "recommended_treks": recommended}), 200

    # 6. Specific Trek Search by Name / Location
    for t in treks:
        t_name = t.get("name", "").lower()
        t_loc = t.get("location", "").lower()
        if t_name in low_msg or (t_loc and t_loc in low_msg):
            recommended.append(t)

    if recommended:
        t = recommended[0]
        stops = ", ".join(t.get("major_stops", [])) if t.get("major_stops") else "Scenic Himalayan trails"
        reply = (
            f"Here are the details for **{t.get('name')}**:\n"
            f"- 📍 **Location:** {t.get('location')}\n"
            f"- 💰 **Price:** ₹{t.get('price', 0):,}\n"
            f"- ⏱️ **Duration:** {t.get('duration')} Days\n"
            f"- 🏔️ **Difficulty:** {str(t.get('difficulty')).capitalize()}\n"
            f"- 🎟️ **Available Slots:** {t.get('available_slot')} spots remaining\n"
            f"- 🗺️ **Major Stops:** {stops}\n"
            f"- 📅 **Dates:** {t.get('start_date')} to {t.get('end_date')}\n\n"
            f"{t.get('description', '')}"
        )
        return jsonify({"reply": reply, "recommended_treks": recommended[:3]}), 200

    # 7. Generic Trek Recommendation / Available treks
    if any(k in low_msg for k in ["trek", "recommend", "show", "available", "list", "options", "which"]):
        reply = (
            f"We currently have **{len(treks)}** active trekking expedition(s) ready for booking! "
            f"Here are some top recommendations:"
        )
        return jsonify({"reply": reply, "recommended_treks": treks[:3]}), 200

    # Default fallback
    reply = (
        f"I'm here to help with all TrekFlow details! You can ask me:\n"
        f"- *'Show easy treks for beginners'*\n"
        f"- *'Which treks are under ₹5,000?'*\n"
        f"- *'How does booking work?'*\n"
        f"- *'What are the dates and slots for treks?'*\n\n"
        f"Here are a few popular treks to check out:"
    )
    return jsonify({"reply": reply, "recommended_treks": treks[:2]}), 200
