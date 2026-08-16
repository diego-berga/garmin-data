import garminconnect
import datetime
import json
import os

EMAIL = os.environ["GARMIN_EMAIL"]
PASSWORD = os.environ["GARMIN_PASSWORD"]
DAYS_BACK = 60


def main():
    client = garminconnect.Garmin(EMAIL, PASSWORD)
    client.login()

    today = datetime.date.today()
    daily_data = []
    activities_data = []

    for i in range(DAYS_BACK):
        day = today - datetime.timedelta(days=i)
        day_str = day.isoformat()
        try:
            sleep = client.get_sleep_data(day_str)
            hrv = client.get_hrv_data(day_str)
            stats = client.get_stats(day_str)
            body_battery = client.get_body_battery(day_str, day_str)

            sleep_dto = sleep.get("dailySleepDTO", {}) if sleep else {}
            sleep_seconds = sleep_dto.get("sleepTimeSeconds", 0)
            sleep_hours = round(sleep_seconds / 3600, 2) if sleep_seconds else None
            sleep_score = (
                sleep_dto.get("sleepScores", {}).get("overall", {}).get("value")
                if sleep_dto.get("sleepScores") else None
            )

            hrv_value = None
            if hrv and "hrvSummary" in hrv:
                hrv_value = hrv["hrvSummary"].get("lastNightAvg")

            resting_hr = stats.get("restingHeartRate") if stats else None
            stress_avg = stats.get("averageStressLevel") if stats else None

            bb_min = bb_max = bb_charged = bb_drained = None
            if body_battery and len(body_battery) > 0:
                bb = body_battery[0]
                bb_charged = bb.get("charged")
                bb_drained = bb.get("drained")
                values = [v[1] for v in bb.get("bodyBatteryValuesArray", []) if v[1] is not None]
                if values:
                    bb_min = min(values)
                    bb_max = max(values)

            daily_data.append({
                "date": day_str,
                "sleep_hours": sleep_hours,
                "sleep_score": sleep_score,
                "hrv": hrv_value,
                "resting_hr": resting_hr,
                "body_battery_min": bb_min,
                "body_battery_max": bb_max,
                "body_battery_charged": bb_charged,
                "body_battery_drained": bb_drained,
                "stress_avg": stress_avg,
            })
        except Exception as e:
            print(f"Errore dati giornalieri {day_str}: {e}")

    try:
        activities = client.get_activities(0, 30)
        for act in activities:
            entry = {
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
            }
            d, dur = act.get("distance"), act.get("duration")
            if d and dur and d > 0:
                pace_sec = dur / (d / 1000)
                entry["avg_pace_min_km"] = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}"
            activities_data.append(entry)
    except Exception as e:
        print(f"Errore attività: {e}")

    output = {
        "last_updated": datetime.datetime.now().isoformat(),
        "daily": daily_data,
        "activities": activities_data,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/data.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()

