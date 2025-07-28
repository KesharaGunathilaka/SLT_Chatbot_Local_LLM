import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
# from llm_groq import query_groq as query_llm
from llm_ollama import query_ollama as query_llm
from vector_store import query_similar_docs

app = Flask(__name__)
user_sessions = {}
CORS(app)

# Load Data
try:
    with open("data/branches.json", encoding="utf8") as f:
        BRANCHES = json.load(f)
    with open("data/index.json", encoding="utf8") as f:
        INDEX = json.load(f)
    print(f"✅ Loaded {len(INDEX)} scraped pages and {len(BRANCHES)} branches.")
except Exception as e:
    print(f"❌ Error loading data: {e}")
    BRANCHES, INDEX = [], {}


#  Search & Scoring Logic
def score_relevance(query, data):
    query_words = query.lower().split()
    text = data.get("text", "").lower()
    if "ocr_images" in data:
        text += " " + " ".join(img["text"].lower()
                               for img in data["ocr_images"])
    return sum(text.count(word) for word in query_words)


def find_relevant_pages(query, top_n=3):
    results = query_similar_docs(query, top_k=top_n)
    return [(1, id_, {"text": doc}) for id_, doc in zip(results["ids"][0], results["documents"][0])]


def convert_links_to_html(text):
    # Turn any plain URL into clickable link
    url_pattern = re.compile(r'(https?://[^\s)]+)')
    return url_pattern.sub(r'<a href="\1" target="_blank" rel="noopener noreferrer" class="text-blue-600 underline">\1</a>', text)


#  Location Handling
def find_nearest_branches(user_coords, branches, top_n=3):
    distances = []
    for branch in branches:
        dist = geodesic(
            user_coords, (branch["latitude"], branch["longitude"])).km
        distances.append((branch, dist))
    return sorted(distances, key=lambda x: x[1])[:top_n]


def format_branch(branch, dist_km):
    lines = [f"📍 **{branch['name']}** – approx. {dist_km:.2f} km away"]
    if branch.get("address"):
        lines.append(f"🏠 Address: {branch['address']}")
    if branch.get("phone"):
        lines.append(f"📞 Phone: {branch['phone']}")
    if branch.get("email"):
        lines.append(f"📧 Email: {branch['email']}")
    return "\n".join(lines)


def location_response(user_input):
    try:
        geolocator = Nominatim(user_agent="slt-location-finder")

        if "near me" in user_input.lower() or user_input.strip().lower() in ["me", "here", "my location"]:
            return "📍 Please tell me your city to find nearby SLT branches. For example: 'Find branches near Kandy'"

        location = geolocator.geocode(f"{user_input}, Sri Lanka")
        if not location:
            return "❌ Sorry, I couldn't find that location. Please try with a nearby city or town."

        user_coords = (location.latitude, location.longitude)
        nearest = find_nearest_branches(user_coords, BRANCHES)

        response = [
            f"📌 Your location: **{location.address}**",
            "\n🏢 **Here are the nearest SLT branches:**\n"
        ]
        for branch, dist in nearest:
            response.append(format_branch(branch, dist))
            response.append("")
        response.append(
            "🔗 For more: [SLT Branch Locator](https://www.slt.lk/en/contact-us/branch-locator/our-locations/our-network)")
        return "\n".join(response)

    except Exception as e:
        return f"❌ Location detection error: {str(e)}"


# Main Chat Endpoint
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_input = data.get("message", "").strip().lower()
        user_id = "default"  # placeholder, use real user ID or session in future

        if not user_input:
            return jsonify({"error": "❌ Empty message provided."}), 400

        # 1. Casual chat
        casual_replies = {
            "hello": "👋 Hello! How can I help you today?",
            "hi": "Hi there! 😊 Ask me anything about SLT services.",
            "thanks": "🙏 You're welcome!",
            "thank you": "Happy to help! 😊",
            "bye": "👋 Goodbye! Have a great day.",
        }
        if user_input in casual_replies:
            return jsonify({"reply": casual_replies[user_input]})

        # 2. If waiting for city name
        if user_sessions.get(user_id) == "awaiting_city":
            user_sessions[user_id] = None
            response = location_response(user_input)
            return jsonify({"reply": response})

        # 3. Ask for city if vague query like "near me"
        if "near me" in user_input or user_input in ["me", "my location", "near"]:
            user_sessions[user_id] = "awaiting_city"
            return jsonify({"reply": "📍 Sure! Please tell me your city name (e.g., Colombo, Kandy, or Galle)."})

        # 4. Exact city name based lookup
        for branch in BRANCHES:
            name_lower = branch["name"].lower()
            if name_lower in user_input:
                lines = [f"📍 SLT Branch: **{branch['name']}**"]
                if "contact" in user_input or "phone" in user_input:
                    lines.append(
                        f"📞 Phone: {branch.get('phone', 'Not available')}")
                if "email" in user_input:
                    lines.append(
                        f"📧 Email: {branch.get('email', 'Not available')}")
                if "address" in user_input or "location" in user_input:
                    lines.append(
                        f"🏠 Address: {branch.get('address', 'Not available')}")
                if len(lines) > 1:
                    return jsonify({"reply": "\n".join(lines)})

        # 5. Generic branch/location query
        location_keywords = ["branch", "location",
                             "coverage", "area", "office"]
        if any(k in user_input for k in location_keywords):
            return jsonify({"reply": location_response(user_input)})

        # 6. General Q&A via LLaMA
        pages = find_relevant_pages(user_input)
        if not pages:
            return jsonify({"reply": "❌ I couldn't find relevant information. Try rephrasing your question."})

        context_blocks = []
        for _, url, data in pages:
            summary = data.get("text", "")
            ocr_list = data.get("ocr_images", [])
            ocr_summary = "\n".join(
                [f"- {img['src'].split('/')[-1]}: {img['text']}" for img in ocr_list[:3]])
            block = f"🔗 Page: {url}\n📄 Text: {summary[:1000]}\n🖼️ OCR: {ocr_summary[:500]}"
            context_blocks.append(block)

        full_context = "\n\n---\n\n".join(context_blocks)

        prompt = f"""
You are an expert assistant for Sri Lanka Telecom (SLT), helping users with their questions based on official content from www.slt.lk.

🧑 User Question:
{user_input}

🗂️ Extracted Context:
{full_context}

🎯 Instructions:
- Provide a clear, helpful answer based on this context.
- Use bullet points, emojis, or short paragraphs if useful.
- Always include the source SLT webpage URL (from the context) when possible.
- Format links like this: [Visit Page](https://www.slt.lk/...)
- If no answer is possible, say so kindly.

Answer:
"""
        answer = query_llm(prompt)
        return jsonify({"reply": convert_links_to_html(answer)})

    except Exception as e:
        return jsonify({"error": f"❌ Server error: {str(e)}"}), 500


# Health Check Route

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "✅ SLT Chatbot is running",
        "scraped_pages": len(INDEX),
        "branches_loaded": len(BRANCHES)
    })


# Start Flask
if __name__ == "__main__":
    print("🚀 SLT Assistant API starting...")
    app.run(host="0.0.0.0", port=5000, debug=True)
