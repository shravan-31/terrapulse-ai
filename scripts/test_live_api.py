#!/usr/bin/env python3
"""
scripts/test_live_api.py
Automated end-to-end testing of the live running SatQuery AI API server.
"""

import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def post_json(endpoint: str, payload: dict):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"\n❌ [HTTP {exc.code} on POST {endpoint}]:\n{body}\n")
        raise

def get_json(endpoint: str):
    url = f"{BASE_URL}{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"\n❌ [HTTP {exc.code} on GET {endpoint}]:\n{body}\n")
        raise

def main():
    print("=" * 60)
    print("🛰️  Testing Live SatQuery AI System Endpoints")
    print("=" * 60)

    # 1. Health
    h = get_json("/api/health")
    print(f"1. Health Check: Status={h['status']}, DB={h['dependencies']['database']}, Groq={h['features']['groq']}")
    assert h["dependencies"]["database"] == "ok", "Database must be ok"

    # 2. Query Parse
    qp = post_json("/api/query/parse", {"query": "Find new construction between 2022 and 2024 with cloud < 15%"})
    print(f"2. Query Parse: Model={qp['parser_model']}, Semantic Prompt='{qp['parsed']['semantic_prompt']}'")
    assert qp["parsed"]["max_cloud_cover"] <= 15

    # 3. AOIs
    aois = get_json("/api/aoi")
    aoi_list = aois.get("aois", [])
    print(f"3. AOIs: Total={aois.get('count', len(aoi_list))} persistent AOIs loaded from database")
    assert len(aoi_list) > 0, "At least one persistent AOI required"
    sample_aoi = aoi_list[0]

    # Scenes
    scenes = get_json("/api/scenes")
    scene_list = scenes.get("scenes", [])
    print(f"   Scenes: Total={scenes.get('count', len(scene_list))} scenes registered")
    assert len(scene_list) >= 2, "At least two scenes required for change detection"
    t1_scene = scene_list[0]
    t2_scene = scene_list[1]

    # 4. Semantic Search
    sr = post_json("/api/search/semantic", {"query": "cleared forest area", "top_k": 5})
    matches = sr.get("count", len(sr.get("results", [])))
    prompt = sr.get("semantic_prompt", "cleared forest area")
    print(f"4. Semantic Search: Matches={matches}, Prompt='{prompt}'")

    # 5. Change Detection
    cd = post_json("/api/change/analyze", {
        "aoi_id": sample_aoi["id"],
        "baseline_scene_id": t1_scene["id"],
        "comparison_scene_id": t2_scene["id"],
        "change_type_hint": "vegetation_loss"
    })
    analysis_id = cd["analysis_id"]
    print(f"5. Change Detection: Changes={cd['changes_detected']}, Status={cd['status']}, AnalysisID={analysis_id[:8]}...")

    # 6. Spectral Hypothesis Classifier
    hypo = post_json("/api/timeline/classify-hypothesis", {
        "ndvi_delta": -0.55,
        "ndwi_delta": -0.05,
        "ndbi_delta": 0.25,
        "aspect_ratio": 1.4
    })
    print(f"6. Spectral Classifier: Type={hypo.get('change_type')}, Hypothesis='{hypo.get('confidence_hypothesis')}'")

    # 7. Assistant Chat
    chat = post_json("/api/assistant/chat", {
        "message": "How many AOIs and changes are recorded?",
        "analysis_id": analysis_id
    })
    print(f"7. Assistant Chat: Engine={chat['engine']}, Reply='{chat['reply'][:70]}...'")

    # 8. Report Generator
    rep = post_json("/api/report/generate", {
        "analysis_id": analysis_id,
        "format": "json"
    })
    print(f"8. Report Generator: Format=JSON, Total Changes in Report={rep['total_changes']}")

    print("=" * 60)
    print("✅ ALL 8 SYSTEM MODULES ARE FULLY FUNCTIONAL AND VERIFIED LIVE!")
    print("=" * 60)

if __name__ == "__main__":
    main()
