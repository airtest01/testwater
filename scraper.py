import requests
import re
import json
from bs4 import BeautifulSoup
import os

URL = 'https://tiwrm.hii.or.th/DATA/REPORT/php/chart/chaopraya/small/chaopraya.php'
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_TARGET_ID = os.environ.get('LINE_TARGET_ID')

def get_water_data():
    """
    ฟังก์ชันสำหรับดึงข้อมูลโดยการอ่านค่าจาก JavaScript (json_data) โดยตรง
    """
    try:
        response = requests.get(URL, timeout=15)
        response.raise_for_status()

        # ใช้ Regular Expression เพื่อค้นหาบรรทัดที่มี 'var json_data'
        match = re.search(r'var json_data = (\[.*\]);', response.text)
        
        if not match:
            print("Could not find json_data variable in the page.")
            return None

        # ดึงข้อมูล JSON ออกมาและตัดส่วนที่ไม่ต้องการทิ้ง
        json_str = match.group(1)
        
        # แปลงข้อความ JSON ให้กลายเป็น Dictionary ของ Python
        data = json.loads(json_str)

        # เข้าถึงข้อมูลของสถานี C13 (ท้ายเขื่อนเจ้าพระยา)
        station_data = data[0].get('itc_water', {}).get('C13', None)

        if station_data:
            storage = station_data.get('storage', '-')
            qmax = station_data.get('qmax', '-')
            # จัดรูปแบบข้อความให้เหมือนกับบนหน้าเว็บ
            return f"{storage}/ {qmax} cms"
        
        return None

    except (requests.exceptions.RequestException, json.JSONDecodeError, AttributeError) as e:
        print(f"An error occurred: {e}")
        return None

def send_line_message(message):
    """
    ฟังก์ชันสำหรับส่งข้อความแจ้งเตือนผ่าน LINE Messaging API
    """
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_TARGET_ID:
        print("LINE credentials are not set. Cannot send message.")
        return

    url = 'https://api.line.me/v2/bot/message/push'
    headers = { 'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}' }
    payload = { 'to': LINE_TARGET_ID, 'messages': [{'type': 'text', 'text': message}] }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print("LINE message sent successfully!")
    except requests.exceptions.RequestException as e:
        print(f"Error sending LINE message: {e.response.text if e.response else 'No response'}")

def main():
    """
    ฟังก์ชันหลักในการทำงาน
    """
    last_data_file = 'last_data.txt'
    last_data = ''
    if os.path.exists(last_data_file):
        with open(last_data_file, 'r', encoding='utf-8') as f:
            last_data = f.read().strip()

    current_data = get_water_data()
    if current_data:
        print(f"Current data: {current_data}")
        print(f"Last saved data: {last_data}")
        if current_data != last_data:
            print("Data has changed! Sending notification...")
            message = f"อัปเดต! 🚨\nปริมาณน้ำท้ายเขื่อนเจ้าพระยา (จ.ชัยนาท)\n\n" \
                      f"ค่าปัจจุบัน: {current_data}\n" \
                      f"ค่าเดิม: {last_data if last_data else 'ยังไม่มีข้อมูลก่อนหน้า'}"
            send_line_message(message)
            with open(last_data_file, 'w', encoding='utf-8') as f:
                f.write(current_data)
        else:
            print("Data has not changed.")
    else:
        print("Could not retrieve current data from JSON.")

if __name__ == "__main__":
    main()
