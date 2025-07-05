import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime
import pytz

# --- การตั้งค่าทั่วไป ---
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_TARGET_ID = os.environ.get('LINE_TARGET_ID')
TIMEZONE_THAILAND = pytz.timezone('Asia/Bangkok')

# --- การตั้งค่าสำหรับสคริปต์นี้โดยเฉพาะ ---
STATION_URL = "https://singburi.thaiwater.net/wl" # <-- เปลี่ยนเป็น URL ใหม่ที่คุณให้มา
LAST_DATA_FILE = 'last_inburi_data.txt'
STATION_ID_TO_FIND = "C.35" # <-- ID ของสถานีที่ต้องการค้นหา (อ.อินทร์บุรี)

def get_inburi_river_data():
    """ดึงข้อมูลระดับน้ำจากตารางในหน้าเว็บ singburi.thaiwater.net"""
    try:
        print(f"Fetching data from {STATION_URL} for station {STATION_ID_TO_FIND}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(STATION_URL, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # ค้นหาตารางข้อมูลจาก id 'tele_wl'
        table = soup.find('table', id='tele_wl')
        if not table:
            print("Could not find the data table on the page.")
            return None

        # วนลูปหาแถว (tr) ที่มีข้อมูลสถานี C.35
        target_row = None
        for row in table.find('tbody').find_all('tr'):
            columns = row.find_all('td')
            # คอลัมน์แรก (index 0) คือชื่อสถานี
            if columns and STATION_ID_TO_FIND in columns[0].text:
                target_row = columns
                break
        
        if not target_row:
            print(f"Could not find station {STATION_ID_TO_FIND} in the table.")
            return None

        # ดึงข้อมูลจากคอลัมน์ต่างๆ ตามลำดับในตาราง
        station_name = target_row[0].text.strip()
        water_level_str = target_row[2].text.strip() # ระดับน้ำ (ม.รทก.)
        bank_level_str = target_row[3].text.strip() # ระดับตลิ่ง (ม.รทก.)

        print(f"Found station: {station_name}")
        print(f"  - Water Level: {water_level_str} m.")
        print(f"  - Bank Level: {bank_level_str} m.")

        # แปลงค่าเป็นตัวเลข
        water_level = float(water_level_str)
        bank_level = float(bank_level_str)
        overflow = water_level - bank_level

        return {
            "station": station_name,
            "water_level": water_level,
            "bank_level": bank_level,
            "overflow": overflow
        }

    except (requests.exceptions.RequestException, AttributeError, ValueError, IndexError) as e:
        print(f"An error occurred in get_inburi_river_data: {e}")
        return None

def send_line_message(data):
    """ส่งข้อความแจ้งเตือนระดับน้ำของอินทร์บุรี"""
    now_thailand = datetime.now(TIMEZONE_THAILAND)
    formatted_datetime = now_thailand.strftime("%d/%m/%Y %H:%M น.")

    if data['overflow'] > 0:
        status_text = "⚠️ *น้ำล้นตลิ่ง*"
        status_icon = "🚨"
        overflow_text = f"{data['overflow']:.2f} ม."
    else:
        status_text = "✅ *ระดับน้ำปกติ*"
        status_icon = "🌊"
        overflow_text = f"ต่ำกว่าตลิ่ง {-data['overflow']:.2f} ม."

    message = (
        f"{status_icon} *แจ้งเตือนระดับน้ำแม่น้ำเจ้าพระยา*\n"
        f"📍 *พื้นที่: {data['station']}*\n"
        f"━━━━━━━━━━━━━━\n"
        f"💧 *ระดับน้ำปัจจุบัน:* {data['water_level']:.2f} ม. (รทก.)\n"
        f"🏞️ *ระดับขอบตลิ่ง:* {data['bank_level']:.2f} ม. (รทก.)\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 *สถานะ:* {status_text}\n"
        f"({overflow_text})\n\n"
        f"🗓️ {formatted_datetime}"
    )

    url = 'https://api.line.me/v2/bot/message/push'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'}
    payload = {'to': LINE_TARGET_ID, 'messages': [{'type': 'text', 'text': message}]}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print("LINE message for In Buri sent successfully!")
    except requests.exceptions.RequestException as e:
        print(f"Error sending LINE message: {e.response.text if e.response else 'No response'}")

def read_last_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return f.read().strip()
    return ""

def write_data(file_path, data):
    with open(file_path, 'w') as f:
        f.write(data)

def main():
    """ตรรกะหลักของโปรแกรม"""
    current_data_dict = get_inburi_river_data()
    
    if current_data_dict is None:
        print("Could not retrieve current data. Exiting.")
        return

    current_data_str = f"{current_data_dict['water_level']:.2f}"
    last_data_str = read_last_data(LAST_DATA_FILE)

    print(f"Current data string: {current_data_str}")
    print(f"Last data string: {last_data_str}")

    if current_data_str != last_data_str:
        print("Data has changed! Processing notification...")
        send_line_message(current_data_dict)
        write_data(LAST_DATA_FILE, current_data_str)
    else:
        print("Data has not changed. No action needed.")

if __name__ == "__main__":
    main()
