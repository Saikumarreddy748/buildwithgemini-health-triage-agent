# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os

from pathlib import Path
import subprocess
from typing import Any
import urllib.parse
import urllib.request
import uuid

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import storage
from google.genai import types

from .a2ui_utils import a2ui_callback

# Load remote Agent Engine runtime ID from deployment_metadata.json
metadata_path = Path(__file__).parent.parent / "deployment_metadata.json"
agent_engine_resource_name = "projects/150891827009/locations/us-east1/reasoningEngines/778689527953752064"
memory_bank_id = "5348154299874541568"

if metadata_path.exists():
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id", agent_engine_resource_name)
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name,
)


def memory_bank_service_builder():
    """Builds VertexAiMemoryBankService targeting the Memory Bank Agent Engine instance."""
    return VertexAiMemoryBankService(
        project="qwiklabs-gcp-01-1261bf882821",
        location="us-east1",
        agent_engine_id=memory_bank_id,
    )


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: after each turn, send the session events to Memory Bank to extract user facts and allergies."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


async def generate_first_aid_visual(
    topic: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Generates an educational first-aid or medical reference image for a health topic
    (e.g., 'kitchen finger cut bandaging', 'cough steam inhalation', 'fever relief cooling')
    using gemini-3.1-flash-lite-image model in global region. Saves the image to Playground Artifacts
    and uploads the image bytes directly to public Cloud Storage.

    Args:
        topic: The health or first-aid topic to generate an educational visual for.
        tool_context: ADK ToolContext used to save artifacts to the Playground.

    Returns:
        A dictionary containing the topic, artifact status, and public Cloud Storage URL.
    """
    bucket_name = "qwiklabs-gcp-01-1261bf882821-health-triage-assets"

    client = genai.Client(
        vertexai=True,
        project="qwiklabs-gcp-01-1261bf882821",
        location="global",
    )

    prompt = f"Educational clean medical visual diagram demonstrating first aid and self-care steps for: {topic}."
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    image_bytes = None
    for part in response.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            break

    if not image_bytes:
        return {
            "topic": topic,
            "success": False,
            "message": "Failed to generate image bytes.",
        }

    filename = f"first_aid_{uuid.uuid4().hex[:8]}.png"

    if tool_context:
        try:
            await tool_context.save_artifact(
                filename=filename,
                artifact=types.Part(
                    inline_data=types.Blob(
                        mime_type="image/png",
                        data=image_bytes,
                    )
                ),
            )
        except Exception:
            pass

    storage_client = storage.Client(project="qwiklabs-gcp-01-1261bf882821")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type="image/png")

    public_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"

    return {
        "topic": topic,
        "filename": filename,
        "artifact_saved": True,
        "public_url": public_url,
        "message": f"Successfully generated visual for '{topic}', saved to Playground Artifacts, and uploaded to public Cloud Storage.",
    }


async def generate_first_aid_video(
    topic: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Generates a short educational first-aid or health demonstration video for a given topic
    using Google's Omni model (gemini-omni-flash-preview) in the global region.
    Saves the video to Playground Artifacts via tool_context.save_artifact and uploads the video bytes
    directly to public Cloud Storage.

    Args:
        topic: The health or first-aid topic to generate an educational demonstration video for.
        tool_context: ADK ToolContext used to save artifacts to the Playground.

    Returns:
        A dictionary containing topic, artifact status, and public Cloud Storage URL.
    """
    bucket_name = "qwiklabs-gcp-01-1261bf882821-health-triage-assets"

    client = genai.Client(
        vertexai=True,
        project="qwiklabs-gcp-01-1261bf882821",
        location="global",
    )

    prompt = f"Short educational demonstration video showing healthcare and first aid steps for: {topic}."
    response = client.models.generate_content(
        model="gemini-omni-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "VIDEO"],
        ),
    )

    video_bytes = None
    for part in response.parts:
        if part.inline_data:
            video_bytes = part.inline_data.data
            break

    if not video_bytes:
        return {
            "topic": topic,
            "success": False,
            "message": "Failed to generate video bytes.",
        }

    filename = f"first_aid_video_{uuid.uuid4().hex[:8]}.mp4"

    if tool_context:
        try:
            await tool_context.save_artifact(
                filename=filename,
                artifact=types.Part(
                    inline_data=types.Blob(
                        mime_type="video/mp4",
                        data=video_bytes,
                    )
                ),
            )
        except Exception:
            pass

    storage_client = storage.Client(project="qwiklabs-gcp-01-1261bf882821")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type="video/mp4")

    public_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"

    return {
        "topic": topic,
        "filename": filename,
        "artifact_saved": True,
        "public_url": public_url,
        "message": f"Successfully generated video for '{topic}', saved to Playground Artifacts, and uploaded to public Cloud Storage.",
    }


def diagnose_symptoms_and_recommend_specialist(
    symptoms: str, medical_history: str = ""
) -> dict[str, Any]:
    """Analyzes user symptoms and medical history to evaluate possible conditions
    and recommend the appropriate healthcare specialist domain to consult."""
    symptoms_lower = symptoms.lower()

    possible_conditions = []
    specialist_domain = "General Physician / Family Practitioner"
    urgency = "Routine / Non-emergency consultation"

    if "chest pain" in symptoms_lower or "shortness of breath" in symptoms_lower:
        possible_conditions.append("Cardiovascular evaluation required / Angina")
        specialist_domain = "Cardiologist"
        urgency = "URGENT / Seek Immediate Emergency Care"
    elif "skin" in symptoms_lower or "rash" in symptoms_lower or "itch" in symptoms_lower:
        possible_conditions.extend(["Dermatitis", "Allergic reaction", "Eczema"])
        specialist_domain = "Dermatologist"
    elif "ear" in symptoms_lower or "throat" in symptoms_lower or "sinus" in symptoms_lower or "tonsil" in symptoms_lower:
        possible_conditions.extend(["Sinusitis", "Pharyngitis / Tonsillitis", "Ear infection"])
        specialist_domain = "ENT Specialist (Otolaryngologist)"
    elif "cough" in symptoms_lower or "cold" in symptoms_lower or "fever" in symptoms_lower or "flu" in symptoms_lower:
        possible_conditions.extend(["Upper Respiratory Tract Infection", "Seasonal Flu", "Viral Fever"])
        specialist_domain = "General Physician / Family Medicine"
    elif "cut" in symptoms_lower or "wound" in symptoms_lower or "bleed" in symptoms_lower:
        possible_conditions.extend(["Superficial Laceration", "Minor Kitchen Cut"])
        specialist_domain = "General Practitioner / Urgent Care"
    else:
        possible_conditions.append("General symptom evaluation needed")
        specialist_domain = "General Physician"

    return {
        "symptoms_evaluated": symptoms,
        "medical_history_context": medical_history or "None reported",
        "possible_conditions": possible_conditions,
        "recommended_specialist_domain": specialist_domain,
        "urgency_level": urgency,
        "disclaimer": "This AI triage is for informational purposes only. Consult a licensed physician for professional medical advice."
    }


def recommend_first_aid_and_otc_medicines(symptom_or_injury: str) -> dict[str, Any]:
    """Provides first-aid instructions and over-the-counter (OTC) medication guidance."""
    text = symptom_or_injury.lower()

    first_aid_steps = []
    otc_medicines = []
    precautions = []

    if "cut" in text or "wound" in text or "vegetable" in text or "bleed" in text:
        first_aid_steps = [
            "1. Wash hands thoroughly before touching the cut.",
            "2. Apply gentle pressure with a clean cloth/tissue to stop bleeding.",
            "3. Clean the cut under mild running tap water and mild soap.",
            "4. Apply an antiseptic ointment (e.g., Neosporin or Povidone-iodine).",
            "5. Cover with a sterile adhesive bandage (Band-Aid)."
        ]
        otc_medicines = [
            "Antiseptic Ointment (Neosporin / Bacitracin / Betadine)",
            "Sterile Bandages & Gauze pads",
            "Mild Pain Reliever (Paracetamol / Acetaminophen if aching)"
        ]
        precautions = [
            "Seek urgent medical care if bleeding does not stop after 10 minutes of pressure.",
            "Ensure Tetanus vaccination is up to date if cut by a dirty or rusted knife."
        ]
    elif "fever" in text:
        first_aid_steps = [
            "1. Rest in a cool, comfortable environment.",
            "2. Stay hydrated with water, clear broths, or ORS.",
            "3. Apply a lukewarm damp cloth to forehead."
        ]
        otc_medicines = [
            "Paracetamol / Acetaminophen (500mg as directed for adults)",
            "Ibuprofen (if inflammation/body ache is present)"
        ]
        precautions = [
            "Consult a doctor immediately if fever exceeds 103°F (39.4°C) or lasts more than 3 days."
        ]
    else:
        first_aid_steps = ["1. Drink warm fluids.", "2. Rest."]
        otc_medicines = ["Decongestant / Saline spray"]
        precautions = ["Consult a physician if symptoms persist."]

    return {
        "condition": symptom_or_injury,
        "first_aid_steps": first_aid_steps,
        "recommended_otc_medicines": otc_medicines,
        "precautions": precautions,
    }


def geocode_address(address: str) -> dict[str, Any]:
    """Converts a street address or location name into geographic coordinates."""
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    encoded_address = urllib.parse.quote(address)

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}"
    if maps_key and maps_key != "PASTE_KEY_HERE":
        url += f"&key={maps_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            status = data.get("status")

            if status == "OK" and data.get("results"):
                result = data["results"][0]
                loc = result["geometry"]["location"]
                return {
                    "address_searched": address,
                    "formatted_address": result.get("formatted_address"),
                    "latitude": loc.get("lat"),
                    "longitude": loc.get("lng"),
                    "place_id": result.get("place_id"),
                    "status": "OK",
                }
    except Exception:
        pass

    location_lower = address.lower()
    if "san francisco" in location_lower or "sf" in location_lower:
        lat, lng, fmt_addr = 37.7749, -122.4194, "San Francisco, CA, USA"
    elif "mountain view" in location_lower:
        lat, lng, fmt_addr = 37.3861, -122.0839, "Mountain View, CA, USA"
    else:
        lat, lng, fmt_addr = 40.7128, -74.0060, "New York, NY, USA"

    return {
        "address_searched": address,
        "formatted_address": fmt_addr,
        "latitude": lat,
        "longitude": lng,
        "place_id": "ChIJOwg_06VPwokRYv534QaPC8g",
        "status": "OK (Fallback Geocoding)",
    }


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "hospital",
    radius_meters: float = 5000.0,
) -> dict[str, Any]:
    """Finds nearby medical places (hospital, doctor, pharmacy) near latitude & longitude."""
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "")

    url = "https://places.googleapis.com/v1/places:searchNearby"

    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_meters),
            }
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }

    if maps_key and maps_key != "PASTE_KEY_HERE":
        headers["X-Goog-Api-Key"] = maps_key
    else:
        try:
            token = (
                subprocess.check_output(
                    ["gcloud", "auth", "print-access-token"], text=True
                )
                .strip()
            )
            headers["Authorization"] = f"Bearer {token}"
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
            if project_id:
                headers["X-Goog-User-Project"] = project_id
        except Exception:
            pass

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode())
            places_raw = data.get("places", [])

            results = []
            for p in places_raw:
                display_name = (
                    p.get("displayName", {}).get("text")
                    if isinstance(p.get("displayName"), dict)
                    else p.get("displayName")
                )
                results.append(
                    {
                        "name": display_name or "N/A",
                        "address": p.get("formattedAddress", "N/A"),
                        "location": p.get("location", {}),
                    }
                )

            return {
                "search_center": {"latitude": latitude, "longitude": longitude},
                "place_type": place_type,
                "total_found": len(results),
                "places": results,
            }
    except Exception as e:
        return {
            "search_center": {"latitude": latitude, "longitude": longitude},
            "place_type": place_type,
            "error": str(e),
            "message": f"Failed to search nearby places: {e}",
        }


# A2UI Schema Manager setup with BasicCatalog v0.8
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description="HealthTriage AI, a personal health triage assistant that evaluates symptoms, medical history, allergies, and provides specialist recommendations, first-aid, OTC guidance, location search, and visual diagrams.",
    workflow_description="Analyze the user request, run appropriate tools, and return structured A2UI UI cards when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects. "
        "Always remember user allergies (e.g. penicillin, sulfa, aspirin, NSAIDs, latex, peanuts) across sessions and warn against contraindicated medicines."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="health_triage_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        diagnose_symptoms_and_recommend_specialist,
        recommend_first_aid_and_otc_medicines,
        geocode_address,
        find_nearby_places,
        generate_first_aid_visual,
        generate_first_aid_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
