import requests
import xmltodict
import os
import pytz
from datetime import datetime

# --- CONFIGURATION ---
# IMPORTANT: Use square brackets [] and quotes "" for each airport
TARGET_AIRPORTS = ["ASE", "DEN", "LAX", "IAH", "ATL", "ORD"]

STATUS_URL = "https://nasstatus.faa.gov/api/airport-status-information"
PLAN_URL = "https://www.fly.faa.gov/adv/adv_spt.jsp"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "schedule")
MY_TIMEZONE = pytz.timezone('US/Mountain')

def send_discord_alert(message):
    if not WEBHOOK_URL: return
    requests.post(WEBHOOK_URL, json={"content": message})

def check_realtime_status():
    try:
        response = requests.get(STATUS_URL, headers={'User-Agent': 'PythonScript'})
        data = xmltodict.parse(response.content)
        status_info = data.get('AIRPORT_STATUS_INFORMATION', {})
        
        # FIX: Handle cases where 'Delay_type' is None or missing
        delay_lists = status_info.get('Delay_type')
        if not delay_lists:
            return [] # No delays nationwide
            
        if isinstance(delay_lists, dict): delay_lists = [delay_lists]

        alerts = []
        for item in delay_lists:
            for key, value in item.items():
                if key.endswith('_List') and value:
                    programs = value.get('Program') or value.get('Ground_Delay') or value.get('Arrival_Delay')
                    if not programs: continue
                    
                    if isinstance(programs, dict): programs = [programs]
                    
                    for prog in programs:
                        airport = prog.get('ARPT')
                        if airport in TARGET_AIRPORTS:
                            reason = prog.get('Reason', 'Unknown')
                            avg_delay = prog.get('Avg', 'N/A')
                            alert_type = item.get('Name', 'Delay')
                            alerts.append(f"**{airport} - {alert_type}**\nReason: {reason}\nAvg Delay: {avg_delay}")
        return alerts
    except Exception as e:
        print(f"Error checking realtime status: {e}")
        return []

def check_future_plans():
    try:
        response = requests.get(PLAN_URL, headers={'User-Agent': 'PythonScript'})
        text = response.text.upper()
        relevant_lines = []
        
        for line in text.split('\n'):
            for airport in TARGET_AIRPORTS:
                # Ensure we are comparing strings (prevents the "Tuple" error)
                if isinstance(airport, str) and airport in line:
                    if "GROUND STOP" in line or "DELAY" in line:
                        clean = line.replace("<td>", "").replace("</td>", "").replace("&NBSP;", "").strip()
                        if len(clean) > 10: 
                            relevant_lines.append(f"**{airport}**: {clean}")
        return relevant_lines
    except Exception as e:
        print(f"Error checking future plans: {e}")
        return []

def is_heartbeat_time(now):
    # 8:00 AM Heartbeat
    if now.hour == 8: return True
    # 12:00 PM Heartbeat
    if now.hour == 12: return True
    return False

if __name__ == "__main__":
    now = datetime.now(MY_TIMEZONE)
    time_str = now.strftime('%I:%M %p %Z')
    print(f"Checking status for {TARGET_AIRPORTS} at {time_str}...")
    
    realtime_issues = check_realtime_status()
    future_plans = check_future_plans()
    
    if realtime_issues or future_plans:
        msg = f"✈️ **FAA Alert**\n"
        if realtime_issues: msg += "\n**Active Now:**\n" + "\n".join(realtime_issues)
        if future_plans: msg += "\n\n**Forecasted:**\n" + "\n".join(future_plans)
        msg += f"\n\n*Checked at {time_str}*"
        send_discord_alert(msg)

    elif EVENT_NAME == 'workflow_dispatch':
        msg = f"👋 **Manual Check:**\nAll systems clear at {', '.join(TARGET_AIRPORTS)}."
        msg += f"\n*Checked at {time_str}*"
        send_discord_alert(msg)

    elif is_heartbeat_time(now):
        msg = f"🟢 **Hourly Heartbeat:** System Online.\nNo active delays at {', '.join(TARGET_AIRPORTS)}."
        msg += f"\n*Checked at {time_str}*"
        send_discord_alert(msg)
        
    else:
        print("All clear. Staying silent.")
