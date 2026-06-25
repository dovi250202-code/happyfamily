# -*- coding: utf-8 -*-
"""
PHẦN MỀM ĐĂNG KÝ THỰC ĐƠN HÀNG NGÀY CHO GIA ĐÌNH — BẢN REAL-TIME (WebSocket)
----------------------------------------------------------------------------
CHẠY THỬ TRÊN MÁY (trước khi đưa lên mạng):
  1. pip install -r requirements.txt
  2. python app.py
  3. Mở http://127.0.0.1:5000

CHIA SẺ LINK CHO CẢ NHÀ DÙNG CHUNG (xem hướng dẫn đầy đủ trong HUONG_DAN_DEPLOY.md):
  - Đưa code này lên Render.com (miễn phí) để có 1 link dạng:
    https://thuc-don-nha-minh.onrender.com
  - Gửi link đó cho người nhà, ai mở cũng vào CÙNG MỘT trang, dữ liệu CHUNG.
  - Khi ai đó sửa món ăn, người khác đang mở trang sẽ thấy thay đổi
    NGAY LẬP TỨC (không cần tải lại trang) nhờ công nghệ WebSocket.

Dữ liệu lưu theo ngày thật (yyyy-mm-dd) vào file thuc_don_data.json,
nên có thể bấm "Tuần trước / Tuần sau" để xem lại các tuần đã qua.
"""

import json
import os
import threading
import webbrowser
from datetime import datetime

from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
app.config["SECRET_KEY"] = "thuc-don-gia-dinh-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "thuc_don_data.json")
LOCK = threading.Lock()

WEEKDAY_NAMES = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
MEALS = ["Sáng", "Trưa", "Tối"]
DAY_EMOJI = ["🌷", "🌼", "🌻", "🍀", "🌺", "🎉", "☀️"]
MEAL_EMOJI = {"Sáng": "🌅", "Trưa": "☀️", "Tối": "🌙"}
STICKERS = ["🍜", "🍲", "🍱", "🍕", "🍣", "🥗", "🍛", "🍙", "🍰", "🥘", "🍳", "🍤"]


# ---------------------------------------------------------------- dữ liệu ----

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- trang chính ----

@app.route("/")
def index():
    return render_template_string(
        HTML_TEMPLATE,
        weekday_names=WEEKDAY_NAMES,
        meals=MEALS,
        day_emoji=DAY_EMOJI,
        meal_emoji=MEAL_EMOJI,
        stickers=STICKERS,
    )


# ---------------------------------------------------------------- API REST (vẫn giữ để dùng được cả khi mất WebSocket) ----

@app.route("/api/menu", methods=["GET"])
def api_get_menu():
    with LOCK:
        data = load_data()
    return jsonify(data)


@app.route("/api/menu", methods=["POST"])
def api_save_menu():
    payload = request.get_json(force=True)
    result, status = _do_save(payload)
    return jsonify(result), status


@app.route("/api/menu", methods=["DELETE"])
def api_delete_menu():
    payload = request.get_json(force=True)
    result, status = _do_delete(payload)
    return jsonify(result), status


def _do_save(payload):
    date_str = (payload.get("date") or "").strip()
    meal = payload.get("meal")
    dish = (payload.get("dish") or "").strip()
    author = (payload.get("author") or "").strip() or "Chưa rõ"

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return {"error": "Ngày không hợp lệ"}, 400
    if meal not in MEALS:
        return {"error": "Buổi ăn không hợp lệ"}, 400
    if not dish:
        return {"error": "Tên món ăn không được để trống"}, 400

    with LOCK:
        data = load_data()
        data.setdefault(date_str, {})
        data[date_str][meal] = {
            "dish": dish,
            "author": author,
            "updated_at": datetime.now().strftime("%H:%M %d/%m/%Y"),
        }
        save_data(data)
        full_data = data

    # Báo NGAY cho mọi người đang mở trang (real-time qua WebSocket)
    socketio.emit("menu_updated", full_data)
    return {"ok": True, "data": data[date_str][meal]}, 200


def _do_delete(payload):
    date_str = payload.get("date")
    meal = payload.get("meal")

    with LOCK:
        data = load_data()
        if date_str in data and meal in data[date_str]:
            del data[date_str][meal]
            if not data[date_str]:
                del data[date_str]
            save_data(data)
        full_data = data

    socketio.emit("menu_updated", full_data)
    return {"ok": True}, 200


# ---------------------------------------------------------------- WebSocket: cho phép gửi qua socket trực tiếp ----

@socketio.on("connect")
def on_connect():
    socketio.emit("menu_updated", load_data())


@socketio.on("save_dish")
def on_save_dish(payload):
    result, _ = _do_save(payload)


@socketio.on("delete_dish")
def on_delete_dish(payload):
    result, _ = _do_delete(payload)


# ---------------------------------------------------------------- HTML/CSS/JS ----

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🍲 Thực đơn tuần của nhà mình</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
<style>
  :root{
    --bg1:#fff6ec; --bg2:#ffe9d6; --card:#ffffff; --accent:#ff8c66; --accent-dark:#e8633e;
    --accent2:#34a373; --text:#3a332c; --muted:#a59a8c; --border:#f3e4d4;
    --shadow: 0 10px 28px rgba(230,140,90,0.14);
  }
  *{box-sizing:border-box;}
  body{
    margin:0; font-family:'Segoe UI', 'Quicksand', Tahoma, Arial, sans-serif;
    background: radial-gradient(circle at 10% 0%, var(--bg2), var(--bg1) 60%);
    color:var(--text); padding:28px 16px 70px; min-height:100vh;
    background-attachment: fixed;
  }
  .floaters{ position:fixed; inset:0; pointer-events:none; overflow:hidden; z-index:0; }
  .floaters span{ position:absolute; font-size:34px; opacity:.18; animation:float 14s infinite ease-in-out; }
  @keyframes float{
    0%{ transform:translateY(0) rotate(0deg); }
    50%{ transform:translateY(-26px) rotate(12deg); }
    100%{ transform:translateY(0) rotate(0deg); }
  }
  .wrap{ position:relative; z-index:1; max-width:1320px; margin:0 auto; }
  h1{ text-align:center; font-size:30px; margin:0 0 2px; color:var(--accent-dark); text-shadow:1px 1px 0 #fff; }
  .sub{ text-align:center; color:var(--muted); margin-bottom:18px; font-size:14px; }

  .banner-error{
    display:none; max-width:640px; margin:0 auto 18px; background:#fde8e8; color:#9b2c2c;
    border:1.5px solid #f3b9b9; border-radius:14px; padding:14px 16px; font-size:13.5px; line-height:1.5;
  }
  .banner-error b{ display:block; margin-bottom:4px; font-size:14px; }

  .topbar{
    max-width:760px; margin:0 auto 22px; display:flex; gap:10px; align-items:center;
    flex-wrap:wrap; justify-content:center;
  }
  .who{
    flex:1 1 280px; display:flex; gap:10px; align-items:center;
    background:var(--card); padding:12px 16px; border-radius:16px; box-shadow:var(--shadow);
  }
  .who label{font-size:14px; color:var(--muted); white-space:nowrap; font-weight:600;}
  .who input{
    flex:1; border:1.5px solid var(--border); border-radius:10px; padding:8px 12px; font-size:14px;
    outline:none; transition:.2s;
  }
  .who input:focus{ border-color:var(--accent); }
  .who .avatar{ font-size:22px; }

  .week-nav{
    display:flex; gap:8px; align-items:center; background:var(--card);
    padding:10px 14px; border-radius:16px; box-shadow:var(--shadow);
  }
  .week-nav button{
    border:none; background:#fff0e4; color:var(--accent-dark); font-weight:700;
    border-radius:10px; padding:8px 12px; cursor:pointer; font-size:13px; transition:.15s;
  }
  .week-nav button:hover{ background:var(--accent); color:#fff; }
  .week-nav .week-label{ font-size:13.5px; font-weight:700; min-width:150px; text-align:center; }
  .week-nav .today-btn{ background:var(--accent2); color:#fff; }
  .week-nav .today-btn:hover{ opacity:.88; background:var(--accent2); }
  .past-tag{
    display:inline-block; margin-left:6px; font-size:11px; background:#eef2ff; color:#4c5fd5;
    border-radius:8px; padding:2px 8px; font-weight:700; vertical-align:middle;
  }

  .grid{
    display:grid; grid-template-columns:repeat(auto-fit, minmax(230px,1fr));
    gap:18px;
  }
  .day-card{
    background:var(--card); border-radius:20px; padding:16px 16px 6px; box-shadow:var(--shadow);
    border-top:5px solid var(--accent); transition: transform .18s ease, box-shadow .3s ease;
  }
  .day-card.is-past{ opacity:.82; }
  .day-card.is-today{ outline:2.5px solid var(--accent2); }
  .day-card.just-updated{ box-shadow: 0 0 0 4px rgba(52,163,115,0.35), var(--shadow); }
  .day-card:hover{ transform: translateY(-4px); }
  .day-head{ display:flex; align-items:baseline; gap:8px; margin-bottom:2px;}
  .day-title{ font-weight:800; font-size:18px; }
  .day-emoji{ font-size:20px; }
  .day-date{ color:var(--muted); font-size:12px; margin-bottom:14px; }
  .meal-block{margin-bottom:14px;}
  .meal-label{
    font-size:12px; font-weight:700; color:var(--accent2); text-transform:uppercase;
    letter-spacing:.05em; margin-bottom:6px; display:flex; align-items:center; gap:5px;
  }
  .dish-box{
    border:1.5px dashed var(--border); border-radius:12px; padding:10px 12px;
    min-height:50px; font-size:14px; position:relative; background:#fffaf4;
    cursor:pointer; transition:.15s; display:flex; align-items:center; gap:8px;
  }
  .dish-box:hover{ border-color:var(--accent); background:#fff3e8; }
  .dish-box.empty{ color:var(--muted); font-style:italic; border-style:dashed; }
  .dish-meta{ font-size:11px; color:var(--muted); margin-top:5px; line-height:1.5; }
  .dish-meta b{ color:#8a6a4f; }
  .dish-actions{ display:flex; gap:10px; margin-top:6px; }
  .dish-actions button{
    border:none; background:none; cursor:pointer; font-size:12px;
    color:var(--accent2); padding:3px 8px; border-radius:8px; font-weight:600;
  }
  .dish-actions button.del{color:#d1495b;}
  .dish-actions button:hover{background:#f3ece2;}
  .edit-row{display:flex; gap:6px; margin-top:6px;}
  .edit-row input{
    flex:1; border:1.5px solid var(--border); border-radius:10px; padding:8px 10px; font-size:13px; outline:none;
  }
  .edit-row input:focus{ border-color:var(--accent); }
  .edit-row button{
    border:none; background:linear-gradient(135deg, var(--accent), var(--accent-dark));
    color:white; border-radius:10px; padding:8px 14px; font-size:13px; cursor:pointer; font-weight:700;
  }
  .edit-row button:hover{ opacity:.92; }
  .status{ text-align:center; font-size:12px; color:var(--muted); margin-top:34px; }
  .dot{
    display:inline-block; width:8px; height:8px; border-radius:50%;
    background:var(--accent2); margin-right:5px; animation:pulse 1.6s infinite;
  }
  .dot.offline{ background:#d1495b; animation:none; }
  @keyframes pulse{0%{opacity:1;}50%{opacity:.3;}100%{opacity:1;}}
</style>
</head>
<body>

<div class="floaters">
  <span style="top:6%; left:4%; animation-delay:0s;">🍜</span>
  <span style="top:18%; left:80%; animation-delay:2s;">🍰</span>
  <span style="top:60%; left:10%; animation-delay:4s;">🥗</span>
  <span style="top:75%; left:88%; animation-delay:1s;">🍕</span>
  <span style="top:40%; left:50%; animation-delay:3s;">🍙</span>
  <span style="top:85%; left:40%; animation-delay:5s;">🍳</span>
</div>

<div class="wrap">
<h1>🍲 Thực đơn tuần của nhà mình</h1>
<div class="sub">Mỗi người nhập tên rồi viết món muốn ăn cho từng ngày — ai sửa, mọi người thấy ngay ✨</div>

<div class="banner-error" id="errorBanner">
  <b>⚠️ Mất kết nối tới server</b>
  Đang thử kết nối lại... Nếu kéo dài, kiểm tra lại server có đang chạy / link có đúng không.
</div>

<div class="topbar">
  <div class="who">
    <span class="avatar">🙋</span>
    <label for="authorInput">Tên bạn:</label>
    <input id="authorInput" type="text" placeholder="VD: Mẹ, Bố, An...">
  </div>
  <div class="week-nav">
    <button id="prevWeekBtn">◀ Tuần trước</button>
    <div class="week-label" id="weekLabel">--</div>
    <button id="nextWeekBtn">Tuần sau ▶</button>
    <button class="today-btn" id="todayBtn">Hôm nay</button>
  </div>
</div>

<div class="grid" id="grid"></div>

<div class="status"><span class="dot" id="statusDot"></span><span id="statusText">Đã kết nối — cập nhật theo thời gian thực</span></div>
</div>

<script>
const WEEKDAY_NAMES = {{ weekday_names | tojson }};
const MEALS = {{ meals | tojson }};
const DAY_EMOJI = {{ day_emoji | tojson }};
const MEAL_EMOJI = {{ meal_emoji | tojson }};
const DAY_COLORS = ["#ff8c66","#ffb84d","#ffd166","#34a373","#4fb3a9","#5b8def","#b388eb"];

function startOfDay(d){ const x = new Date(d); x.setHours(0,0,0,0); return x; }
function getMonday(d){
  const x = startOfDay(d);
  const day = x.getDay();
  const diff = (day === 0 ? -6 : 1 - day);
  x.setDate(x.getDate() + diff);
  return x;
}
function addDays(d, n){ const x = new Date(d); x.setDate(x.getDate()+n); return x; }
function isoDate(d){
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,"0");
  const day = String(d.getDate()).padStart(2,"0");
  return `${y}-${m}-${day}`;
}
function fmtShort(d){
  const m = String(d.getMonth()+1).padStart(2,"0");
  const day = String(d.getDate()).padStart(2,"0");
  return `${day}/${m}`;
}
function fmtRange(monday){
  const sunday = addDays(monday, 6);
  const m1 = String(monday.getMonth()+1).padStart(2,"0");
  const m2 = String(sunday.getMonth()+1).padStart(2,"0");
  return `${String(monday.getDate()).padStart(2,"0")}/${m1} – ${String(sunday.getDate()).padStart(2,"0")}/${m2}/${sunday.getFullYear()}`;
}

const TODAY = startOfDay(new Date());
const THIS_MONDAY = getMonday(TODAY);
let currentMonday = new Date(THIS_MONDAY);

const grid = document.getElementById("grid");
const authorInput = document.getElementById("authorInput");
const weekLabel = document.getElementById("weekLabel");
const errorBanner = document.getElementById("errorBanner");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

let currentAuthor = "";
authorInput.addEventListener("input", () => currentAuthor = authorInput.value);

let menuData = {};
let editingKey = null;
let weekDates = [];

function keyOf(dateStr, meal){ return dateStr + "|" + meal; }

function computeWeekDates(){
  weekDates = [];
  for (let i=0;i<7;i++) weekDates.push(addDays(currentMonday, i));
}

function updateWeekLabel(){
  let label = fmtRange(currentMonday);
  if (currentMonday.getTime() === THIS_MONDAY.getTime()){
    label += ` <span class="past-tag">Tuần này</span>`;
  } else if (currentMonday.getTime() < THIS_MONDAY.getTime()){
    label += ` <span class="past-tag">Đã qua</span>`;
  } else {
    label += ` <span class="past-tag">Sắp tới</span>`;
  }
  weekLabel.innerHTML = label;
}

function buildGrid(){
  computeWeekDates();
  updateWeekLabel();
  grid.innerHTML = "";

  weekDates.forEach((date, idx) => {
    const dateStr = isoDate(date);
    const isToday = date.getTime() === TODAY.getTime();
    const isPast = date.getTime() < TODAY.getTime();

    const card = document.createElement("div");
    card.className = "day-card" + (isPast ? " is-past" : "") + (isToday ? " is-today" : "");
    card.id = "card-" + dateStr;
    card.style.borderTopColor = DAY_COLORS[idx % DAY_COLORS.length];

    const head = document.createElement("div");
    head.className = "day-head";
    const title = document.createElement("div");
    title.className = "day-title";
    title.textContent = WEEKDAY_NAMES[idx];
    const emoji = document.createElement("div");
    emoji.className = "day-emoji";
    emoji.textContent = DAY_EMOJI[idx] || "🍽️";
    head.appendChild(title);
    head.appendChild(emoji);
    card.appendChild(head);

    const dateLine = document.createElement("div");
    dateLine.className = "day-date";
    dateLine.textContent = fmtShort(date) + (isToday ? "  •  hôm nay" : "");
    card.appendChild(dateLine);

    MEALS.forEach(meal => {
      const block = document.createElement("div");
      block.className = "meal-block";
      block.id = "block-" + keyOf(dateStr, meal).replace(/[\s|]/g,"_");

      const label = document.createElement("div");
      label.className = "meal-label";
      label.textContent = (MEAL_EMOJI[meal] || "") + " " + meal;
      block.appendChild(label);

      card.appendChild(block);
    });

    grid.appendChild(card);
  });

  renderAllBlocks();
}

function renderAllBlocks(){
  weekDates.forEach(date => {
    const dateStr = isoDate(date);
    MEALS.forEach(meal => renderBlock(dateStr, meal));
  });
}

function renderBlock(dateStr, meal){
  const id = "block-" + keyOf(dateStr, meal).replace(/[\s|]/g,"_");
  const block = document.getElementById(id);
  if(!block) return;

  const label = block.querySelector(".meal-label");
  block.innerHTML = "";
  block.appendChild(label);

  const entry = (menuData[dateStr] && menuData[dateStr][meal]) ? menuData[dateStr][meal] : null;
  const key = keyOf(dateStr, meal);

  if (editingKey === key){
    const row = document.createElement("div");
    row.className = "edit-row";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Tên món ăn...";
    input.value = entry ? entry.dish : "";
    const btn = document.createElement("button");
    btn.textContent = "Lưu";
    // dùng mousedown (bắn ra trước blur) để bấm Lưu không bị huỷ bởi việc mất focus
    btn.addEventListener("mousedown", (e) => { e.preventDefault(); saveDish(dateStr, meal, input.value); });
    input.addEventListener("keydown", e => {
      if (e.key === "Enter") saveDish(dateStr, meal, input.value);
      if (e.key === "Escape") { editingKey = null; renderBlock(dateStr, meal); }
    });
    // click ra ngoài ô đang sửa (không phải nút Lưu) -> tự huỷ, không lưu
    input.addEventListener("blur", () => {
      setTimeout(() => {
        if (editingKey === key) { editingKey = null; renderBlock(dateStr, meal); }
      }, 150);
    });
    row.appendChild(input);
    row.appendChild(btn);
    block.appendChild(row);
    setTimeout(() => input.focus(), 0);
    return;
  }

  const box = document.createElement("div");
  box.className = "dish-box" + (entry ? "" : " empty");
  if (entry){
    const textSpan = document.createElement("span");
    textSpan.textContent = entry.dish;
    box.appendChild(textSpan);
  } else {
    box.textContent = "➕ Chưa có món — bấm để thêm";
  }
  box.onclick = () => { editingKey = key; renderBlock(dateStr, meal); };
  block.appendChild(box);

  if (entry){
    const meta = document.createElement("div");
    meta.className = "dish-meta";
    meta.innerHTML = "Đăng ký / sửa bởi <b>" + entry.author + "</b><br>lúc " + entry.updated_at;
    block.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "dish-actions";

    const editBtn = document.createElement("button");
    editBtn.textContent = "✏️ Sửa";
    editBtn.onclick = (e) => { e.stopPropagation(); editingKey = key; renderBlock(dateStr, meal); };

    const delBtn = document.createElement("button");
    delBtn.className = "del";
    delBtn.textContent = "🗑️ Xóa";
    delBtn.onclick = (e) => { e.stopPropagation(); deleteDish(dateStr, meal); };

    actions.appendChild(editBtn);
    actions.appendChild(delBtn);
    block.appendChild(actions);
  }
}

function flashCard(dateStr){
  const card = document.getElementById("card-" + dateStr);
  if(!card) return;
  card.classList.add("just-updated");
  setTimeout(() => card.classList.remove("just-updated"), 900);
}

// ---------- WebSocket: nhận cập nhật real-time ----------
const socket = io();

socket.on("connect", () => {
  errorBanner.style.display = "none";
  statusDot.classList.remove("offline");
  statusText.textContent = "Đã kết nối — cập nhật theo thời gian thực";
});

socket.on("disconnect", () => {
  errorBanner.style.display = "block";
  statusDot.classList.add("offline");
  statusText.textContent = "Mất kết nối...";
});

socket.on("menu_updated", (data) => {
  const prevKeys = JSON.stringify(menuData);
  menuData = data;
  renderAllBlocks();
  // hiệu ứng nhấp nháy nhẹ cho các ngày trong tuần đang xem nếu có gì mới
  weekDates.forEach(d => {
    const ds = isoDate(d);
    if (data[ds]) flashCard(ds);
  });
});

function saveDish(dateStr, meal, dish){
  dish = (dish || "").trim();
  if(!dish){ alert("Vui lòng nhập tên món ăn."); return; }
  socket.emit("save_dish", { date: dateStr, meal, dish, author: currentAuthor || authorInput.value });
  editingKey = null;
  renderBlock(dateStr, meal); // hiển thị tạm trong khi chờ server xác nhận
}

function deleteDish(dateStr, meal){
  if(!confirm("Xóa món này?")) return;
  socket.emit("delete_dish", { date: dateStr, meal });
}

document.getElementById("prevWeekBtn").onclick = () => { currentMonday = addDays(currentMonday, -7); editingKey=null; buildGrid(); };
document.getElementById("nextWeekBtn").onclick = () => { currentMonday = addDays(currentMonday, 7); editingKey=null; buildGrid(); };
document.getElementById("todayBtn").onclick = () => { currentMonday = new Date(THIS_MONDAY); editingKey=null; buildGrid(); };

buildGrid();
</script>

</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    is_local = port == 5000 and "RENDER" not in os.environ

    print("=" * 64)
    print(" PHẦN MỀM THỰC ĐƠN GIA ĐÌNH (REAL-TIME) ĐANG CHẠY")
    print(f" Mở trình duyệt tại: http://127.0.0.1:{port}")
    print(" Để CHIA SẺ LINK cho cả nhà dùng chung qua Internet,")
    print(" xem hướng dẫn trong file HUONG_DAN_DEPLOY.md")
    print(" Nhấn Ctrl+C để dừng.")
    print("=" * 64)

    if is_local:
        try:
            threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
        except Exception:
            pass

    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True, use_reloader=False)
