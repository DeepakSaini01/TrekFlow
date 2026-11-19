import os
import json
import re
import requests
from pathlib import Path
from flask import Blueprint, request, jsonify
from backend.models import Trek, Status
from backend import db

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

chatbot_bp = Blueprint("chatbot_bp", __name__, url_prefix="/api")


def _read_site_settings():
    """Reads About Us, Contact, and How-it-works from site_settings.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    settings_path = os.path.join(base_dir, "site_settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "about_us": "TrekFlow connects passionate trekkers with certified trek leaders for unforgettable Himalayan expeditions.",
        "contact_email": "support@trekflow.com",
        "contact_phone": "+91 98765 43210",
        "contact_address": "TrekFlow Base Camp, Manali, Himachal Pradesh, India",
        "how_it_works": [
            {"step": 1, "title": "Browse Treks", "desc": "Explore handpicked expeditions filtered by difficulty and dates."},
            {"step": 2, "title": "Reserve Your Slot", "desc": "Sign in as a Trekker and lock your spot with instant booking."},
            {"step": 3, "title": "Prep & Summit", "desc": "Receive automated gear checklists, join your group leader, and summit!"}
        ]
    }


def _get_active_treks():
    """Fetches all open or approved treks from SQLite"""
    treks = Trek.query.filter(Trek.status.in_([Status.Open, Status.Approved])).all()
    if not treks:
        treks = Trek.query.all()
    return [t.to_dict() for t in treks]


def _call_groq_api(user_message, treks, settings):
    """Calls Groq Cloud API with available models on the account"""
    groq_api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY")
    if not groq_api_key:
        return None

    system_prompt = (
        "You are 'TrekFlow AI', an enthusiastic, expert Himalayan mountain guide and booking assistant for TrekFlow.\n\n"
        "OBJECTIVES:\n"
        "1. Give engaging, inspiring, and concise advice tailored to the user's question.\n"
        "2. ONLY recommend treks that actually exist in the PROVIDED TREKS DATABASE below. Never invent fake treks.\n"
        "3. Format your response with clean Markdown: bold headers, bullet points, and appropriate emojis (🏔️, 💰, ⏱️, 🎒, 📍).\n"
        "4. When suggesting a trek, always state its Name, Location, Price (in ₹), Difficulty, Duration, and available slots.\n"
        "5. Provide practical mountain tips when relevant (preparation, fitness, packing, season).\n"
        "6. Keep replies concise, friendly, and action-oriented.\n\n"
        f"--- LIVE SITE TREKS DATABASE ---\n{json.dumps(treks, indent=2)}\n\n"
        f"--- COMPANY & BOOKING INFO ---\n{json.dumps(settings, indent=2)}\n"
    )

    # Models verified on this Groq account
    models_to_try = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "allam-2-7b"
    ]

    headers = {
        "Authorization": f"Bearer {groq_api_key.strip()}",
        "Content-Type": "application/json"
    }

    url = "https://api.groq.com/openai/v1/chat/completions"

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.6,
            "max_tokens": 600
        }
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=8)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                print(f"Groq ({model}) status:", res.status_code, res.text[:120])
        except Exception as e:
            print("Groq Error:", e)
            continue

    return None


@chatbot_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_msg = (data.get("message") or "").strip()

    if not user_msg:
        return jsonify({"reply": "Hello! I am your TrekFlow Guide. How can I help you plan your next mountain adventure?", "recommended_treks": []}), 400

    low_msg = user_msg.lower()
    treks = _get_active_treks()
    settings = _read_site_settings()

    # 1. Try Groq AI
    ai_reply = _call_groq_api(user_msg, treks, settings)

    # If Groq generated an answer, return it with matching trek cards
    if ai_reply:
        matched = [t for t in treks if t["name"].lower() in ai_reply.lower()]
        return jsonify({"reply": ai_reply, "recommended_treks": matched[:3]}), 200

    # 2. Enhanced Built-in Guide Engine (Offline / Fallback)
    recommended = []

    if re.search(r"\b(hi|hello|hey|namaste|greetings|hola)\b", low_msg) and len(low_msg.split()) <= 4:
        reply = (
            "🏔️ **Namaste & Welcome to TrekFlow!**\n\n"
            "I'm your personal expedition guide. Whether you're a first-time hiker looking for gentle trails or a seasoned summit chaser, I'm here to help!\n\n"
            "**Here are a few things you can ask me:**\n"
            "- *'What are the best treks for beginners?'*\n"
            "- *'Show me budget treks under ₹5,000'*\n"
            "- *'What should I pack for a high-altitude trek?'*\n"
            "- *'How does the booking process work?'*"
        )
        return jsonify({"reply": reply, "recommended_treks": treks[:3]}), 200

    if any(k in low_msg for k in ["pack", "gear", "backpack", "shoes", "clothes", "what to bring", "checklist"]):
        reply = (
            "🎒 **Essential Trekking Packing Checklist:**\n\n"
            "- 🥾 **Footwear:** Broken-in trekking shoes with deep lug soles + 3-4 pairs of wool socks.\n"
            "- 🧥 **Layering:** Thermal base layer, fleece mid-layer, and a wind/waterproof down jacket.\n"
            "- 🔦 **Accessories:** LED headlamp with extra batteries, UV sunglasses, and trekking poles.\n"
            "- 💧 **Hydration:** 2L reusable water bladder or thermos + water purification tablets.\n"
            "- 🩹 **Safety:** Personal first-aid kit, blister tape, and altitude medications."
        )
        return jsonify({"reply": reply, "recommended_treks": []}), 200

    if any(k in low_msg for k in ["how to book", "booking", "reserve", "how it works", "payment"]):
        steps = settings.get("how_it_works", [])
        steps_text = "\n".join([f"**Step {s.get('step')}: {s.get('title')}**\n{s.get('desc')}" for s in steps])
        reply = f"📅 **How Easy It Is to Book on TrekFlow:**\n\n{steps_text}\n\n💡 **Pro-Tip:** Sign in as a **Trekker** before checkout to view your itinerary anytime!"
        return jsonify({"reply": reply, "recommended_treks": []}), 200

    if any(k in low_msg for k in ["contact", "phone", "email", "support", "call", "address"]):
        email = settings.get("contact_email", "support@trekflow.com")
        phone = settings.get("contact_phone", "+91 98765 43210")
        address = settings.get("contact_address", "TrekFlow Base Camp")
        reply = f"📞 **TrekFlow Support:**\n\n- 📧 **Email:** {email}\n- 📱 **Phone:** {phone}\n- 📍 **Base Camp:** {address}"
        return jsonify({"reply": reply, "recommended_treks": []}), 200

    budget_match = re.search(r"(under|below|less than|budget|cheap|affordable)\s*(?:rs\.?|inr|₹)?\s*(\d+)", low_msg)
    if budget_match or any(k in low_msg for k in ["cheap", "budget", "cost", "price", "affordable"]):
        max_price = float(budget_match.group(2)) if budget_match and budget_match.group(2) else None
        if max_price:
            matched = [t for t in treks if (t.get("price") or 0) <= max_price]
            if matched:
                reply = f"💰 **Great Budget Picks Under ₹{int(max_price):,}**:"
                recommended = matched
            else:
                cheapest = sorted(treks, key=lambda x: x.get("price") or 0)[:2]
                reply = f"We currently don't have open expeditions under ₹{int(max_price):,}. Here are our **most affordable available treks**:"
                recommended = cheapest
        else:
            sorted_treks = sorted(treks, key=lambda x: x.get("price") or 0)
            recommended = sorted_treks[:3]
            reply = "💰 **Most Affordable TrekFlow Expeditions:**"
        return jsonify({"reply": reply, "recommended_treks": recommended}), 200

    if "easy" in low_msg or "beginner" in low_msg:
        recommended = [t for t in treks if str(t.get("difficulty", "")).lower() == "easy"]
        reply = "🌱 **Best Treks for Beginners & First-Timers:**"
        return jsonify({"reply": reply, "recommended_treks": recommended or treks[:2]}), 200

    if "hard" in low_msg or "difficult" in low_msg or "challenging" in low_msg:
        recommended = [t for t in treks if str(t.get("difficulty", "")).lower() == "hard"]
        reply = "🏔️ **High-Altitude & Thrilling Challenges for Experienced Trekkers:**"
        return jsonify({"reply": reply, "recommended_treks": recommended or treks[:2]}), 200

    if "moderate" in low_msg:
        recommended = [t for t in treks if str(t.get("difficulty", "")).lower() == "moderate"]
        reply = "⚖️ **Moderate Difficulty Treks (The Perfect Balance):**"
        return jsonify({"reply": reply, "recommended_treks": recommended or treks[:2]}), 200

    for t in treks:
        if t.get("name", "").lower() in low_msg or (t.get("location") and t.get("location").lower() in low_msg):
            recommended.append(t)

    if recommended:
        t = recommended[0]
        stops = ", ".join(t.get("major_stops", [])) if t.get("major_stops") else "Scenic Himalayan passes"
        reply = (
            f"🏔️ **Expedition Overview: {t.get('name')}**\n\n"
            f"- 📍 **Location:** {t.get('location')}\n"
            f"- 💰 **Price:** ₹{t.get('price', 0):,} per trekker\n"
            f"- ⏱️ **Duration:** {t.get('duration')} Days\n"
            f"- 🧗 **Difficulty:** {str(t.get('difficulty')).capitalize()}\n"
            f"- 🎟️ **Available Slots:** {t.get('available_slot')} spots remaining\n"
            f"- 🗺️ **Trail Stops:** {stops}\n"
            f"- 📅 **Departure Dates:** {t.get('start_date')} to {t.get('end_date')}\n\n"
            f"{t.get('description', '')}"
        )
        return jsonify({"reply": reply, "recommended_treks": recommended[:3]}), 200

    reply = f"🏔️ We currently have **{len(treks)} active expedition(s)** ready for booking! Here are our top recommendations:"
    return jsonify({"reply": reply, "recommended_treks": treks[:3]}), 200
