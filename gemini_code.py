import os
import re
import asyncio
import uuid
import shutil
import time
import random
import sqlite3
from typing import Dict, List
from fastapi import FastAPI, Request, Response, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response as PlainResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright
import midtransclient

app = FastAPI()

# --- KONFIGURASI GOOGLE SEARCH CONSOLE VERIFICATION & SITEMAP ---
# Masukkan nama file verifikasi dan isi kodenya di bawah ini (atau letakkan file fisiknya di folder project)
GOOGLE_VERIFICATION_FILENAME = "google724c2c35ebc454fc.html"
GOOGLE_VERIFICATION_CONTENT = "google-site-verification: google724c2c35ebc454fc.html"

@app.get(f"/{GOOGLE_VERIFICATION_FILENAME}", response_class=HTMLResponse)
async def google_verification():
    # Cek apakah file fisik ada di direktori, jika ada baca filenya, jika tidak gunakan string di atas
    file_path = os.path.join(os.getcwd(), GOOGLE_VERIFICATION_FILENAME)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return GOOGLE_VERIFICATION_CONTENT

# --- FITUR SITEMAP.XML DINAMIS ---
@app.get("/sitemap.xml", response_class=PlainResponse)
async def sitemap(request: Request):
    base_url = str(request.base_url).rstrip("/")
    
    # Daftar halaman utama pada aplikasi Anda
    routes = [
        {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/login", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/register", "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{base_url}/forgot-password", "changefreq": "yearly", "priority": "0.3"}
    ]
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for route in routes:
        xml_content += "  <url>\n"
        xml_content += f"    <loc>{route['loc']}</loc>\n"
        xml_content += f"    <changefreq>{route['changefreq']}</changefreq>\n"
        xml_content += f"    <priority>{route['priority']}</priority>\n"
        xml_content += "  </url>\n"
        
    xml_content += '</urlset>'
    
    return PlainResponse(content=xml_content, media_type="application/xml")

# --- KONFIGURASI MIDTRANS (Gunakan Environment Variable untuk Keamanan) ---
MIDTRANS_CLIENT_KEY = os.getenv("MIDTRANS_CLIENT_KEY", "Mid-client-KyjVIKjIiP-gRRnQ")
MIDTRANS_SERVER_KEY = os.getenv("MIDTRANS_SERVER_KEY", "Mid-server-TaxRiT0dIPdTC5Byp7VXNqfz")
IS_PRODUCTION = False

snap = midtransclient.Snap(
    is_production=IS_PRODUCTION,
    server_key=MIDTRANS_SERVER_KEY,
    client_key=MIDTRANS_CLIENT_KEY
)

# --- DATABASE SQLITE ---
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            balance INTEGER DEFAULT 2000,
            device_info TEXT DEFAULT 'Unknown',
            device_uuid TEXT DEFAULT 'Unknown'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_topups (
            order_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at REAL NOT NULL
        )
    """)
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "balance" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 2000")
    if "device_info" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN device_info TEXT DEFAULT 'Unknown'")
    if "device_uuid" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN device_uuid TEXT DEFAULT 'Unknown'")

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, balance, device_info, device_uuid) VALUES ('admin', 'deocthulu21', 50000, 'System Administrator', 'admin-device')")
        cursor.execute("INSERT INTO users (username, password, balance, device_info, device_uuid) VALUES ('user1', 'password123', 2000, 'Default Device', 'default-device')")
        conn.commit()
    conn.close()

def get_user_data(username: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT password, balance FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return {"password": row[0], "balance": row[1]} if row else None

def get_all_users() -> List[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance, device_info, device_uuid FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [{"username": row[0], "balance": row[1], "device_info": row[2], "device_uuid": row[3]} for row in rows]

def set_user_balance(username: str, new_balance: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, username))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def save_user(username: str, password: str, device_info: str, device_uuid: str) -> tuple[bool, str]:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE device_uuid = ?", (device_uuid,))
        device_account_count = cursor.fetchone()[0]
        
        if device_account_count >= 3:
            conn.close()
            return False, "Perangkat HP ini telah mencapai batas maksimal pendaftaran (Maksimal 3 akun per perangkat)."

        cursor.execute(
            "INSERT INTO users (username, password, balance, device_info, device_uuid) VALUES (?, ?, 2000, ?, ?)",
            (username, password, device_info, device_uuid)
        )
        conn.commit()
        conn.close()
        return True, "Berhasil"
    except sqlite3.IntegrityError:
        return False, "Identitas username telah digunakan, gunakan nama lain!"

def deduct_balance(username: str, cost: int = 50) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")
    cursor.execute("SELECT balance FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row and row[0] >= cost:
        cursor.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (cost, username))
        conn.commit()
        conn.close()
        return True
    conn.rollback()
    conn.close()
    return False

def save_pending_topup(order_id: str, username: str, amount: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pending_topups (order_id, username, amount, created_at) VALUES (?, ?, ?, ?)",
                   (order_id, username, amount, time.time()))
    conn.commit()
    conn.close()

def process_midtrans_success(order_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, amount, status FROM pending_topups WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    
    if row and row[2] == 'pending':
        username, amount = row[0], row[1]
        cursor.execute("UPDATE pending_topups SET status = 'success' WHERE order_id = ?", (order_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, username))
        conn.commit()
        conn.close()
        return username, amount
    
    conn.close()
    return None, None

init_db()

sessions_state: Dict[str, dict] = {}
sessions_lock = asyncio.Lock()
browser_semaphore = asyncio.Semaphore(5)

class RunRequest(BaseModel):
    emails: List[str]
    workers: int = 5

class CreateTopupRequest(BaseModel):
    amount: int

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Google Captcha Checker Systems</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: radial-gradient(circle at 50% 0%, #1a1c29 0%, #090a0f 100%); color: #f1f5f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
        .login-card { background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%); backdrop-filter: blur(20px); padding: 40px; border-radius: 24px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px rgba(212, 175, 55, 0.08); border: 1px solid rgba(212, 175, 55, 0.2); width: 380px; position: relative; }
        .login-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, #d4af37, transparent); }
        h3 { margin-top: 0; text-align: center; font-family: 'Cinzel', serif; font-weight: 800; letter-spacing: 2px; color: #f8fafc; font-size: 24px; margin-bottom: 25px; text-transform: uppercase; background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .input-group { margin-bottom: 20px; }
        label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #d4af37; margin-bottom: 8px; font-weight: 600; }
        .password-container { position: relative; display: flex; align-items: center; }
        input { width: 100%; background: rgba(15, 23, 42, 0.8); color: #fff; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 14px 16px; box-sizing: border-box; font-size: 14px; transition: all 0.3s ease; }
        input:focus { outline: none; border-color: #d4af37; box-shadow: 0 0 15px rgba(212, 175, 55, 0.2); background: rgba(15, 23, 42, 0.95); }
        .password-container input { padding-right: 45px; }
        .toggle-password { position: absolute; right: 14px; background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 16px; padding: 0; width: auto; }
        .toggle-password:hover { color: #d4af37; }
        button[type="submit"] { background: linear-gradient(135deg, #d4af37 0%, #aa771c 100%); color: #0f172a; border: none; padding: 14px; border-radius: 12px; cursor: pointer; width: 100%; font-size: 13px; font-family: 'Cinzel', serif; font-weight: 800; letter-spacing: 1.5px; margin-top: 10px; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3); }
        button[type="submit"]:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5); }
        .error { color: #f87171; font-size: 12px; text-align: center; margin-bottom: 15px; }
        .links { margin-top: 20px; text-align: center; font-size: 13px; color: #94a3b8; }
        .links a { color: #d4af37; text-decoration: none; font-weight: 500; transition: color 0.2s; }
        .links a:hover { color: #f3e5ab; text-decoration: underline; }
    </style>
</head>
<body>
    <div class="login-card">
        <h3>Captcha Checker</h3>
        <div id="error-msg" class="error"></div>
        <form method="POST" action="/login">
            <div class="input-group">
                <label>Username</label>
                <input type="text" name="username" required autocomplete="off">
            </div>
            <div class="input-group">
                <label>Password</label>
                <div class="password-container">
                    <input type="password" name="password" id="password" required>
                    <button type="button" class="toggle-password" onclick="togglePassword('password', this)">👁️</button>
                </div>
            </div>
            <button type="submit">AUTENTIKASI</button>
        </form>
        <div class="links">
            Belum terdaftar? <a href="/register">Inisialisasi Akun</a><br>
            <a href="/forgot-password" style="color: #94a3b8; font-size: 11px; display: inline-block; margin-top: 12px;">Keamanan & Pemulihan</a>
        </div>
    </div>
    <script>
        function togglePassword(fieldId, btn) {
            const field = document.getElementById(fieldId);
            if (field.type === "password") {
                field.type = "text";
                btn.innerText = "👁‍🗨";
            } else {
                field.type = "password";
                btn.innerText = "👁️";
            }
        }
    </script>
</body>
</html>
"""

REGISTER_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daftar - Google Captcha Checker Systems</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: radial-gradient(circle at 50% 0%, #1a1c29 0%, #090a0f 100%); color: #f1f5f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
        .login-card { background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%); backdrop-filter: blur(20px); padding: 40px; border-radius: 24px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px rgba(212, 175, 55, 0.08); border: 1px solid rgba(212, 175, 55, 0.2); width: 380px; position: relative; }
        .login-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, #d4af37, transparent); }
        h3 { margin-top: 0; text-align: center; font-family: 'Cinzel', serif; font-weight: 800; letter-spacing: 2px; color: #f8fafc; font-size: 22px; margin-bottom: 10px; text-transform: uppercase; background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .badge-bonus { text-align: center; background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); border-radius: 8px; padding: 6px; font-size: 11px; font-weight: 600; margin-bottom: 20px; }
        .input-group { margin-bottom: 20px; }
        label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #d4af37; margin-bottom: 8px; font-weight: 600; }
        .password-container { position: relative; display: flex; align-items: center; }
        input { width: 100%; background: rgba(15, 23, 42, 0.8); color: #fff; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 14px 16px; box-sizing: border-box; font-size: 14px; transition: all 0.3s ease; }
        input:focus { outline: none; border-color: #d4af37; box-shadow: 0 0 15px rgba(212, 175, 55, 0.2); background: rgba(15, 23, 42, 0.95); }
        .password-container input { padding-right: 45px; }
        .toggle-password { position: absolute; right: 14px; background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 16px; padding: 0; width: auto; }
        .toggle-password:hover { color: #d4af37; }
        button[type="submit"] { background: linear-gradient(135deg, #d4af37 0%, #aa771c 100%); color: #0f172a; border: none; padding: 14px; border-radius: 12px; cursor: pointer; width: 100%; font-size: 13px; font-family: 'Cinzel', serif; font-weight: 800; letter-spacing: 1.5px; margin-top: 10px; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3); }
        button[type="submit"]:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5); }
        .error { color: #f87171; font-size: 12px; text-align: center; margin-bottom: 15px; }
        .links { margin-top: 20px; text-align: center; font-size: 13px; color: #94a3b8; }
        .links a { color: #d4af37; text-decoration: none; font-weight: 500; transition: color 0.2s; }
        .links a:hover { color: #f3e5ab; text-decoration: underline; }
    </style>
</head>
<body>
    <div class="login-card">
        <h3>Registrasi Sistem</h3>
        <div class="badge-bonus">🔒 Maksimal 3 Akun per Perangkat HP</div>
        <div id="error-msg" class="error"></div>
        <form method="POST" action="/register">
            <div class="input-group">
                <label>Username Baru</label>
                <input type="text" name="username" required autocomplete="off">
            </div>
            <div class="input-group">
                <label>Password Baru</label>
                <div class="password-container">
                    <input type="password" name="password" id="reg-password" required>
                    <button type="button" class="toggle-password" onclick="togglePassword('reg-password', this)">👁️</button>
                </div>
            </div>
            <button type="submit">DAFTAR & MASUK</button>
        </form>
        <div class="links">
            Sudah memiliki hak akses? <a href="/login">Autentikasi</a>
        </div>
    </div>
    <script>
        function togglePassword(fieldId, btn) {
            const field = document.getElementById(fieldId);
            if (field.type === "password") {
                field.type = "text";
                btn.innerText = "🙈";
            } else {
                field.type = "password";
                btn.innerText = "👁️";
            }
        }
    </script>
</body>
</html>
"""

FORGOT_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pemulihan - Google Captcha Checker Systems</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: radial-gradient(circle at 50% 0%, #1a1c29 0%, #090a0f 100%); color: #f1f5f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%); backdrop-filter: blur(20px); padding: 40px; border-radius: 24px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px rgba(212, 175, 55, 0.08); border: 1px solid rgba(212, 175, 55, 0.2); width: 380px; text-align: center; position: relative; }
        .login-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, #d4af37, transparent); }
        h3 { margin-top: 0; font-family: 'Cinzel', serif; font-weight: 800; color: #f87171; letter-spacing: 1px; font-size: 20px; }
        p { font-size: 13px; color: #94a3b8; line-height: 1.6; margin-bottom: 25px; }
        .btn-register { background: linear-gradient(135deg, #d4af37 0%, #aa771c 100%); color: #0f172a; border: none; padding: 14px; border-radius: 12px; cursor: pointer; width: 100%; font-size: 13px; font-family: 'Cinzel', serif; font-weight: 800; letter-spacing: 1.5px; text-decoration: none; display: inline-block; box-sizing: border-box; box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3); transition: all 0.3s ease; }
        .btn-register:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5); }
        .back-link { display: block; margin-top: 20px; font-size: 13px; color: #94a3b8; text-decoration: none; transition: color 0.2s; }
        .back-link:hover { color: #d4af37; }
    </style>
</head>
<body>
    <div class="login-card">
        <h3>Protokol Keamanan</h3>
        <p>Sesuai standar enkripsi tingkat tinggi, pemulihan kata sandi tidak diizinkan. Anda diwajibkan untuk menginisialisasi entitas akun baru.</p>
        <a href="/register" class="btn-register">INISIALISASI AKUN</a>
        <a href="/login" class="back-link">Kembali ke Autentikasi</a>
    </div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- TAMBAHAN SEO TITLE & META DESCRIPTION -->
    <title>Google Captcha Checker - Intelligent Account Verifier</title>
    <meta name="description" content="Sistem pengecekan akun Google otomatis dan cerdas untuk memverifikasi status email secara cepat dan akurat.">

    <!-- Midtrans Snap JS Script -->
    <script type="text/javascript" src="https://app.sandbox.midtrans.com/snap/snap.js" data-client-key="Mid-client-KyjVIKjIiP-gRRnQ"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');

        body { 
            font-family: 'Plus Jakarta Sans', sans-serif; 
            background: radial-gradient(circle at 50% 0%, #1a1c29 0%, #090a0f 100%); 
            color: #f1f5f9; 
            padding: 30px 15px; 
            margin: 0; 
            min-height: 100vh;
        }
        
        .container { max-width: 650px; margin: auto; }
        
        .card { 
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.75) 100%); 
            backdrop-filter: blur(20px);
            padding: 25px; 
            border-radius: 20px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1); 
            margin-bottom: 20px; 
            border: 1px solid rgba(212, 175, 55, 0.15); 
            position: relative;
        }

        .card::after {
            content: '';
            position: absolute;
            top: 0; left: 30px; right: 30px; height: 1px;
            background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.3), transparent);
        }

        .header-flex { display: flex; flex-direction: column; gap: 15px; }
        
        @keyframes shine {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        .brand-container {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .brand-title {
            font-family: 'Cinzel', serif;
            font-weight: 800;
            font-size: 18px;
            letter-spacing: 1.5px;
            display: inline-flex;
            align-items: center;
            background: linear-gradient(90deg, #ffffff 0%, #cbd5e1 30%, #38bdf8 50%, #ffffff 70%, #cbd5e1 100%);
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: shine 4s linear infinite;
        }

        .verified-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #1d9bf0;
            color: #ffffff;
            border-radius: 50%;
            width: 16px;
            height: 16px;
            font-size: 10px;
            font-weight: bold;
            box-shadow: 0 0 10px rgba(29, 155, 240, 0.6);
            flex-shrink: 0;
            -webkit-text-fill-color: #ffffff;
        }

        .header-actions { display: flex; align-items: center; gap: 10px; }

        .btn-logout { 
            background: rgba(239, 68, 68, 0.15); 
            color: #f87171; 
            border: 1px solid rgba(239, 68, 68, 0.3); 
            padding: 8px 16px; 
            border-radius: 8px; 
            cursor: pointer; 
            font-size: 11px; 
            font-weight: 700; 
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
        }
        .btn-logout:hover { background: #ef4444; color: white; box-shadow: 0 0 15px rgba(239, 68, 68, 0.4); }

        .btn-admin {
            background: rgba(212, 175, 55, 0.15);
            color: #d4af37;
            border: 1px solid rgba(212, 175, 55, 0.3);
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .btn-admin:hover { background: #d4af37; color: #0f172a; box-shadow: 0 0 15px rgba(212, 175, 55, 0.4); }

        .btn-telegram {
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.3s ease;
        }
        .btn-telegram:hover {
            background: #38bdf8;
            color: #0f172a;
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
        }

        .credit-card {
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.1) 0%, rgba(15, 23, 42, 0.6) 100%);
            border: 1px solid rgba(212, 175, 55, 0.3);
            border-radius: 14px;
            padding: 15px 20px;
            margin-top: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .credit-info { display: flex; flex-direction: column; }
        .credit-label { font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
        .credit-val { font-family: 'Cinzel', serif; font-size: 22px; font-weight: 800; color: #34d399; margin-top: 2px; }
        .credit-rate { font-size: 11px; color: #d4af37; font-weight: 500; margin-top: 2px; }
        
        textarea { 
            width: 100%; 
            height: 140px; 
            background: rgba(10, 15, 30, 0.9); 
            color: #f8fafc; 
            border: 1px solid rgba(255, 255, 255, 0.1); 
            border-radius: 12px; 
            padding: 15px; 
            box-sizing: border-box; 
            resize: none; 
            font-size: 13px; 
            font-family: monospace;
            transition: all 0.3s ease;
        }
        textarea:focus {
            outline: none;
            border-color: #d4af37;
            box-shadow: 0 0 15px rgba(212, 175, 55, 0.15);
        }

        .btn-group { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px; margin-top: 12px; }
        
        button { 
            background: linear-gradient(135deg, #d4af37 0%, #aa771c 100%); 
            color: #0f172a; 
            border: none; 
            padding: 12px; 
            border-radius: 10px; 
            cursor: pointer; 
            font-size: 12px; 
            font-family: 'Cinzel', serif;
            font-weight: 800;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(212, 175, 55, 0.2);
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(212, 175, 55, 0.4); }
        button:disabled { background: #334155; color: #64748b; cursor: not-allowed; box-shadow: none; transform: none; }
        
        .btn-clear { background: rgba(71, 85, 105, 0.4); color: #cbd5e1; border: 1px solid rgba(255,255,255,0.05); }
        .btn-clear:hover { background: rgba(100, 116, 139, 0.6); color: #fff; box-shadow: none; }
        
        .btn-stop { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
        .btn-stop:hover { background: #ef4444; color: white; box-shadow: 0 0 15px rgba(239, 68, 68, 0.4); }
        .btn-stop:disabled { background: #334155; color: #64748b; border: none; }

        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 5px; }
        .stat-box { 
            background: rgba(10, 15, 30, 0.6); 
            padding: 16px; 
            border-radius: 12px; 
            border: 1px solid rgba(255, 255, 255, 0.05); 
            display: flex; 
            flex-direction: column; 
            justify-content: space-between; 
            position: relative;
            overflow: hidden;
        }
        .stat-box.full { grid-column: span 2; display: block; text-align: center; }
        .stat-num { font-size: 26px; font-weight: 800; margin-top: 6px; font-family: 'Cinzel', serif; letter-spacing: 1px; }
        
        .btn-copy { 
            background: rgba(212, 175, 55, 0.1); 
            border: 1px solid rgba(212, 175, 55, 0.3); 
            margin-top: 12px; 
            width: 100%; 
            padding: 10px; 
            border-radius: 8px; 
            cursor: pointer; 
            color: #d4af37; 
            font-weight: 700; 
            font-size: 11px; 
            letter-spacing: 1px;
            transition: all 0.2s;
        }
        .btn-copy:hover { background: #d4af37; color: #0f172a; box-shadow: 0 0 15px rgba(212, 175, 55, 0.4); }
        
        .btn-copy-valid { 
            background: rgba(52, 211, 153, 0.1); 
            border: 1px solid rgba(52, 211, 153, 0.3); 
            margin-top: 12px; 
            width: 100%; 
            padding: 10px; 
            border-radius: 8px; 
            cursor: pointer; 
            color: #34d399; 
            font-weight: 700; 
            font-size: 11px; 
            letter-spacing: 1px;
            transition: all 0.2s;
        }
        .btn-copy-valid:hover { background: #34d399; color: #0f172a; box-shadow: 0 0 15px rgba(52, 211, 153, 0.4); }

        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
        th { color: #d4af37; font-family: 'Cinzel', serif; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }
        
        .badge-valid { background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); padding: 4px 8px; border-radius: 6px; font-weight: 700; font-size: 10px; letter-spacing: 0.5px; }
        .badge-captcha { background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); padding: 4px 8px; border-radius: 6px; font-weight: 700; font-size: 10px; letter-spacing: 0.5px; }
        .badge-invalid { background: rgba(248, 113, 113, 0.15); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); padding: 4px 8px; border-radius: 6px; font-weight: 700; font-size: 10px; letter-spacing: 0.5px; }
        
        @keyframes pulse-animation {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(0.99); }
            100% { opacity: 1; transform: scale(1); }
        }
        .processing-anim {
            animation: pulse-animation 1.2s infinite ease-in-out;
            background: linear-gradient(135deg, #b8860b 0%, #8b6508 100%) !important;
            color: #fff !important;
        }

        #toast {
            visibility: hidden;
            min-width: 250px;
            background: rgba(15, 23, 42, 0.95);
            color: #d4af37;
            text-align: center;
            border-radius: 12px;
            padding: 14px;
            position: fixed;
            z-index: 1000;
            right: 25px;
            top: 25px;
            border: 1px solid rgba(212, 175, 55, 0.3);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            font-size: 13px;
            font-weight: 600;
            opacity: 0;
            transition: opacity 0.3s ease, top 0.3s ease;
        }
        #toast.show { visibility: visible; opacity: 1; top: 35px; }

        #done-modal {
            display: none;
            position: fixed;
            z-index: 2000;
            left: 0; top: 0; width: 100%; height: 100%;
            background-color: rgba(9, 10, 15, 0.85);
            backdrop-filter: blur(8px);
            justify-content: center;
            align-items: center;
        }
        
        .modal-box {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid rgba(212, 175, 55, 0.4);
            padding: 28px;
            border-radius: 24px;
            text-align: center;
            box-shadow: 0 25px 60px rgba(0,0,0,0.7), 0 0 30px rgba(212, 175, 55, 0.1);
            animation: bounce-in 0.4s ease;
            max-width: 380px;
            width: 88%;
        }

        @keyframes bounce-in {
            0% { transform: scale(0.7); opacity: 0; }
            80% { transform: scale(1.03); opacity: 1; }
            100% { transform: scale(1); opacity: 1; }
        }
        .modal-desc {
            color: #94a3b8;
            font-size: 12px;
            margin-bottom: 15px;
            line-height: 1.5;
        }

        .done-title {
            font-size: 32px;
            font-family: 'Cinzel', serif;
            font-weight: 800;
            color: #34d399;
            margin-bottom: 12px;
            letter-spacing: 2px;
        }
        .btn-done-close {
            background: linear-gradient(135deg, #d4af37 0%, #aa771c 100%);
            color: #0f172a;
            border: none;
            padding: 14px;
            border-radius: 12px;
            font-size: 12px;
            font-family: 'Cinzel', serif;
            font-weight: 800;
            letter-spacing: 1.5px;
            cursor: pointer;
            width: 100%;
            box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3);
            transition: all 0.3s;
        }
        .btn-done-close:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5); }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header-flex">
                <div class="brand-container">
                    <div class="brand-title">Google Captcha Checker</div>
                    <span class="verified-badge" title="Verified System">✓</span>
                </div>
                <div class="header-actions">
                    __ADMIN_BTN__
                    <a href="https://t.me/Googlechecker" target="_blank" class="btn-telegram">
                        💬 Admin TOP UP
                    </a>
                    <button class="btn-logout" onclick="window.location.href='/logout'">LOGOUT</button>
                </div>
            </div>

            <div class="credit-card">
                <div class="credit-info">
                    <div class="credit-label">Saldo Kredit Aktif</div>
                    <div class="credit-val" id="user-balance">Rp0</div>
                    <div class="credit-rate">⚡ Rp50 / 1 Email Check</div>
                </div>
            </div>

            <div style="background: rgba(15, 23, 42, 0.5); border: 1px dashed rgba(212, 175, 55, 0.25); border-radius: 12px; padding: 12px 18px; margin-top: 15px; font-size: 11px; color: #cbd5e1; display: flex; justify-content: space-between; align-items: center;">
                <span style="display: flex; align-items: center; gap: 6px;"><span style="font-size: 14px;">⏱️</span> Estimasi Waktu Proses:</span>
                <span id="estimasi-waktu" style="color: #d4af37; font-weight: 700; font-family: monospace;">Masukkan email untuk estimasi</span>
            </div>

            <textarea id="emails" placeholder="Masukkan deretan target email (1 baris per entitas)..." style="margin-top: 15px;"></textarea>
            <input type="hidden" id="workers" value="5">
            <div class="btn-group">
                <button id="btn-mulai" onclick="mulaiCek()">START</button>
                <button id="btn-clear" class="btn-clear" onclick="clearText()">CLEAR</button>
                <button id="btn-batal" class="btn-stop" onclick="batalkanCek()" disabled>STOP</button>
            </div>
        </div>

        <div class="card">
            <div class="stats-grid">
                <div class="stat-box full">
                    <div style="color: #94a3b8; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600;">Progres Eksekusi Sistem</div>
                    <div class="stat-num" style="color: #f8fafc;"><span id="progress-selesai">0</span> <span style="color: #475569; font-size: 18px;">/</span> <span id="total-input">0</span></div>
                </div>
                
                <div class="stat-box" style="border-left: 3px solid #34d399;">
                    <div>
                        <div style="color: #34d399; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600;">CLEAN</div>
                        <div class="stat-num" id="total-valid" style="color: #34d399;">0</div>
                    </div>
                    <button class="btn-copy-valid" onclick="copyHasilValid()">📋 Salin Valid</button>
                </div>
                
                <div class="stat-box" style="border-left: 3px solid #fbbf24;">
                    <div>
                        <div style="color: #fbbf24; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600;">CAPTCHA</div>
                        <div class="stat-num" id="total-captcha" style="color: #fbbf24;">0</div>
                    </div>
                    <button class="btn-copy" onclick="copyHasilCaptcha()">📋 Salin Captcha</button>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="brand-title" style="font-size: 13px; margin-bottom: 12px;">
                Pengecekan sedang Berlangsung
                <span class="verified-badge" style="width: 12px; height: 12px; font-size: 8px; margin-left: 6px;">✓</span>
            </div>
            <div style="max-height: 240px; overflow-y: auto;">
                <table id="tabel-hasil">
                    <thead>
                        <tr>
                            <th style="width: 50px;">No</th>
                            <th>Alamat Email</th>
                            <th style="width: 110px;">Status Email</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="3" style="text-align: center; color: #475569; font-style: italic;">Belum ada telemetri aktif</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="done-modal">
        <div class="modal-box">
            <div class="done-title">SELESAI</div>
            <div class="modal-desc">Checker Done</div>
            <button class="btn-done-close" onclick="tutupModalDone()">TUTUP</button>
        </div>
    </div>

    <div id="toast">Notifikasi Sistem</div>

    <script>
        let pollInterval = null;
        let toastTimeout = null;
        let wasRunning = false;

        document.addEventListener("DOMContentLoaded", () => {
            tarikStatus();
        });

        document.getElementById("emails").addEventListener("input", function() {
            let lines = this.value.trim().split('\\n').filter(e => e.trim() !== "");
            let count = lines.length;
            let estEl = document.getElementById("estimasi-waktu");
            if (count === 0) {
                estEl.innerText = "Masukkan email untuk estimasi";
            } else {
                let totalSeconds = Math.ceil((count * 2.5) / 5);
                if (totalSeconds < 60) {
                    estEl.innerText = `~ ${totalSeconds} detik (${count} email)`;
                } else {
                    let minutes = (totalSeconds / 60).toFixed(1);
                    estEl.innerText = `~ ${minutes} menit (${count} email)`;
                }
            }
        });

        function playBeepSound() {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioCtx.createOscillator();
                const gainNode = audioCtx.createGain();

                oscillator.type = 'sine';
                oscillator.frequency.setValueAtTime(880, audioCtx.currentTime);
                gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.8);

                oscillator.connect(gainNode);
                gainNode.connect(audioCtx.destination);

                oscillator.start();
                oscillator.stop(audioCtx.currentTime + 0.8);
            } catch (e) {}
        }

        function showToast(message) {
            let toast = document.getElementById("toast");
            toast.innerText = message;
            toast.className = "show";
            if (toastTimeout) clearTimeout(toastTimeout);
            toastTimeout = setTimeout(() => { toast.className = ""; }, 3000);
        }

        function clearText() {
            document.getElementById("emails").value = "";
            document.getElementById("estimasi-waktu").innerText = "Masukkan email untuk estimasi";
            showToast("✨ Area input berhasil dibersihkan.");
        }

        function tutupModalDone() {
            document.getElementById("done-modal").style.display = "none";
        }

        async function mulaiCek() {
            let emailsText = document.getElementById("emails").value.trim();
            let workers = document.getElementById("workers").value;
            if (!emailsText) {
                alert("Harap masukkan target email terlebih dahulu!");
                return;
            }

            let daftarEmailMentah = emailsText.split('\\n').map(e => e.trim()).filter(e => e);
            let seen = new Set();
            let duplicateCount = 0;
            let daftarEmail = [];
            const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
            
            for (let e of daftarEmailMentah) {
                let eLower = e.toLowerCase();
                if (emailRegex.test(eLower)) {
                    if (seen.has(eLower)) {
                        duplicateCount++;
                    } else {
                        seen.add(eLower);
                        daftarEmail.push(e);
                    }
                }
            }

            if (duplicateCount > 0) {
                showToast(`⚠️ Terdeteksi ${duplicateCount} email duplikat diabaikan.`);
            }

            let btnMulai = document.getElementById("btn-mulai");
            let btnBatal = document.getElementById("btn-batal");
            
            btnMulai.disabled = true;
            btnMulai.classList.add("processing-anim");
            btnMulai.innerText = "⏳ MEMPROSES...";
            btnBatal.disabled = false;
            wasRunning = true;

            let res = await fetch('/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ emails: daftarEmail, workers: parseInt(workers) })
            });
            let resData = await res.json();

            if (resData.status === "insufficient_balance") {
                alert(resData.message);
                btnMulai.disabled = false;
                btnMulai.classList.remove("processing-anim");
                btnMulai.innerText = "START";
                btnBatal.disabled = true;
                return;
            }

            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(tarikStatus, 500);
        }

        async function batalkanCek() {
            let btnBatal = document.getElementById("btn-batal");
            btnBatal.disabled = true;
            btnBatal.innerText = "⏳ MENGHENTIKAN...";
            await fetch('/stop', { method: 'POST' });
            showToast("🛑 Menghentikan seluruh proses worker...");
        }

        async function tarikStatus() {
            let res = await fetch('/status');
            let data = await res.json();

            if (data.balance !== undefined) {
                document.getElementById("user-balance").innerText = "Rp" + data.balance.toLocaleString("id-ID");
            }

            document.getElementById("total-input").innerText = data.total;
            document.getElementById("progress-selesai").innerText = data.selesai;
            document.getElementById("total-valid").innerText = data.valid_count;
            document.getElementById("total-captcha").innerText = data.captcha_count;

            let tbody = document.querySelector("#tabel-hasil tbody");
            if (data.results && data.results.length > 0) {
                tbody.innerHTML = "";
                data.results.forEach((item, index) => {
                    let badgeClass = "badge-invalid";
                    if (item.status === "VALID") badgeClass = "badge-valid";
                    else if (item.status.includes("CAPTCHA")) badgeClass = "badge-captcha";

                    let badge = `<span class="${badgeClass}">${item.status}</span>`;
                    tbody.innerHTML += `<tr>
                        <td style="color: #64748b;">${index + 1}</td>
                        <td style="font-family: monospace;">${item.email}</td>
                        <td>${badge}</td>
                    </tr>`;
                });
                let logContainer = tbody.parentElement.parentElement;
                logContainer.scrollTop = logContainer.scrollHeight;
            }

            if (!data.is_running && wasRunning) {
                wasRunning = false;
                clearInterval(pollInterval);
                
                let btnMulai = document.getElementById("btn-mulai");
                let btnBatal = document.getElementById("btn-batal");
                
                btnMulai.disabled = false;
                btnMulai.classList.remove("processing-anim");
                btnMulai.innerText = "START";
                btnBatal.disabled = false;
                btnBatal.innerText = "HENTIKAN";

                document.getElementById("done-modal").style.display = "flex";
                playBeepSound();
            }
        }

        function salinTeks(textToCopy, pesanSukses) {
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    showToast(pesanSukses);
                }).catch(() => {
                    fallbackSalinTeks(textToCopy, pesanSukses);
                });
            } else {
                fallbackSalinTeks(textToCopy, pesanSukses);
            }
        }

        function fallbackSalinTeks(textToCopy, pesanSukses) {
            let textArea = document.createElement("textarea");
            textArea.value = textToCopy;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                document.execCommand('copy');
                showToast(pesanSukses);
            } catch (err) {
                alert("Gagal menyalin teks secara otomatis.");
            }
            document.body.removeChild(textArea);
        }

        function copyHasilCaptcha() {
            fetch('/status')
            .then(res => res.json())
            .then(data => {
                let textToCopy = data.results
                    .filter(item => item.status.includes("CAPTCHA"))
                    .map(item => item.email)
                    .join('\\n');
            
                if (!textToCopy) {
                    alert("Tidak ada entitas Captcha yang dapat disalin.");
                    return;
                }
                salinTeks(textToCopy, "📋 Berhasil menyalin email Captcha.");
            });
        }

        function copyHasilValid() {
            fetch('/status')
            .then(res => res.json())
            .then(data => {
                let textToCopy = data.results
                    .filter(item => item.status === "VALID")
                    .map(item => item.email)
                    .join('\\n');
            
                if (!textToCopy) {
                    alert("Tidak ada entitas Valid yang dapat disalin.");
                    return;
                }
                salinTeks(textToCopy, "📋 Berhasil menyalin email Valid.");
            });
        }
    </script>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - Management Saldo & Device</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: radial-gradient(circle at 50% 0%, #1a1c29 0%, #090a0f 100%); color: #f1f5f9; padding: 30px 15px; margin: 0; min-height: 100vh; }
        .container { max-width: 900px; margin: auto; }
        .card { background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.75) 100%); backdrop-filter: blur(20px); padding: 25px; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); margin-bottom: 20px; border: 1px solid rgba(212, 175, 55, 0.15); }
        .header-flex { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px; }
        .brand-title { font-family: 'Cinzel', serif; font-weight: 800; font-size: 18px; letter-spacing: 1.5px; color: #d4af37; }
        .btn-back { background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 11px; font-weight: 700; text-decoration: none; transition: all 0.3s; }
        .btn-back:hover { background: #94a3b8; color: #0f172a; }
        
        .search-container { margin-bottom: 20px; display: flex; gap: 10px; }
        .search-input { flex: 1; background: rgba(10, 15, 30, 0.9); border: 1px solid rgba(212, 175, 55, 0.3); border-radius: 10px; padding: 12px 16px; color: #fff; font-size: 13px; outline: none; transition: all 0.3s; }
        .search-input:focus { border-color: #d4af37; box-shadow: 0 0 10px rgba(212, 175, 55, 0.2); }

        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
        th { color: #d4af37; font-family: 'Cinzel', serif; font-size: 11px; letter-spacing: 1px; }
        input[type="number"] { background: rgba(10, 15, 30, 0.9); border: 1px solid rgba(212, 175, 55, 0.3); border-radius: 8px; padding: 8px 10px; color: #34d399; font-family: monospace; width: 100px; }
        .btn-update { background: linear-gradient(135deg, #34d399 0%, #059669 100%); color: #0f172a; border: none; padding: 8px 14px; border-radius: 8px; font-weight: 700; font-size: 11px; cursor: pointer; transition: all 0.2s; }
        .btn-update:hover { transform: translateY(-1px); box-shadow: 0 0 12px rgba(52, 211, 153, 0.4); }
        .device-badge { font-size: 11px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.2); display: inline-block; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header-flex">
                <div class="brand-title">⚙️ DASHBOARD ADMIN (MANAJEMEN AKUN & DEVICE)</div>
                <a href="/" class="btn-back">⯇ KEMBALI KE MAIN APP</a>
            </div>

            <div class="search-container">
                <input type="text" id="searchInput" class="search-input" placeholder="🔍 Cari username terdaftar..." onkeyup="filterTable()">
            </div>

            <table id="userTable">
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Device ID / HP UUID</th>
                        <th>User-Agent HP</th>
                        <th>Saldo Saat Ini</th>
                        <th>Set Saldo Baru (Rp)</th>
                        <th>Aksi</th>
                    </tr>
                </thead>
                <tbody>
                    __USER_ROWS__
                </tbody>
            </table>
        </div>
    </div>
    <script>
        function filterTable() {
            let input = document.getElementById("searchInput");
            let filter = input.value.toLowerCase();
            let table = document.getElementById("userTable");
            let tr = table.getElementsByTagName("tr");

            for (let i = 1; i < tr.length; i++) {
                let tdUsername = tr[i].getElementsByTagName("td")[0];
                if (tdUsername) {
                    let txtValue = tdUsername.textContent || tdUsername.innerText;
                    if (txtValue.toLowerCase().indexOf(filter) > -1) {
                        tr[i].style.display = "";
                    } else {
                        tr[i].style.display = "none";
                    }
                }
            }
        }

        async function updateBalance(username) {
            let inputEl = document.getElementById("bal-" + username);
            let newBalance = parseInt(inputEl.value);

            if (isNaN(newBalance) || newBalance < 0) {
                alert("Masukkan jumlah saldo yang valid!");
                return;
            }

            try {
                let res = await fetch('/admin/update-balance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `target_user=${encodeURIComponent(username)}&new_balance=${newBalance}`
                });
                let data = await res.json();

                if (data.status === "success") {
                    alert(`Saldo pengguna ${username} berhasil diubah menjadi Rp${newBalance.toLocaleString('id-ID')}`);
                    location.reload();
                } else {
                    alert("Gagal mengubah saldo: " + (data.message || "Unknown Error"));
                }
            } catch (e) {
                alert("Terjadi kesalahan jaringan.");
            }
        }
    </script>
</body>
</html>
"""

def check_auth(request: Request) -> str:
    return request.cookies.get("username")

def get_or_create_device_uuid(request: Request, response: Response) -> str:
    device_uuid = request.cookies.get("device_uuid")
    if not device_uuid:
        device_uuid = str(uuid.uuid4())
        response.set_cookie(key="device_uuid", value=device_uuid, max_age=315360000, httponly=True)
    return device_uuid

def get_or_create_user_uid(request: Request, response: Response) -> str:
    uid = request.cookies.get("user_session_id")
    if not uid:
        uid = str(uuid.uuid4())
        response.set_cookie(key="user_session_id", value=uid, httponly=True)
    
    async def touch_session():
        async with sessions_lock:
            if uid in sessions_state:
                sessions_state[uid]["last_active"] = time.time()
    
    asyncio.create_task(touch_session())
    return uid

async def cleanup_old_sessions():
    while True:
        await asyncio.sleep(1800)
        now = time.time()
        async with sessions_lock:
            expired_uids = [
                uid for uid, data in sessions_state.items()
                if not data.get("is_running", False) and (now - data.get("last_active", now) > 3600)
            ]
            for uid in expired_uids:
                del sessions_state[uid]

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_old_sessions())

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if check_auth(request):
        return RedirectResponse(url="/", status_code=303)
    return LOGIN_TEMPLATE

@app.post("/login", response_class=HTMLResponse)
async def login_submit(username: str = Form(...), password: str = Form(...)):
    user_info = get_user_data(username)
    if user_info and user_info["password"] == password:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="is_logged_in", value="true", httponly=True)
        response.set_cookie(key="username", value=username, httponly=True)
        return response
    
    error_script = '<script>document.getElementById("error-msg").innerHTML = "Autentikasi gagal! Periksa kredensial atau <a href=\'/register\'>Register new account</a>.";</script>'
    return LOGIN_TEMPLATE + error_script

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, response: Response):
    if check_auth(request):
        return RedirectResponse(url="/", status_code=303)
    get_or_create_device_uuid(request, response)
    return REGISTER_TEMPLATE

@app.post("/register", response_class=HTMLResponse)
async def register_submit(request: Request, response: Response, username: str = Form(...), password: str = Form(...)):
    if not username.strip() or not password.strip():
        error_script = '<script>document.getElementById("error-msg").innerText = "Kolom username dan password wajib diisi!";</script>'
        return REGISTER_TEMPLATE + error_script
        
    user_agent = request.headers.get("user-agent", "Unknown Device")
    device_uuid = get_or_create_device_uuid(request, response)
    
    success, message = save_user(username, password, user_agent, device_uuid)
    if not success:
        error_script = f'<script>document.getElementById("error-msg").innerText = "{message}";</script>'
        return REGISTER_TEMPLATE + error_script
        
    response.status_code = 303
    response.headers["Location"] = "/"
    response.set_cookie(key="is_logged_in", value="true", httponly=True)
    response.set_cookie(key="username", value=username, httponly=True)
    return response

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page():
    return FORGOT_PASSWORD_TEMPLATE

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="is_logged_in")
    response.delete_cookie(key="username")
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, response: Response):
    username = check_auth(request)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
        
    uid = get_or_create_user_uid(request, response)
    async with sessions_lock:
        if uid not in sessions_state:
            sessions_state[uid] = {
                "total": 0, "selesai": 0, "valid_count": 0,
                "captcha_count": 0, "invalid_count": 0,
                "results": [], "is_running": False, "last_active": time.time()
            }
            
    admin_button = '<a href="/admin" class="btn-admin">⚙️ DASHBOARD ADMIN</a>' if username == "admin" else ''
    rendered_html = HTML_TEMPLATE.replace("__ADMIN_BTN__", admin_button).replace("Mid-client-KyjVIKjIiP-gRRnQ", MIDTRANS_CLIENT_KEY)
    return rendered_html

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    username = check_auth(request)
    if not username or username != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak. Hanya untuk akun Admin.")

    users = get_all_users()
    rows_html = ""
    for u in users:
        rows_html += f"""
        <tr>
            <td style="font-weight: 700;">{u['username']}</td>
            <td><span class="device-badge" title="{u['device_uuid']}">{u['device_uuid']}</span></td>
            <td><span class="device-badge" title="{u['device_info']}">{u['device_info']}</span></td>
            <td style="color: #34d399; font-family: monospace;">Rp{u['balance']:,}</td>
            <td><input type="number" id="bal-{u['username']}" value="{u['balance']}"></td>
            <td><button class="btn-update" onclick="updateBalance('{u['username']}')">Simpan</button></td>
        </tr>
        """
    return ADMIN_TEMPLATE.replace("__USER_ROWS__", rows_html)

@app.post("/admin/update-balance")
async def admin_update_balance(request: Request, target_user: str = Form(...), new_balance: int = Form(...)):
    username = check_auth(request)
    if not username or username != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")

    success = set_user_balance(target_user, new_balance)
    if success:
        return {"status": "success", "message": f"Saldo {target_user} berhasil diperbarui"}
    return JSONResponse(status_code=400, content={"status": "error", "message": "Gagal memperbarui saldo user"})

@app.post("/create-topup")
async def create_topup(payload: CreateTopupRequest, request: Request):
    username = check_auth(request)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if payload.amount < 1000:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Minimal topup Rp1.000"})
        
    order_id = f"TOPUP-{username}-{int(time.time())}-{random.randint(100, 999)}"
    
    param = {
        "transaction_details": {
            "order_id": order_id,
            "gross_amount": payload.amount
        },
        "customer_details": {
            "first_name": username
        },
        "item_details": [{
            "id": "TOPUP-BALANCE",
            "price": payload.amount,
            "quantity": 1,
            "name": f"Topup Saldo Checker ({username})"
        }]
    }
    
    try:
        transaction = snap.create_transaction(param)
        snap_token = transaction['token']
        save_pending_topup(order_id, username, payload.amount)
        return {"status": "success", "snap_token": snap_token, "order_id": order_id}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/webhook/midtrans")
async def webhook_midtrans(request: Request):
    try:
        notification_body = await request.json()
        transaction_status = notification_body.get('transaction_status')
        order_id = notification_body.get('order_id')
        fraud_status = notification_body.get('fraud_status')

        if transaction_status in ['capture', 'settlement']:
            if fraud_status == 'challenge':
                pass
            else:
                matched_user, amount = process_midtrans_success(order_id)
                if matched_user:
                    return {"status": "success", "message": f"Saldo Rp{amount} berhasil ditambahkan ke {matched_user}"}
        elif transaction_status in ['cancel', 'deny', 'expire']:
            pass
            
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.post("/run")
async def run_checker(payload: RunRequest, request: Request, response: Response):
    username = check_auth(request)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_info = get_user_data(username)
    if not user_info or user_info["balance"] < 50:
        return JSONResponse(status_code=400, content={"status": "insufficient_balance", "message": "Saldo Anda tidak mencukupi (Minimal Rp50 per email). Silakan hubungi admin untuk Top Up."})
        
    uid = get_or_create_user_uid(request, response)
    async with sessions_lock:
        if sessions_state.get(uid, {}).get("is_running", False):
            return {"status": "already running"}

    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    seen = set()
    daftar_email = []
    
    for email in payload.emails:
        email_clean = email.strip()
        email_lower = email_clean.lower()
        if email_regex.match(email_lower):
            if email_lower not in seen:
                seen.add(email_lower)
                daftar_email.append(email_clean)

    async with sessions_lock:
        sessions_state[uid] = {
            "total": len(daftar_email), "selesai": 0, "valid_count": 0,
            "captcha_count": 0, "invalid_count": 0,
            "results": [], "is_running": True, "last_active": time.time()
        }

    asyncio.create_task(jalankan_multi_worker_async(uid, username, daftar_email, payload.workers))
    return {"status": "started", "unique_total": len(daftar_email)}

@app.post("/stop")
async def stop_checker(request: Request, response: Response):
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    uid = get_or_create_user_uid(request, response)
    async with sessions_lock:
        if uid in sessions_state:
            sessions_state[uid]["is_running"] = False
    return {"status": "stopped"}

@app.get("/status")
async def get_status(request: Request, response: Response):
    username = check_auth(request)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    user_info = get_user_data(username)
    current_balance = user_info["balance"] if user_info else 0
    
    uid = get_or_create_user_uid(request, response)
    async with sessions_lock:
        if uid in sessions_state:
            sessions_state[uid]["last_active"] = time.time()
            data = dict(sessions_state[uid])
            data["balance"] = current_balance
            return data
            
    return {"total": 0, "selesai": 0, "valid_count": 0, "captcha_count": 0, "invalid_count": 0, "results": [], "is_running": False, "balance": current_balance}

def simpan_ke_desktop(results: List[dict]):
    try:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_path = os.path.join(desktop_path, "hasil_cek_email.txt")
        
        with open(file_path, "w", encoding="utf-8") as f:
            for item in results:
                f.write(f"{item['email']} | {item['status']}\n")
    except Exception:
        pass

async def worker_task_async(uid: str, username: str, worker_id: int, emails_chunk: List[str]):
    user_data_dir = os.path.join(os.getcwd(), f"temp_profile_{uid[:5]}_{worker_id}_{int(time.time())}")
    
    async with browser_semaphore:
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    executable_path=None,
                    channel="msedge",
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-infobars"],
                    viewport={"width": 1280, "height": 720}
                )

                page = await browser.new_page()

                for email in emails_chunk:
                    async with sessions_lock:
                        if not sessions_state.get(uid, {}).get("is_running", False):
                            break
                    
                    if not deduct_balance(username, cost=50):
                        async with sessions_lock:
                            if uid in sessions_state:
                                sessions_state[uid]["is_running"] = False
                        break
                        
                    status = "VALID"
                    try:
                        await page.goto("https://accounts.google.com/signin/v2/identifier?flowName=GlifWebSignIn&flowEntry=ServiceLogin", timeout=12000)
                        
                        email_input_selector = 'input[type="email"], input#identifierId, input[name="identifier"]'
                        await page.wait_for_selector(email_input_selector, timeout=8000)
                        await page.fill(email_input_selector, email)
                        
                        async with page.expect_navigation(timeout=8000, wait_until="networkidle"):
                            await page.press(email_input_selector, 'Enter')
                    except Exception:
                        pass
                    
                    try:
                        await page.wait_for_load_state("load", timeout=5000)
                        await page.wait_for_load_state("networkidle", timeout=4000)
                    except Exception:
                        pass
                    
                    await page.wait_for_timeout(1500)
                    
                    try:
                        content = (await page.content()).lower()
                        url_sekarang = page.url.lower()
                        
                        if any(keyword in content for keyword in [
                            "recaptcha", "bukan robot", "verifikasi", "challenge", 
                            "pemberitahuan", "confirm", "menyesalkan", "unusual traffic", "sambungkan", "ketuk ya", "menampilkan"
                        ]) or "signin/rejected" in url_sekarang or "denied" in url_sekarang:
                            status = "CAPTCHA"
                        elif any(keyword in content for keyword in [
                            "tidak dapat menemukan akun", "could not find your google account", "cant find your google account"
                        ]):
                            status = "INVALID"
                        else:
                            status = "VALID"
                    except Exception:
                        status = "VALID"
                    
                    async with sessions_lock:
                        if uid in sessions_state:
                            sessions_state[uid]["results"].append({"email": email, "status": status})
                            if status == "VALID":
                                sessions_state[uid]["valid_count"] += 1
                            elif status == "CAPTCHA":
                                sessions_state[uid]["captcha_count"] += 1
                            else:
                                sessions_state[uid]["invalid_count"] += 1
                            sessions_state[uid]["selesai"] += 1
            finally:
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass
                if os.path.exists(user_data_dir):
                    try:
                        shutil.rmtree(user_data_dir)
                    except Exception:
                        pass

async def jalankan_multi_worker_async(uid: str, username: str, daftar_email: List[str], num_works: int):
    chunks = [[] for _ in range(num_works)]
    for i, email in enumerate(daftar_email):
        chunks[i % num_works].append(email)
        
    tasks = [worker_task_async(uid, username, idx + 1, chunk) for idx, chunk in enumerate(chunks) if chunk]
    
    await asyncio.gather(*tasks)
    
    async with sessions_lock:
        if uid in sessions_state:
            sessions_state[uid]["is_running"] = False
            simpan_ke_desktop(sessions_state[uid]["results"])

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)