import sqlite3
import time
import random
import string
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from jose import JWTError, jwt
from typing import Optional
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
import hashlib
import hmac
import os

# FastAPI app
app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bot token and JWT secret
BOT_TOKEN = "8102038373:AAHbEcAMBy7WRS_vUWIDZuhWbQXF4HlqDHc"  # Replace with your bot token
SECRET_KEY = "your-secret-key"  # Replace with a secure key
ALGORITHM = "HS256"
ADMIN_IDS = [5361974069]  # Replace with admin Telegram IDs

# Database setup
db = sqlite3.connect("clicker.db", check_same_thread=False)
cursor = db.cursor()

# Initialize database tables
def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS table1 (
        col1 TEXT PRIMARY KEY,
        col2 TEXT,
        col3 TEXT DEFAULT '0',
        col4 TEXT DEFAULT '1',
        col5 TEXT DEFAULT '0',
        col6 INTEGER DEFAULT 1,
        col7 DATE,
        col8 INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS table2 (
        col1 TEXT PRIMARY KEY,
        col2 INTEGER,
        col3 INTEGER,
        col4 INTEGER,
        col5 TEXT DEFAULT ''
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS table3 (
        col1 TEXT,
        col2 TEXT,
        col3 TEXT CHECK(col3 IN ('pending', 'accepted')),
        PRIMARY KEY (col1, col2)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS table4 (
        col1 TEXT,
        col2 TEXT,
        PRIMARY KEY (col1, col2)
    )
    """)
    cursor.execute("PRAGMA table_info(table3)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'col3' not in columns:
        cursor.execute("ALTER TABLE table3 ADD COLUMN col3 TEXT CHECK(col3 IN ('pending', 'accepted'))")
    
    cursor.execute("PRAGMA table_info(table2)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'col5' not in columns:
        cursor.execute("ALTER TABLE table2 ADD COLUMN col5 TEXT DEFAULT ''")
    
    cursor.execute("PRAGMA table_info(table1)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'col6' not in columns:
        cursor.execute("ALTER TABLE table1 ADD COLUMN col6 INTEGER DEFAULT 1")
    if 'col7' not in columns:
        cursor.execute("ALTER TABLE table1 ADD COLUMN col7 DATE")
    if 'col8' not in columns:
        cursor.execute("ALTER TABLE table1 ADD COLUMN col8 INTEGER")
    
    db.commit()

init_db()

# Pydantic models
class UserData(BaseModel):
    id: int
    username: Optional[str]

class PromoCode(BaseModel):
    activations: int
    coins: int

class Transfer(BaseModel):
    username: str
    amount: int

# Authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_telegram_init_data(init_data: str) -> dict:
    data = dict(pair.split('=') for pair in init_data.split('&') if pair)
    received_hash = data.pop('hash', None)
    user_data = eval(data.get('user', '{}').replace('true', 'True').replace('false', 'False').replace('null', 'None'))
    
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if computed_hash != received_hash:
        raise HTTPException(status_code=401, detail="Invalid initData")
    
    return user_data

async def get_current_user(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
    
    try:
        user_data = verify_telegram_init_data(init_data)
        return UserData(id=user_data.get('id'), username=user_data.get('username'))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid initData")

# Helper functions
def get_user_data(user_id: str, username: str):
    cursor.execute("INSERT OR IGNORE INTO table1 (col1, col2) VALUES (?, ?)", (str(user_id), username))
    db.commit()
    cursor.execute("""
    SELECT col3, col4, col5, col6, col7, col8,
           (SELECT COUNT(*) FROM table4 WHERE col1 = table1.col1) AS referral_count
    FROM table1 WHERE col1 = ?
    """, (str(user_id),))
    return cursor.fetchone()

# Frontend HTML/CSS/JS
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TomClicker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background-color: #f8f9fa; }
        .container { max-width: 600px; margin-top: 20px; }
        .btn-custom { width: 100%; margin-bottom: 10px; }
        #main-menu { display: block; }
        .menu { display: none; }
        .alert { margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="text-center">TomClicker</h1>
        <div id="user-info" class="mb-3"></div>
        <div id="main-menu">
            <button class="btn btn-primary btn-custom" onclick="click()">👆 Click!</button>
            <button class="btn btn-secondary btn-custom" onclick="showMenu('shop')">🛒 Shop</button>
            <button class="btn btn-secondary btn-custom" onclick="showMenu('top-players')">🏆 Top Players</button>
            <button class="btn btn-secondary btn-custom" onclick="showMenu('promo-codes')">🎟 Promo Codes</button>
            <button class="btn btn-secondary btn-custom" onclick="showMenu('friends')">👥 Friends</button>
            <button class="btn btn-secondary btn-custom" onclick="showMenu('referral')">🔗 Referral System</button>
            <button class="btn btn-secondary btn-custom" onclick="showMenu('transfers')">💸 Transfers</button>
            <button class="btn btn-secondary btn-custom" onclick="mango()">🥭 MANGO</button>
            <button class="btn btn-secondary btn-custom" onclick="withdraw()">💰 Withdraw</button>
            <button class="btn btn-danger btn-custom" id="admin-panel" style="display: none;" onclick="showMenu('admin-panel')">⚙ Admin Panel</button>
        </div>
        <div id="shop" class="menu">
            <h2>Shop</h2>
            <button class="btn btn-primary btn-custom" onclick="buyClick(1, 50)">🔽 Buy +1 Click (50 Coins)</button>
            <button class="btn btn-primary btn-custom" onclick="buyClick(2, 100)">🔽 ITER Buy +2 Clicks (100 Coins)</button>
            <button class="btn btn-primary btn-custom" onclick="buyClick(100, 1000)">🔽 Buy +100 Clicks (1000 Coins)</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="top-players" class="menu">
            <h2>Top Players</h2>
            <div id="top-players-list"></div>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="promo-codes" class="menu">
            <h2>Promo Codes</h2>
            <input type="text" id="promo-code-input" class="form-control mb-2" placeholder="Enter promo code">
            <button class="btn btn-primary btn-custom" onclick="activatePromoCode()">Activate</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="friends" class="menu">
            <h2>Friends</h2>
            <button class="btn btn-primary btn-custom" onclick="showMenu('find-friend')">🔍 Find Friend</button>
            <button class="btn btn-primary btn-custom" onclick="listFriends()">📜 List Friends</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="find-friend" class="menu">
            <h2>Find Friend</h2>
            <input type="text" id="friend-username" class="form-control mb-2" placeholder="Enter username">
            <button class="btn btn-primary btn-custom" onclick="findFriend()">Send Request</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="referral" class="menu">
            <h2>Referral System</h2>
            <div id="referral-link"></div>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="transfers" class="menu">
            <h2>Transfers</h2>
            <button class="btn btn-primary btn-custom" onclick="showMenu('transfer-coins')">💰 Transfer Coins</button>
            <button class="btn btn-primary btn-custom" onclick="showMenu('transfer-clicks')">👆 Transfer Clicks</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="transfer-coins" class="menu">
            <h2>Transfer Coins</h2>
            <input type="text" id="transfer-coins-username" class="form-control mb-2" placeholder="Enter username">
            <input type="number" id="transfer-coins-amount" class="form-control mb-2" placeholder="Enter amount">
            <button class="btn btn-primary btn-custom" onclick="transfer('coins')">Transfer</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="transfer-clicks" class="menu">
            <h2>Transfer Clicks</h2>
            <input type="text" id="transfer-clicks-username" class="form-control mb-2" placeholder="Enter username">
            <input type="number" id="transfer-clicks-amount" class="form-control mb-2" placeholder="Enter amount">
            <button class="btn btn-primary btn-custom" onclick="transfer('clicks')">Transfer</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="admin-panel" class="menu">
            <h2>Admin Panel</h2>
            <button class="btn btn-primary btn-custom" onclick="showMenu('manage-promo-codes')">🎟 Manage Promo Codes</button>
            <button class="btn btn-primary btn-custom" onclick="showMenu('set-multiplier')">🔢 Set Multiplier</button>
            <button class="btn btn-primary btn-custom" onclick="resetClicks()">🔄 Reset Clicks</button>
            <button class="btn btn-primary btn-custom" onclick="resetMultiplier()">🔄 Reset Multiplier</button>
            <button class="btn btn-primary btn-custom" id="return-to-top" style="display: none;" onclick="returnToTop()">🔙 Return to Top</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="manage-promo-codes" class="menu">
            <h2>Manage Promo Codes</h2>
            <button class="btn btn-primary btn-custom" onclick="showMenu('create-promo-code')">➕ Create Promo Code</button>
            <button class="btn btn-primary btn-custom" onclick="listPromoCodes()">📋 List Promo Codes</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="create-promo-code" class="menu">
            <h2>Create Promo Code</h2>
            <input type="number" id="promo-activations" class="form-control mb-2" placeholder="Enter activations">
            <input type="number" id="promo-coins" class="form-control mb-2" placeholder="Enter coins">
            <button class="btn btn-primary btn-custom" onclick="createPromoCode()">Create</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="set-multiplier" class="menu">
            <h2>Set Multiplier</h2>
            <p>Warning: Setting a multiplier will remove you from the top players.</p>
            <input type="number" id="multiplier-value" class="form-control mb-2" placeholder="Enter multiplier">
            <button class="btn btn-primary btn-custom" onclick="setMultiplier()">Set</button>
            <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
        </div>
        <div id="alerts"></div>
    </div>
    <script>
        let userId, username;

        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        userId = window.Telegram.WebApp.initDataUnsafe.user.id;
        username = window.Telegram.WebApp.initDataUnsafe.user.username || `user_${userId}`;
        
        async function fetchWithAuth(url, options = {}) {
            options.headers = {
                ...options.headers,
                'X-Telegram-Init-Data': window.Telegram.WebApp.initData
            };
            const response = await fetch(url, options);
            const data = await response.json();
            if (!response.ok) {
                showAlert(data.detail, 'danger');
                throw new Error(data.detail);
            }
            return data;
        }

        async function init() {
            const data = await fetchWithAuth('/api/main');
            updateUserInfo(data);
            if (data.is_admin) document.getElementById('admin-panel').style.display = 'block';
            if (!data.in_top) document.getElementById('return-to-top').style.display = 'block';
        }

        function updateUserInfo(data) {
            const boost = data.referral_count < 10 ? '2%' : data.referral_count < 20 ? '5%' : '15%';
            document.getElementById('user-info').innerHTML = `
                <p>👋 Hello, ${data.username}!</p>
                <p>Clicked: ${data.clicks} 🤑</p>
                <p>Coins: ${data.coins} 💰</p>
                <p>Multiplier: x${data.multiplier}</p>
                <p>Referral Boost: ${boost}</p>
            `;
        }

        function showMenu(menuId) {
            document.querySelectorAll('.menu').forEach(menu => menu.style.display = 'none');
            document.getElementById('main-menu').style.display = 'none';
            document.getElementById(menuId).style.display = 'block';
        }

        function backToMain() {
            document.querySelectorAll('.menu').forEach(menu => menu.style.display = 'none');
            document.getElementById('main-menu').style.display = 'block';
            document.getElementById('alerts').innerHTML = '';
            init();
        }

        function showAlert(message, type) {
            document.getElementById('alerts').innerHTML = `
                <div class="alert alert-${type}">${message}</div>
            `;
        }

        async function click() {
            const data = await fetchWithAuth('/api/click', { method: 'POST' });
            updateUserInfo(data);
        }

        async function buyClick(amount, cost) {
            const data = await fetchWithAuth(`/api/shop/buy-click/${amount}`, { method: 'POST' });
            showAlert('✅ Upgrade purchased!', 'success');
            init();
        }

        async function getTopPlayers() {
            const data = await fetchWithAuth('/api/top-players');
            document.getElementById('top-players-list').innerHTML = data.players.map((p, i) => 
                `${i + 1}. ${p.username} - ${p.clicks} clicks`
            ).join('<br>');
            showMenu('top-players');
        }

        async function activatePromoCode() {
            const code = document.getElementById('promo-code-input').value.trim().toUpperCase();
            if (!code) {
                showAlert('❌ Enter a promo code!', 'danger');
                return;
            }
            const data = await fetchWithAuth('/api/promo-codes/activate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });
            showAlert(`✅ Promo code activated! You got ${data.coins} coins.`, 'success');
            init();
        }

        async function findFriend() {
            const friendUsername = document.getElementById('friend-username').value.trim();
            if (!friendUsername) {
                showAlert('❌ Enter a username!', 'danger');
                return;
            }
            const data = await fetchWithAuth('/api/friends/find', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: friendUsername })
            });
            showAlert(`✅ Friend request sent to @${friendUsername}!`, 'success');
            backToMain();
        }

        async function listFriends() {
            const data = await fetchWithAuth('/api/friends/list');
            document.getElementById('friends').innerHTML = `
                <h2>Friends</h2>
                <p>${data.friends.length ? data.friends.map(f => `@${f}`).join('<br>') : 'No friends yet.'}</p>
                <button class="btn btn-primary btn-custom" onclick="showMenu('find-friend')">🔍 Find Friend</button>
                <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
            `;
            showMenu('friends');
        }

        async function getReferralLink() {
            const data = await fetchWithAuth('/api/referral');
            document.getElementById('referral-link').innerHTML = `Your referral link: <a href="${data.link}">${data.link}</a>`;
            showMenu('referral');
        }

        async function transfer(type) {
            const username = document.getElementById(`transfer-${type}-username`).value.trim();
            const amount = parseInt(document.getElementById(`transfer-${type}-amount`).value);
            if (!username || !amount) {
                showAlert('❌ Enter username and amount!', 'danger');
                return;
            }
            const data = await fetchWithAuth(`/api/transfers/${type}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, amount })
            });
            showAlert(`✅ Transferred ${amount} ${type} to ${username}!`, 'success');
            init();
        }

        async function mango() {
            const data = await fetchWithAuth('/api/mango', { method: 'POST' });
            showAlert(`🥭 Your promo code: ${data.promo_code} (Reward: ${data.coins} coins, ${data.clicks} clicks)`, 'success');
            init();
        }

        async function withdraw() {
            const data = await fetchWithAuth('/api/withdraw', { method: 'POST' });
            showAlert(data.message, 'danger');
        }

        async function resetClicks() {
            const data = await fetchWithAuth('/api/admin/reset-clicks', { method: 'POST' });
            showAlert('✅ Clicks reset!', 'success');
            init();
        }

        async function resetMultiplier() {
            const data = await fetchWithAuth('/api/admin/reset-multiplier', { method: 'POST' });
            showAlert('✅ Multiplier reset!', 'success');
            init();
        }

        async function setMultiplier() {
            const multiplier = parseInt(document.getElementById('multiplier-value').value);
            if (!multiplier) {
                showAlert('❌ Enter a multiplier!', 'danger');
                return;
            }
            const data = await fetchWithAuth('/api/admin/set-multiplier', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ multiplier })
            });
            showAlert(`✅ Multiplier set to ${multiplier}!`, 'success');
            init();
        }

        async function returnToTop() {
            const data = await fetchWithAuth('/api/admin/return-to-top', { method: 'POST' });
            showAlert('✅ Returned to top players!', 'success');
            init();
        }

        async function createPromoCode() {
            const activations = parseInt(document.getElementById('promo-activations').value);
            const coins = parseInt(document.getElementById('promo-coins').value);
            if (!activations || !coins) {
                showAlert('❌ Enter activations and coins!', 'danger');
                return;
            }
            const data = await fetchWithAuth('/api/admin/promo-codes/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ activations, coins })
            });
            showAlert(`🎟 Promo code created: ${data.code} (${coins} coins, ${activations} activations)`, 'success');
            backToMain();
        }

        async function listPromoCodes() {
            const data = await fetchWithAuth('/api/admin/promo-codes/list');
            document.getElementById('manage-promo-codes').innerHTML = `
                <h2>Manage Promo Codes</h2>
                <p>${data.promo_codes.length ? data.promo_codes.join('<br>') : 'No promo codes.'}</p>
                <button class="btn btn-primary btn-custom" onclick="showMenu('create-promo-code')">➕ Create Promo Code</button>
                <button class="btn btn-secondary btn-custom" onclick="backToMain()">🔙 Back</button>
            `;
            showMenu('manage-promo-codes');
        }

        init();
    </script>
</body>
</html>
"""

# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return HTML_CONTENT

@app.get("/api/main")
async def main_menu(user: UserData = Depends(get_current_user)):
    data = get_user_data(str(user.id), user.username or f"user_{user.id}")
    if not data:
        raise HTTPException(status_code=500, detail="Failed to fetch user data")
    
    clicks, multiplier, coins, in_top, last_mango, _, referral_count = data
    boost = 0.02 if referral_count < 10 else 0.05 if referral_count < 20 else 0.15
    
    return {
        "username": user.username or f"user_{user.id}",
        "clicks": clicks,
        "multiplier": multiplier,
        "coins": coins,
        "referral_boost": f"{int(boost * 100)}%",
        "referral_count": referral_count,
        "is_admin": user.id in ADMIN_IDS,
        "in_top": bool(in_top)
    }

@app.post("/api/click")
async def click(user: UserData = Depends(get_current_user)):
    data = get_user_data(str(user.id), user.username or f"user_{user.id}")
    clicks, multiplier, coins, in_top, last_mango, _, referral_count = data
    
    multiplier = float(multiplier)
    new_clicks = int(clicks) + int(multiplier)
    new_coins = int(coins) + 1
    
    cursor.execute("UPDATE table1 SET col3 = ?, col5 = ? WHERE col1 = ?",
                  (str(new_clicks), str(new_coins), str(user.id)))
    db.commit()
    
    return await main_menu(user)

@app.post("/api/shop/buy-click/{amount}")
async def buy_click(amount: int, user: UserData = Depends(get_current_user)):
    if amount not in [1, 2, 100]:
        raise HTTPException(status_code=400, detail="Invalid amount")
    
    costs = {1: 50, 2: 100, 100: 1000}
    cost = costs[amount]
    
    data = get_user_data(str(user.id), user.username or f"user_{user.id}")
    clicks, multiplier, coins, _, _, _, _ = data
    
    if int(coins) < cost:
        raise HTTPException(status_code=400, detail="Insufficient coins")
    
    new_multiplier = int(float(multiplier)) + amount
    new_coins = int(coins) - cost
    
    cursor.execute("UPDATE table1 SET col4 = ?, col5 = ? WHERE col1 = ?",
                  (str(new_multiplier), str(new_coins), str(user.id)))
    db.commit()
    
    return {"message": "Upgrade purchased"}

@app.get("/api/top-players")
async def top_players(user: UserData = Depends(get_current_user)):
    cursor.execute("SELECT col2, col3 FROM table1 WHERE col6 = 1 ORDER BY col3 DESC LIMIT 10")
    players = [{"username": row[0], "clicks": row[1]} for row in cursor.fetchall()]
    return {"players": players}

@app.post("/api/promo-codes/activate")
async def activate_promo_code(code: dict, user: UserData = Depends(get_current_user)):
    code = code.get("code").strip().upper()
    cursor.execute("SELECT col2, col3, col4, col5 FROM table2 WHERE col1 = ?", (code,))
    promo = cursor.fetchone()
    
    if not promo:
        raise HTTPException(status_code=400, detail="Invalid or used promo code")
    
    coins, activations, expiry, used_by = promo
    if time.time() > expiry:
        cursor.execute("DELETE FROM table2 WHERE col1 = ?", (code,))
        db.commit()
        raise HTTPException(status_code=400, detail="Promo code expired")
    
    if activations <= 0:
        raise HTTPException(status_code=400, detail="Promo code exhausted")
    
    if str(user.id) in used_by.split(','):
        raise HTTPException(status_code=400, detail="Promo code already used")
    
    cursor.execute("UPDATE table1 SET col5 = col5 + ? WHERE col1 = ?", (coins, str(user.id)))
    cursor.execute("UPDATE table2 SET col3 = col3 - 1, col5 = col5 || ? WHERE col1 = ?",
                  (f",{user.id}", code))
    db.commit()
    
    return {"coins": coins}

@app.post("/api/friends/find")
async def find_friend(data: dict, user: UserData = Depends(get_current_user)):
    friend_username = data.get("username").strip()
    cursor.execute("SELECT col1, col2 FROM table1 WHERE col2 = ?", (friend_username,))
    friend = cursor.fetchone()
    
    if not friend:
        raise HTTPException(status_code=400, detail="User not found")
    
    friend_id, friend_username = friend
    if str(friend_id) == str(user.id):
        raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")
    
    cursor.execute("""
    SELECT col3 FROM table3
    WHERE (col1 = ? AND col2 = ?) OR (col1 = ? AND col2 = ?)
    """, (str(user.id), str(friend_id), str(friend_id), str(user.id)))
    existing = cursor.fetchone()
    
    if existing:
        status = existing[0]
        raise HTTPException(status_code=400, detail=f"Friend request already {'accepted' if status == 'accepted' else 'sent'}")
    
    cursor.execute("INSERT OR IGNORE INTO table3 (col1, col2, col3) VALUES (?, ?, 'pending')",
                  (str(friend_id), str(user.id)))
    db.commit()
    
    return {"message": f"Friend request sent to @{friend_username}"}

@app.get("/api/friends/list")
async def list_friends(user: UserData = Depends(get_current_user)):
    cursor.execute("""
    SELECT u.col2 FROM table1 u
    JOIN table3 fr ON
        (fr.col1 = ? AND fr.col2 = u.col1 AND fr.col3 = 'accepted') OR
        (fr.col2 = ? AND fr.col1 = u.col1 AND fr.col3 = 'accepted')
    WHERE u.col1 != ?
    """, (str(user.id), str(user.id), str(user.id)))
    friends = [row[0] for row in cursor.fetchall()]
    return {"friends": friends}

@app.get("/api/referral")
async def referral_link(user: UserData = Depends(get_current_user)):
    link = f"https://t.me/KomaruXTomClicker_bot?start={user.id}"
    return {"link": link}

@app.post("/api/transfers/{transfer_type}")
async def transfer(transfer_type: str, data: Transfer, user: UserData = Depends(get_current_user)):
    if transfer_type not in ["coins", "clicks"]:
        raise HTTPException(status_code=400, detail="Invalid transfer type")
    
    cursor.execute("SELECT col1 FROM table1 WHERE col2 = ?", (data.username,))
    recipient = cursor.fetchone()
    
    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient not found")
    
    recipient_id = recipient[0]
    column = "col5" if transfer_type == "coins" else "col3"
    
    cursor.execute(f"SELECT {column} FROM table1 WHERE col1 = ?", (str(user.id),))
    balance = int(cursor.fetchone()[0])
    
    if balance < data.amount:
        raise HTTPException(status_code=400, detail=f"Insufficient {transfer_type}")
    
    cursor.execute(f"UPDATE table1 SET {column} = {column} - ? WHERE col1 = ?", (data.amount, str(user.id)))
    cursor.execute(f"UPDATE table1 SET {column} = {column} + ? WHERE col1 = ?", (data.amount, str(recipient_id)))
    db.commit()
    
    return {"message": f"Transferred {data.amount} {transfer_type} to {data.username}"}

@app.post("/api/mango")
async def mango(user: UserData = Depends(get_current_user)):
    data = get_user_data(str(user.id), user.username or f"user_{user.id}")
    clicks, _, coins, _, last_mango, _, _ = data
    
    today = datetime.now().date()
    if user.id not in ADMIN_IDS and last_mango and datetime.strptime(last_mango, '%Y-%m-%d').date() >= today:
        raise HTTPException(status_code=400, detail="You already used MANGO today")
    
    promo_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    promo_coins = 60
    extra_clicks = 10
    expiry = int(time.time()) + 86400
    
    cursor.execute("INSERT INTO table2 (col1, col2, col3, col4) VALUES (?, ?, 1, ?)",
                  (promo_code, promo_coins, expiry))
    new_clicks = int(clicks) + extra_clicks
    cursor.execute("UPDATE table1 SET col3 = ?, col7 = ? WHERE col1 = ?",
                  (str(new_clicks), today, str(user.id)))
    db.commit()
    
    return {"promo_code": promo_code, "coins": promo_coins, "clicks": extra_clicks}

@app.post("/api/withdraw")
async def withdraw(user: UserData = Depends(get_current_user)):
    data = get_user_data(str(user.id), user.username or f"user_{user.id}")
    clicks, _, _, _, _, _, _ = data
    
    if int(clicks) < 500:
        raise HTTPException(status_code=400, detail="Insufficient clicks for withdrawal")
    
    raise HTTPException(status_code=503, detail="Server connection failed")

@app.post("/api/admin/reset-clicks")
async def reset_clicks(user: UserData = Depends(get_current_user)):
    if user.id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    cursor.execute("UPDATE table1 SET col3 = '0' WHERE col1 = ?", (str(user.id),))
    db.commit()
    return {"message": "Clicks reset"}

@app.post("/api/admin/reset-multiplier")
async def reset_multiplier(user: UserData = Depends(get_current_user)):
    if user.id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    cursor.execute("UPDATE table1 SET col4 = '1' WHERE col1 = ?", (str(user.id),))
    db.commit()
    return {"message": "Multiplier reset"}

@app.post("/api/admin/set-multiplier")
async def set_multiplier(data: dict, user: UserData = Depends(get_current_user)):
    if user.id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    multiplier = data.get("multiplier")
    if not isinstance(multiplier, int) or multiplier <= 0:
        raise HTTPException(status_code=400, detail="Invalid multiplier")
    
    cursor.execute("UPDATE table1 SET col4 = ?, col6 = 0 WHERE col1 = ?", (str(multiplier), str(user.id)))
    db.commit()
    return {"message": f"Multiplier set to {multiplier}"}

@app.post("/api/admin/return-to-top")
async def return_to_top(user: UserData = Depends(get_current_user)):
    if user.id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    cursor.execute("UPDATE table1 SET col3 = '0', col4 = '1', col6 = 1 WHERE col1 = ?", (str(user.id),))
    db.commit()
    return {"message": "Returned to top players"}

@app.post("/api/admin/promo-codes/create")
async def create_promo_code(data: PromoCode, user: UserData = Depends(get_current_user)):
    if user.id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    expiry = int(time.time()) + 86400
    
    cursor.execute("INSERT INTO table2 (col1, col2, col3, col4) VALUES (?, ?, ?, ?)",
                  (code, data.coins, data.activations, expiry))
    db.commit()
    
    return {"code": code, "coins": data.coins, "activations": data.activations}

@app.get("/api/admin/promo-codes/list")
async def list_promo_codes(user: UserData = Depends(get_current_user)):
    if user.id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    cursor.execute("SELECT col1, col2, col3, col4, col5 FROM table2")
    promos = cursor.fetchall()
    now = int(time.time())
    promo_list = [
        f"🔢 Code: {code}\n💰 Reward: {coins} coins\n🔄 Activations: {activations}\n👥 Used: {len(used_by.split(',')) if used_by else 0}\n⏳ Status: {'Active' if now < expiry else 'Expired'}"
        for code, coins, activations, expiry, used_by in promos
    ]
    return {"promo_codes": promo_list}

@app.get("/mango.mp4")
async def serve_mango_video():
    if not os.path.exists("mango.mp4"):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse("mango.mp4")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
