from flask import Flask, render_template_string
import threading
import pyrebase
from sense_emu import SenseHat
import time
import sqlite3

# Cấu hình Firebase
config = {
    "apiKey": "AIzaSyDnqfak6IFGim9xNTZnkzOy_8sSLkqDU4w",
    "authDomain": "deviot-d84a6.firebaseapp.com",
    "databaseURL": "https://deviot-d84a6-default-rtdb.firebaseio.com",
    "projectId": "deviot-d84a6",
    "storageBucket": "deviot-d84a6.firebasestorage.app",
    "messagingSenderId": "548576355536",
    "appId": "1:548576355536:web:60de6f77cd2af38a052ad5"
}

# Khởi tạo Firebase và SenseHAT
firebase = pyrebase.initialize_app(config)
database = firebase.database()
sense = SenseHat()
app = Flask(__name__)

# Biến toàn cục
previous_T = 0  # Giá trị T trước đó
temperature_change_threshold = 0.3  # Ngưỡng thay đổi nhiệt độ (1 độ)
current_data = {"T_cap_nhat": 0, "humidity": 0, "joystick_state": "", "pressure": 0}  # Dữ liệu hiển thị trên web

# Hàm lưu nhiệt độ vào database SQLite
def save_temperature_to_db(temperature):
    try:
        conn = sqlite3.connect('temperature_data.db')  # Kết nối hoặc tạo database
        cursor = conn.cursor()

        # Tạo bảng nếu chưa tồn tại
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS temperatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temperature REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Lưu nhiệt độ vào database
        cursor.execute("INSERT INTO temperatures (temperature) VALUES (?)", (temperature,))
        conn.commit()
        conn.close()
        print(f"Temperature {temperature} inserted into database.")
    except Exception as e:
        print("Lỗi khi lưu nhiệt độ vào database:", e)

# Hàm đọc dữ liệu và tối ưu gửi
def push_optimized_data():
    global previous_T, current_data  # Sử dụng biến toàn cục
    while True:
        try:
            # Đọc nhiệt độ, độ ẩm và áp suất từ SenseHAT
            current_temp = round(sense.get_temperature(), 2)
            humidity = round(sense.get_humidity(), 2)
            pressure = round(sense.get_pressure(), 2)

            # Lấy trạng thái joystick
            joystick_events = sense.stick.get_events()
            joystick_state = "Không có sự kiện"
            if joystick_events:
                last_event = joystick_events[-1]
                joystick_state = f"{last_event.direction} - {last_event.action}"

            # So sánh sự thay đổi nhiệt độ với ngưỡng
            if abs(current_temp - previous_T) > temperature_change_threshold:
                # Tính T_cập_nhật
                T_cap_nhat = round((current_temp + previous_T) / 2, 2)
                # Gửi dữ liệu lên Firebase
                sensor_data = {
                    "temperature": T_cap_nhat,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                database.child("OptimizedSensorData").set(sensor_data)
                print("Đã gửi dữ liệu lên Firebase:", sensor_data)

                previous_T = T_cap_nhat  # Cập nhật T

                # Lưu nhiệt độ vào database
                save_temperature_to_db(T_cap_nhat)

            # Cập nhật dữ liệu hiển thị trên web
            current_data["t_hien_tai"] = current_temp
            current_data["T_cap_nhat"] = T_cap_nhat
            current_data["humidity"] = humidity
            current_data["joystick_state"] = joystick_state
            current_data["pressure"] = pressure

            # Tạm dừng 3 giây
            time.sleep(3)

        except Exception as e:
            print("Lỗi xảy ra:", e)

# Route Flask hiển thị dữ liệu trên giao diện web
@app.route('/')
def display_data():
    # HTML template hiển thị dữ liệu
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Giám sát cảm biến</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f4f7fc;
                color: #333;
            }
            h1 {
                text-align: center;
                color: #444;
                font-size: 2em;
            }
            .container {
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                margin-top: 20px;
            }
            .box {
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                padding: 20px;
                width: 250px;
                margin: 10px;
                text-align: center;
            }
            .box h2 {
                color: #444;
                font-size: 1.4em;
                margin-bottom: 10px;
            }
            .box p {
                font-size: 1.1em;
                margin: 5px 0;
            }
            .box p strong {
                color: #5a5a5a;
            }
        </style>
    </head>
    <body>
        <h1>Giám sát cảm biến</h1>
        
        <div class="container">
            <div class="box">
                <h2>Nhiệt độ hiện tại</h2>
                <p><strong>{{ t_hien_tai }}</strong> °C</p>
            </div>
            <div class="box">
                <h2>Nhiệt độ cập nhật lên Firebase</h2>
                <p><strong>{{ T_cap_nhat }}</strong> °C</p>
            </div>
            <div class="box">
                <h2>Độ ẩm</h2>
                <p><strong>{{ humidity }}</strong> %</p>
            </div>
            <div class="box">
                <h2>Áp suất</h2>
                <p><strong>{{ pressure }}</strong> hPa</p>
            </div>
            <div class="box">
                <h2>Trạng thái Joystick</h2>
                <p><strong>{{ joystick_state }}</strong></p>
            </div>
        </div>

        <script>
            setInterval(function() {
                location.reload();  // Tự động tải lại trang sau mỗi 5 giây
            }, 2000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template, **current_data)

# Khởi chạy thread và Flask
if __name__ == '__main__':
    threading.Thread(target=push_optimized_data, daemon=True).start()
    app.run(debug=True)
