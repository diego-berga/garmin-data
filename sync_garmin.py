import garminconnect
import datetime
import json
import os

EMAIL = os.environ["GARMIN_EMAIL"]
PASSWORD = os.environ["GARMIN_PASSWORD"]
DAYS_BACK = 60


def safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"Skip {getattr(fn, '__name__', fn)}: {e}")
        return None


def main():
    client = garminconnect.Garmin(EMAIL, PASSWORD)
    client.login()

    today = datetime.date.today()
    daily_data = []
    activities_data = []

    for i in range(DAYS_BACK):
        day = today - datetime.timedelta(days=i)
        day_str = day.isoformat()

        stats = safe(client.get_stats, day_str) or {}
        sleep = safe(client.get_sleep_data, day_str) or {}
        hrv = safe(client.get_hrv_data, day_str) or {}
        body_battery = safe(client.get_body_battery, day_str, day_str)
        stress = safe(client.get_stress_data, day_str) or {}
        respiration = safe(client.get_respiration_data, day_str) or {}
        spo2 = safe(client.get_spo2_data, day_str) or {}
        readiness = safe(client.get_training_readiness, day_str)
        floors = safe(client.get_floors, day_str) or {}
        intensity = safe(client.get_intensity_minutes_data, day_str)

        sleep_dto = sleep.get("dailySleepDTO", {}) if sleep else {}
        sleep_seconds = sleep_dto.get("sleepTimeSeconds", 0)
        deep_sec = sleep_dto.get("deepSleepSeconds")
        light_sec = sleep_dto.get("lightSleepSeconds")
        rem_sec = sleep_dto.get("remSleepSeconds")
        awake_sec = sleep_dto.get("awakeSleepSeconds")

        hrv_value = hrv_status = None
        if hrv and "hrvSummary" in hrv:
            hrv_value = hrv["hrvSummary"].get("lastNightAvg")
            hrv_status = hrv["hrvSummary"].get("status")

        bb_min = bb_max = bb_charged = bb_drained = None
        if body_battery and isinstance(body_battery, list) and len(body_battery) > 0:
            bb = body_battery[0]
            bb_charged = bb.get("charged")
            bb_drained = bb.get("drained")
            values = [v[1] for v in bb.get("bodyBatteryValuesArray", []) if v[1] is not None]
            if values:
                bb_min = min(values)
                bb_max = max(values)

        readiness_score = readiness_level = None
        if isinstance(readiness, list) and len(readiness) > 0:
            readiness_score = readiness[0].get("score")
            readiness_level = readiness[0].get("level")
        elif isinstance(readiness, dict):
            readiness_score = readiness.get("score")
            readiness_level = readiness.get("level")

        intensity_mod = intensity_vig = None
        if isinstance(intensity, dict):
            intensity_mod = intensity.get("moderateValue")
            intensity_vig = intensity.get("vigorousValue")

        daily_data.append({
            "date": day_str,
            "resting_hr": stats.get("restingHeartRate"),
            "steps": stats.get("totalSteps"),
            "calories_total": stats.get("totalKilocalories"),
            "calories_active": stats.get("activeKilocalories"),
            "floors_climbed": floors.get("floorsAscended"),
            "intensity_minutes_moderate": intensity_mod,
            "intensity_minutes_vigorous": intensity_vig,
            "sleep_hours": round(sleep_seconds / 3600, 2) if sleep_seconds else None,
            "sleep_score": (sleep_dto.get("sleepScores", {}) or {}).get("overall", {}).get("value")
                if sleep_dto.get("sleepScores") else None,
            "sleep_deep_min": round(deep_sec / 60, 1) if deep_sec else None,
            "sleep_light_min": round(light_sec / 60, 1) if light_sec else None,
            "sleep_rem_min": round(rem_sec / 60, 1) if rem_sec else None,
            "sleep_awake_min": round(awake_sec / 60, 1) if awake_sec else None,
            "hrv": hrv_value,
            "hrv_status": hrv_status,
            "body_battery_min": bb_min,
            "body_battery_max": bb_max,
            "body_battery_charged": bb_charged,
            "body_battery_drained": bb_drained,
            "stress_avg": stress.get("avgStressLevel"),
            "stress_max": stress.get("maxStressLevel"),
            "respiration_avg": respiration.get("avgWakingRespirationValue"),
            "spo2_avg": spo2.get("averageSpO2"),
            "spo2_lowest": spo2.get("lowestSpO2"),
            "training_readiness_score": readiness_score,
            "training_readiness_level": readiness_level,
        })

    # Metriche "correnti" (non giornaliere)
    max_metrics = safe(client.get_max_metrics, today.isoformat())
    race_predictions = safe(client.get_race_predictions)
    endurance_score = safe(client.get_endurance_score)
    hill_score = safe(client.get_hill_score)

    current_metrics = {
        "vo2max_running": None,
        "race_prediction_5k_sec": None,
        "race_prediction_10k_sec": None,
        "race_prediction_half_marathon_sec": None,
        "race_prediction_marathon_sec": None,
        "endurance_score": None,
        "hill_score": None,
    }
    if isinstance(max_metrics, list) and len(max_metrics) > 0:
        gmi = max_metrics[0].get("generic", {}) or {}
        current_metrics["vo2max_running"] = gmi.get("vo2MaxValue")
    if isinstance(race_predictions, dict):
        current_metrics["race_prediction_5k_sec"] = race_predictions.get("time5K")
        current_metrics["race_prediction_10k_sec"] = race_predictions.get("time10K")
        current_metrics["race_prediction_half_marathon_sec"] = race_predictions.get("timeHalfMarathon")
        current_metrics["race_prediction_marathon_sec"] = race_predictions.get("timeMarathon")
    if isinstance(endurance_score, dict):
        current_metrics["endurance_score"] = endurance_score.get("overallScore")
    if isinstance(hill_score, dict):
        current_metrics["hill_score"] = hill_score.get("overallScore")

    # Attività con dettaglio (splits, zone FC, dinamica di corsa)
    activities = safe(client.get_activities, 0, 30) or []
    for act in activities:
        activity_id = act.get("activityId")
        entry = {
            "id": activity_id,
            "date": (act.get("startTimeLocal") or "")[:10],
            "type": (act.get("activityType") or {}).get("typeKey"),
            "name": act.get("activityName"),
            "distance_km": round(act["distance"] / 1000, 2) if act.get("distance") else None,
            "duration_min": round(act["duration"] / 60, 1) if act.get("duration") else None,
            "avg_pace_min_km": None,
            "avg_hr": act.get("averageHR"),
            "max_hr": act.get("maxHR"),
            "elevation_gain": act.get("elevationGain"),
            "elevation_loss": act.get("elevationLoss"),
            "calories": act.get("calories"),
            "avg_cadence": act.get("averageRunningCadenceInStepsPerMinute"),
            "vo2max_estimate": act.get("vO2MaxValue"),
            "training_effect_aerobic": act.get("aerobicTrainingEffect"),
            "training_effect_anaerobic": act.get("anaerobicTrainingEffect"),
            "hr_zones": None,
            "splits": None,
        }
        d, dur = act.get("distance"), act.get("duration")
        if d and dur and d > 0:
            pace_sec = dur / (d / 1000)
            entry["avg_pace_min_km"] = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}"

        if activity_id:
            hr_zones = safe(client.get_activity_hr_in_timezones, activity_id)
            if hr_zones:
                try:
                    entry["hr_zones"] = [
                        {"zone": z.get("zoneNumber"), "seconds": z.get("secsInZone")}
                        for z in hr_zones
                    ]
                except Exception as e:
                    print(f"Skip hr_zones parse: {e}")

            splits = safe(client.get_activity_splits, activity_id)
            if splits and isinstance(splits, dict) and "lapDTOs" in splits:
                try:
                    entry["splits"] = [
                        {
                            "lap": idx + 1,
                            "distance_km": round(lap["distance"] / 1000, 2) if lap.get("distance") else None,
                            "duration_min": round(lap["duration"] / 60, 2) if lap.get("duration") else None,
                            "avg_hr": lap.get("averageHR"),
                        }
                        for idx, lap in enumerate(splits["lapDTOs"])
                    ]
                except Exception as e:
                    print(f"Skip splits parse: {e}")

        activities_data.append(entry)

    output = {
        "last_updated": datetime.datetime.now().isoformat(),
        "current_metrics": current_metrics,
        "daily": daily_data,
        "activities": activities_data,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/data.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
