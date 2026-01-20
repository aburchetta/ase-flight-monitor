import requests
import xmltodict
import os
import pytz
from datetime import datetime

# --- CONFIGURATION ---
TARGET_AIRPORT = "SLC"
STATUS_URL = "https://nasstatus.faa.gov/api/airport-status-information"
PLAN_URL = "https://www.fly.faa.gov/adv/adv_spt.jsp"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# Define your Timezone (Aspen/Basalt is Mountain Time)
MY_TIMEZONE = pytz.timezone('US/Mountain')

def send_discord_alert(message):
    if not WEBHOOK_URL:
        print("No Webhook URL found.")
        return
    data = {"content": message}
    requests.post(WEBHOOK_URL, json=data)

def check_realtime_status():
    """Checks for active Ground Stops or Delays"""
    try:
        response = requests.get(STATUS_URL, headers={'User-Agent': 'PythonScript'})
        data = xmltodict.parse(response.content)
        status_info = data.get('AIRPORT_STATUS_INFORMATION', {})
        delay_lists = status_info.get('Delay_type', [])
        if isinstance(delay_lists, dict): delay_lists = [delay_lists]

        alerts = []
        for item in delay_lists:
            for key, value in item.items():
                if key.endswith('_List') and value:
                    programs = value.get('Program') or value.get('Ground_Delay') or value.get('Arrival_Delay')
                    if isinstance(programs, dict): programs = [programs]
                    for prog in programs:
                        if prog.get('ARPT') == TARGET_AIRPORT:
                            reason = prog.get('Reason', 'Unknown')
                            avg_delay = prog.get('Avg', 'N/A')
                            alert_type = item.get('Name', 'Delay')
                            alerts.append(f"**{alert_type}**\nReason: {reason}\nAvg Delay: {avg_delay}")
        return alerts
    except Exception as e:
        print(f"Error checking realtime status: {e}")
        return []

def check_future_plans():
    """Scrapes the operations plan for 'ASE' mentions"""
    try:
        response = requests.get(PLAN_URL, headers={'User-Agent': 'PythonScript'})
        text = response.text.upper()
        lines = text.split('\n')
        relevant_lines = []
        for line in lines:
            if TARGET_AIRPORT in line and ("GROUND STOP" in line or "DELAY" in line):
                clean_line = line.replace("<td>", "").replace("</td>", "").replace("&NBSP;", "").strip()
                if len(clean_line) > 10:
                    relevant_lines.append(clean_line)
        return relevant_lines
    except Exception as e:
        print(f"Error checking future plans: {e}")
        return []

def is_heartbeat_time():
    """Checks if current Mountain Time matches the heartbeat schedule"""
    now = datetime.now(MY_TIMEZONE)
    
    # 8:00 AM Check (08:00 - 08:09)
    if now.hour == 8 and 0 <= now.minute < 10:
        return True
        
    # 12:30 PM Check (12:30 - 12:39)
    if now.hour == 12 and 30 <= now.minute < 40:
        return True
        
    return False

if __name__ == "__main__":
    current_time_str = datetime.now(MY_TIMEZONE).strftime('%I:%M %p %Z')
    print(f"Checking status for {TARGET_AIRPORT} at {current_time_str}...")
    
    realtime_issues = check_realtime_status()
    future_plans = check_future_plans()
    send_heartbeat = is_heartbeat_time()
    
    if realtime_issues or future_plans:
        msg = f"✈️ **FAA Alert for {TARGET_AIRPORT}**\n"
        
        if realtime_issues:
            msg += "\n**Active Now:**\n" + "\n".join(realtime_issues)
        
        if future_plans:
            msg += "\n\n**Forecasted / Planning:**\n" + "\n".join(future_plans)
            
        msg += f"\n\n*Checked at {current_time_str}*"
        
        print("Found issues! Sending alert...")
        send_discord_alert(msg)

    elif send_heartbeat:
        msg = f"🟢 **Daily Heartbeat:** System Online.\nNo active delays at {TARGET_AIRPORT}."
        msg += f"\n*Checked at {current_time_str}*"
        
        print("Sending Heartbeat...")
        send_discord_alert(msg)
        
    else:
        print("No issues and not heartbeat time. Staying silent.")
