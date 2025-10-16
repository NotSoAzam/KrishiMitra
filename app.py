from dotenv import load_dotenv
load_dotenv()

import os
import base64
import traceback
from flask import Flask, request, jsonify
import requests
import google.generativeai as genai
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load API keys from environment variables
PLANT_ID_API_KEY = os.getenv("PLANT_ID_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

print("Debug: Loaded PLANT_ID_API_KEY:", PLANT_ID_API_KEY is not None)
print("Debug: Loaded GOOGLE_API_KEY:", GOOGLE_API_KEY is not None)

if not PLANT_ID_API_KEY or not GOOGLE_API_KEY:
    raise EnvironmentError("API keys for Plant.ID and Google must be set in environment variables.")

# Configure Google Generative AI model
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Manual translations for labels
TRANSLATIONS = {
    "general_name": {"hi": "सामान्य नाम", "te": "సాధారణ పేరు"},
    "soil":        {"hi": "उपयुक्त मिट्टी", "te": "భూడ్ సరైన రకం"},
    "fertilizer":  {"hi": "उर्वरक अनुशंसा", "te": "ఎరువు సిఫార్సు"},
    "pesticide":   {"hi": "कीटनाशक अनुशंसा", "te": "పురుగు నాశక సూచనలు"}
}

@app.route("/identify-pest", methods=["POST"])
def identify_pest():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        image = request.files["image"]
        image_bytes = image.read()
        print(f"Debug: Received image size {len(image_bytes)} bytes")

        base64_img = base64.b64encode(image_bytes).decode('utf-8')

        # Use minimal request body to avoid modifier issues
        plant_id_url = "https://plant.id/api/v3/identification"
        headers = {
            "Content-Type": "application/json",
            "Api-Key": PLANT_ID_API_KEY
        }
        body = {"images": [f"data:image/jpeg;base64,{base64_img}"]}

        plant_response = requests.post(plant_id_url, json=body, headers=headers)
        print("Debug: Plant.ID API status:", plant_response.status_code)

        if plant_response.status_code not in [200, 201]:
            return jsonify({"error": "Plant.ID API failed", "details": plant_response.text}), 500

        plant_data = plant_response.json()
        print("Debug: Plant.ID response keys:", list(plant_data.keys()))

        # Extract plant suggestion
        try:
            if "result" in plant_data and "classification" in plant_data["result"]:
                suggestions = plant_data["result"]["classification"]["suggestions"]
                if suggestions:
                    suggestion = suggestions[0]["name"]
                else:
                    return jsonify({"error": "No plant suggestions found"}), 400
            elif "suggestions" in plant_data:
                suggestion = plant_data["suggestions"][0]["plant_name"]
            else:
                return jsonify({"error": "Unexpected Plant.ID response format"}), 400
            print("Debug: Plant suggestion:", suggestion)
        except Exception as e:
            print("Debug: Error parsing Plant.ID response:", e)
            return jsonify({"error": "Could not parse Plant.ID response"}), 400

        # Generate English advice using Google Gemini
        chat = model.start_chat()
        base_instruction = "Answer briefly and concisely."
        advice_en = {
            "general_name": chat.send_message(f"{base_instruction} General name of crop: {suggestion}").text.strip(),
            "soil":         chat.send_message(f"{base_instruction} What soil is better suited for {suggestion}?").text.strip(),
            "fertilizer":   chat.send_message(f"{base_instruction} Type and amount of fertilizer recommended for {suggestion}").text.strip(),
            "pesticide":    chat.send_message(f"{base_instruction} Type and amount of pesticide recommended for controlling {suggestion}").text.strip()
        }
        print("Debug: Advice generated (EN):", advice_en)

        # Build translated advice
        advice = {
            "general_name": advice_en["general_name"],
            "soil":         advice_en["soil"],
            "fertilizer":   advice_en["fertilizer"],
            "pesticide":    advice_en["pesticide"],
            # Add Hindi and Telugu entries
            "general_name_hi": f"{TRANSLATIONS['general_name']['hi']}: {advice_en['general_name']}",
            "soil_hi":         f"{TRANSLATIONS['soil']['hi']}: {advice_en['soil']}",
            "fertilizer_hi":   f"{TRANSLATIONS['fertilizer']['hi']}: {advice_en['fertilizer']}",
            "pesticide_hi":    f"{TRANSLATIONS['pesticide']['hi']}: {advice_en['pesticide']}",
            "general_name_te": f"{TRANSLATIONS['general_name']['te']}: {advice_en['general_name']}",
            "soil_te":         f"{TRANSLATIONS['soil']['te']}: {advice_en['soil']}",
            "fertilizer_te":   f"{TRANSLATIONS['fertilizer']['te']}: {advice_en['fertilizer']}",
            "pesticide_te":    f"{TRANSLATIONS['pesticide']['te']}: {advice_en['pesticide']}"
        }

        return jsonify(advice)

    except Exception as e:
        print("Error in /identify-pest:", e)
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

@app.route("/pest-advice", methods=["POST"])
def pest_advice():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        pest_name = data.get("pest_name")
        print("Debug: Received pest_name:", pest_name)
        if not pest_name:
            return jsonify({"error": "Pest name missing"}), 400

        chat = model.start_chat()
        base_instruction = "Answer briefly and concisely."
        advice_en = {
            "general_name": chat.send_message(f"{base_instruction} General name of crop: {pest_name}").text.strip(),
            "soil":         chat.send_message(f"{base_instruction} What soil is better suited for {pest_name}?").text.strip(),
            "fertilizer":   chat.send_message(f"{base_instruction} Type and amount of fertilizer recommended for {pest_name}").text.strip(),
            "pesticide":    chat.send_message(f"{base_instruction} Type and amount of pesticide recommended for controlling {pest_name}").text.strip()
        }
        print("Debug: Advice generated for pest (EN):", advice_en)

        # Build translated advice
        advice = {
            "general_name": advice_en["general_name"],
            "soil":         advice_en["soil"],
            "fertilizer":   advice_en["fertilizer"],
            "pesticide":    advice_en["pesticide"],
            "general_name_hi": f"{TRANSLATIONS['general_name']['hi']}: {advice_en['general_name']}",
            "soil_hi":         f"{TRANSLATIONS['soil']['hi']}: {advice_en['soil']}",
            "fertilizer_hi":   f"{TRANSLATIONS['fertilizer']['hi']}: {advice_en['fertilizer']}",
            "pesticide_hi":    f"{TRANSLATIONS['pesticide']['hi']}: {advice_en['pesticide']}",
            "general_name_te": f"{TRANSLATIONS['general_name']['te']}: {advice_en['general_name']}",
            "soil_te":         f"{TRANSLATIONS['soil']['te']}: {advice_en['soil']}",
            "fertilizer_te":   f"{TRANSLATIONS['fertilizer']['te']}: {advice_en['fertilizer']}",
            "pesticide_te":    f"{TRANSLATIONS['pesticide']['te']}: {advice_en['pesticide']}"
        }

        return jsonify(advice)

    except Exception as e:
        print("Error in /pest-advice:", e)
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500
@app.route('/weather-farming-suggestions', methods=['POST'])
def weather_farming_suggestions():
    try:
        data = request.get_json()
        if not data or 'latitude' not in data or 'longitude' not in data:
            return jsonify({"error": "Latitude and longitude must be provided"}), 400

        lat = data['latitude']
        lon = data['longitude']

        # Call Open-Meteo API for current weather and hourly data
        url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}' \
              f'&current_weather=true&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,pressure_msl'
        weather_response = requests.get(url)
        if weather_response.status_code != 200:
            return jsonify({"error": "Failed to fetch weather data"}), 500

        weather_data = weather_response.json()
        current_weather = weather_data.get('current_weather')
        
        if 'hourly' in weather_data:
            hourly_data = weather_data['hourly']
            hourly_times = hourly_data.get('time', [])
            hourly_temps = hourly_data.get('temperature_2m', [])
        else:
            hourly_times = []
            hourly_temps = []

        if not current_weather:
            return jsonify({"error": "Current weather data not available"}), 500

        temp_c = current_weather.get('temperature')
        windspeed = current_weather.get('windspeed')

        hourly = weather_data.get('hourly', {})
        humidity_list = hourly.get('relative_humidity_2m', [])
        pressure_list = hourly.get('pressure_msl', [])
        humidity = humidity_list[0] if humidity_list else None
        pressure = pressure_list[0] if pressure_list else None

        # Compose AI prompt for farming suggestions
        chat = model.start_chat()
        chat.send_message("You are an expert agricultural advisor providing practical farming tips.")

       # Prepare a short summary of the temperature forecast for AI prompt
        forecast_summary = ""
        forecast_count = min(6, len(hourly_times), len(hourly_temps))
        for i in range(forecast_count):
            time_str = hourly_times[i]
            temp_val = hourly_temps[i]
            forecast_summary += f"{time_str}: {temp_val}°C; "

        prompt = (
            f"Given the current weather at latitude {lat} and longitude {lon} with temperature {temp_c}°C, "
            f"humidity {humidity}%, the next hours' temperature forecast is as follows: {forecast_summary.strip()} "
            f"Please suggest 3 farming tips or actions best suited for these conditions."
            f"Only 3 tips. Small and concise. Nothing else."
        )

        ai_response = chat.send_message(prompt)

        return jsonify({
            "temperature": temp_c,
            "hourly_times": hourly_times,
            "hourly_temperature": hourly_temps,
            "farming_suggestions": ai_response.text
        })

    except Exception as e:
        print(f"Error in /weather-farming-suggestions: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/gemini-chat', methods=['POST'])
def gemini_chat():
    try:
        data = request.get_json()
        if not data or 'user_message' not in data:
            return jsonify({"error": "Missing 'user_message' in request"}), 400

        user_message = data['user_message'].strip()
        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        # Start Gemini chat session, no base instruction (or provide one if you want)
        chat = model.start_chat()

        # Send user message to Gemini
        response = chat.send_message(user_message)

        # Return AI chat reply to frontend
        return jsonify({"reply": response.text})

    except Exception as e:
        print(f"Error in /gemini-chat: {e}")
        return jsonify({"error": "Internal server error"}), 500




if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

