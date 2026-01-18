import requests
import xmltodict
import os
from datetime import datetime

# --- CONFIGURATION ---
TARGET_AIRPORT = "ASE"
# The FAA "Real-time" status feed
STATUS_URL = "https://nasstatus.faa.gov/api/airport-status-information"
# The FAA "Planning" feed (future delays)
PLAN_URL = "https://www.fly.faa.gov/adv/adv_spt.jsp"
# Your Discord Webhook URL (We will set this securely in the next step)
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

def send_discord_alert(message):
    if not WEBHOOK_URL:
        print("No Webhook URL found. Skipping notification.")
        return
    data = {"content": message}
    requests.post(WEBHOOK_URL, json=data)

def check_realtime_status():
    """Checks for active Ground Stops or Delays"""
    try:
        response = requests.get(STATUS_URL, headers={'User-Agent': 'PythonScript'})
        data = xmltodict.parse(response.content)
        
        # Navigate the messy XML structure
        status_info = data.get('AIRPORT_STATUS_INFORMATION', {})
        delay_lists = status_info.get('Delay_type', [])
        if isinstance(delay_lists, dict): delay_lists = [delay_lists]

        alerts = []
        
        for item in delay_lists:
            # Check every list (Ground Stop List, Departure Delay List, etc.)
            for key, value in item.items():
                if key.endswith('_List') and value:
                    programs = value.get('Program') or value.get('Ground_Delay') or value.get('Arrival_Delay')
                    if isinstance(programs, dict): programs = [programs]
                    
                    for prog in programs:
                        if prog.get('ARPT') == TARGET_AIRPORT:
                            reason = prog.get('Reason', 'Unknown')
                            avg_delay = prog.get('Avg', 'N/A')
                            alert_type = item.get('Name', 'Delay')
                            alerts.append(f"**{alert_type}** at {TARGET_AIRPORT}\nReason: {reason}\nAvg Delay: {avg_delay}")

        return alerts
    except Exception as e:
        print(f"Error checking realtime status: {e}")
        return []

def check_future_plans():
    """Scrapes the operations plan for 'ASE' mentions"""
    try:
        response = requests.get(PLAN_URL, headers={'User-Agent': 'PythonScript'})
        text = response.text.upper()
        
        # Look for our airport in the text
        lines = text.split('\n')
        relevant_lines = []
        for line in lines:
            if TARGET_AIRPORT in line and ("GROUND STOP" in line or "DELAY" in line):
                clean_line = line.replace("<td>", "").replace("</td>", "").replace("&NBSP;", "").strip()
                if len(clean_line) > 10: # Filter out noise
                    relevant_lines.append(clean_line)
        return relevant_lines
    except Exception as e:
        print(f"Error checking future plans: {e}")
        return []

if __name__ == "__main__":
    print(f"Checking status for {TARGET_AIRPORT}...")
    
    realtime_issues = check_realtime_status()
    future_plans = check_future_plans()
    
    if realtime_issues or future_plans:
        msg = f"✈️ **FAA Alert for {TARGET_AIRPORT}**\n"
        
        if realtime_issues:
            msg += "\n**Active Now:**\n" + "\n".join(realtime_issues)
        
        if future_plans:
            msg += "\n\n**Forecasted / Planning:**\n" + "\n".join(future_plans)
            
        msg += f"\n\n*Checked at {datetime.now()} UTC*"
        
        print("Found issues! Sending alert...")
        send_discord_alert(msg)
    else:
        print("No issues found. All clear.")
