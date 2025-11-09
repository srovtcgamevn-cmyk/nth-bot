# ============================================================
# BANG_CHU_SUPREME.PY
# Discord Bot + Web Admin (Flask) trong 1 file
# ============================================================
# YÊU CẦU:
#   pip install discord.py==2.4.0 flask
#
# BIẾN MÔI TRƯỜNG CẦN:
#   DISCORD_TOKEN
#   OWNER_DISCORD_ID
#
# CHỨC NĂNG:
#   1. EXP & NHIỆT HUYẾT (chat + voice chỉ tính mở mic)
#   2. Reset tuần: 00:00 T7 GMT+7, mở lại 14:00 T2
#   3. /topnhiethuyet, /hoso, /thongke @role
#   4. Chào mừng, tạm biệt, auto role
#   5. Từ khóa cấm + log + tự mute sau nhiều lần
#   6. Reaction role + Tuyên chiếu (nhiều emoji, gỡ role cũ)
#   7. Số báo danh
#   8. Buff mem theo link mời + auto đặt tên Việt
#   9. Chủ bot: datprefix, sheet_lienket (dự phòng), xuat/nhap dữ liệu
#  10. Web admin: dashboard, badwords, reaction/tuyên chiếu, buff, hướng dẫn
#
# LƯU Ý:
#   - Đây là bản trong 1 file nên mình viết theo kiểu "module trong file"
#   - Bạn có thể tách sau nếu muốn
# ============================================================

import os
import json
import random
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify, render_template_string

import discord
from discord.ext import commands, tasks
def only_owner():
    def predicate(ctx: commands.Context):
        return ctx.author.id == OWNER_DISCORD_ID
    return commands.check(predicate)



# ============================================================
# CONFIG CHUNG
# ============================================================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
EXP_FILE = os.path.join(DATA_DIR, "exp_week.json")
BADWORDS_FILE = os.path.join(DATA_DIR, "badwords.json")
REACTION_FILE = os.path.join(DATA_DIR, "reaction_roles.json")
TEMP_ROLE_FILE = os.path.join(DATA_DIR, "temp_roles.json")
SBD_FILE = os.path.join(DATA_DIR, "sobaodanh.json")
PREFIX_FILE = os.path.join(DATA_DIR, "nickprefix.json")
GLOBAL_MEMBERS_FILE = os.path.join(DATA_DIR, "global_members.json")
VIOLATIONS_FILE = os.path.join(DATA_DIR, "violations.json")
BUFF_FILE = os.path.join(DATA_DIR, "buff_links.json")
LOGS_FILE = os.path.join(DATA_DIR, "logs.json")
SHEET_FILE = os.path.join(DATA_DIR, "google_sheet.json")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OWNER_DISCORD_ID = int(os.getenv("821066331826421840", "0") or "0")

# ============================================================
# DISCORD INTENTS
# ============================================================
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
intents.reactions = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

# ============================================================
# HÀM JSON
# ============================================================

def load_json(path: str, default: Any):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# init files
for _file, _default in [
    (CONFIG_FILE, {"guilds": {}, "exp_locked": False}),
    (EXP_FILE, {"users": {}, "prev_week": {}}),
    (BADWORDS_FILE, {"words": [], "mode": "delete_warn"}),
    (REACTION_FILE, {"messages": {}}),
    (TEMP_ROLE_FILE, {"entries": []}),
    (SBD_FILE, {"members": {}}),
    (PREFIX_FILE, {"guilds": {}}),
    (GLOBAL_MEMBERS_FILE, {"users": []}),
    (VIOLATIONS_FILE, {"users": {}}),
    (BUFF_FILE, {"guilds": {}}),
    (LOGS_FILE, []),
    (SHEET_FILE, {"guilds": {}})
]:
    if not os.path.exists(_file):
        save_json(_file, _default)

# ============================================================
# BỘ TÊN VIỆT ĐỂ BUFF
# ============================================================
_base_names_with_accent = [
    "BảoAnh", "BảoAn", "BảoLong", "BảoNgọc", "BảoChâu", "BảoKhang", "BảoHân",
    "MinhAnh", "MinhKhang", "MinhQuân", "MinhThư", "MinhPhúc", "MinhTrang",
    "TuấnAnh", "TuấnKiệt", "TuấnPhong", "TuấnHưng",
    "KhảiĐăng", "HảiĐăng",
    "GiaHuy", "GiaBảo", "GiaKhang", "GiaPhúc",
    "AnhThư", "AnhThảo", "AnhĐào",
    "DiệuLinh", "DiễmMy", "DiệpAnh",
    "ThanhTâm", "ThanhVy", "ThanhTrúc",
    "ThảoVy", "ThảoNhi", "ThảoMy",
    "NgọcAnh", "NgọcHân", "NgọcTrâm", "NgọcBích", "NgọcVy",
    "HồngAnh", "HồngNgọc", "HồngNhung",
    "KimAnh", "KimNgân", "KimOanh",
    "PhươngAnh", "PhươngLinh", "PhươngTrang",
    "HoàiAn", "HoàiPhương",
    "QuỳnhAnh", "QuỳnhNhi",
    "ThùyLinh", "ThùyDương", "ThùyTrang",
    "YếnNhi", "MỹLinh", "MỹDung",
    "TrâmAnh", "KhánhVy", "KhánhLinh",
    "LanAnh", "TúVy", "BăngTâm",
    "HuyềnAnh", "HuyềnTrang", "HàMy",
    "BảoTrân", "BảoVy", "BảoYến",
    "NhậtAnh", "NhậtMinh",
    "HoàngLong", "HoàngAnh", "HoàngMinh", "HoàngPhúc",
]

_base_names_no_accent = [
    "baongoc", "baotran", "baovy", "baoanh", "baokhang",
    "minhphuc", "minhquan", "minhthu", "minhtrang",
    "tuananh", "tuankiet", "tuanphong", "tuanhung",
    "khaidang", "haidang",
    "giabao", "giakhang", "giaphuc",
    "anhthu", "dieulinh",
    "thanhvy", "thanhtruc", "thanhphong",
    "thaovy", "thaonhi",
    "ngocanh", "ngocvy", "ngoclinh",
    "honganh", "hongngoc",
    "phuonganh", "phuonglinh",
    "hoanganh", "hoanglong", "hoangphuc",
    "tramanh", "trammy",
    "khanhvy", "khanhlinh",
    "bangtam", "huyentrang",
    "nhatanh", "nhatminh",
    "quanghuy", "quangvinh",
    "linhchi", "linhdan",
    "myanh", "mydung",
    "vychanh", "vycute",
]

_year_tokens = ["2003","2004","2005","2006","2007","2008","2009","2010","03","05","07","09","69","99","123"]
SUFFIX_TOKENS = ["vip","pro","cute","dz","idol","tv","vn","ff","gamer","yt","no1","real","official","team","clan","baby"]
DECOR_TOKENS = ["♡","☆","•","✦","ツ"]
POPULAR_NUMBERS = ["03","05","07","08","09","2003","2004","2005","2006","69","99","123","888"]

BASE_NAMES_WITH_ACCENT = []
for n in _base_names_with_accent:
    BASE_NAMES_WITH_ACCENT.append(n)
    for y in _year_tokens:
        BASE_NAMES_WITH_ACCENT.append(f"{n}{y}")

BASE_NAMES_NO_ACCENT = []
for n in _base_names_no_accent:
    BASE_NAMES_NO_ACCENT.append(n)
    for y in _year_tokens:
        BASE_NAMES_NO_ACCENT.append(f"{n}{y}")

def generate_vn_nickname(guild_id: int) -> str:
    used = load_json(os.path.join(DATA_DIR, f"names_used_{guild_id}.json"), [])
    for _ in range(80):
        if random.random() < 0.7:
            base = random.choice(BASE_NAMES_WITH_ACCENT)
        else:
            base = random.choice(BASE_NAMES_NO_ACCENT)
        style = random.randint(0,4)
        suf = random.choice(SUFFIX_TOKENS)
        num = random.choice(POPULAR_NUMBERS)
        if style == 0:
            nick = base
        elif style == 1:
            nick = f"{base}{num}"
        elif style == 2:
            nick = f"{base}{suf}"
        elif style == 3:
            nick = f"{base}{suf}{num}"
        else:
            nick = base
        if random.random() < 0.25:
            nick = nick + random.choice(DECOR_TOKENS)
        nick = nick[:32]
        if nick not in used:
            used.insert(0, nick)
            used = used[:200]
            save_json(os.path.join(DATA_DIR, f"names_used_{guild_id}.json"), used)
            return nick
    return base[:32]


# ============================================================
# HÀM TIỆN ÍCH KHÁC
# ============================================================

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_DISCORD_ID

def now_utc():
    return datetime.now(timezone.utc)

def gmt7_now():
    return now_utc() + timedelta(hours=7)

def log_action(action: str, data: dict):
    logs = load_json(LOGS_FILE, [])
    logs.append({
        "time": now_utc().isoformat(),
        "action": action,
        "data": data
    })
    logs = logs[-500:]
    save_json(LOGS_FILE, logs)

# ============================================================
# DISCORD EVENTS
# ============================================================

@bot.event
async def on_ready():
    print(f"✅ BANG_CHU_SUPREME online: {bot.user} ({bot.user.id})")
    auto_reset_exp.start()
    temp_role_cleaner.start()

@bot.event
async def on_member_join(member: discord.Member):
    # lưu global
    global_data = load_json(GLOBAL_MEMBERS_FILE, {"users": []})
    if str(member.id) not in global_data["users"]:
        global_data["users"].append(str(member.id))
        save_json(GLOBAL_MEMBERS_FILE, global_data)

    # config
    cfg = load_json(CONFIG_FILE, {"guilds": {}})
    gconf = cfg["guilds"].get(str(member.guild.id), {})
    welcome_ch = gconf.get("welcome_channel_id")
    welcome_role = gconf.get("welcome_role_id")

    if welcome_role:
        r = member.guild.get_role(welcome_role)
        if r:
            try:
                await member.add_roles(r, reason="auto welcome role")
            except:
                pass

    if welcome_ch:
        ch = member.guild.get_channel(welcome_ch)
        if ch:
            await ch.send(
                f"🎉 Chào mừng {member.mention} đến **{member.guild.name}**!\n"
                f"Vào #chatchung giao lưu nha!"
            )

    # buff mem theo link? -> phần này xử lý trong on_member_join theo invite code
    # Nhưng discord.py không cho lấy invite trực tiếp trong event này khi không bật intents/invite,
    # ở đây mình bỏ qua bước detect code chi tiết để giữ 1 file.
    # Nếu bạn đã có code detect invite ở file buffmem cũ thì gộp lại đoạn đó vào đây.

@bot.event
async def on_member_remove(member: discord.Member):
    cfg = load_json(CONFIG_FILE, {"guilds": {}})
    gconf = cfg["guilds"].get(str(member.guild.id), {})
    leave_ch = gconf.get("leave_channel_id")
    if leave_ch:
        ch = member.guild.get_channel(leave_ch)
        if ch:
            await ch.send(f"👋 {member.display_name} đã rời bang.")
    log_action("member_leave", {"guild_id": member.guild.id, "user_id": member.id})

# VOICE TRACKING (chỉ tính mic mở)
# Ta sẽ lưu tạm trạng thái voice của từng user theo guild trong bộ nhớ
voice_state_map: Dict[int, Dict[int, dict]] = {}  # {guild_id: {user_id: {"start": datetime}}}

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    gid = member.guild.id
    if gid not in voice_state_map:
        voice_state_map[gid] = {}
    user_map = voice_state_map[gid]

    # nếu user vừa bật mic (trước mute, sau unmute) -> start
    # điều kiện tính: user phải ở trong voice channel, không muted, không deafened
    def is_open_mic(vs: discord.VoiceState):
        return vs.channel is not None and not vs.self_mute and not vs.mute and not vs.self_deaf and not vs.deaf

    before_open = is_open_mic(before)
    after_open = is_open_mic(after)

    if after_open and not before_open:
        # start counting
        user_map[member.id] = {"start": now_utc()}
    elif before_open and not after_open:
        # stop counting -> add exp
        info = user_map.pop(member.id, None)
        if info:
            delta = now_utc() - info["start"]
            seconds = delta.total_seconds()
            if seconds > 5:
                # cộng exp voice: 1 exp mỗi 30s
                bonus = int(seconds // 30)
                if bonus > 0:
                    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
                    users = exp_data["users"]
                    uid = str(member.id)
                    if uid not in users:
                        users[uid] = {
                            "exp_chat": 0,
                            "exp_voice": 0,
                            "last_msg": None,
                            "voice_seconds_week": 0
                        }
                    users[uid]["exp_voice"] += bonus
                    users[uid]["voice_seconds_week"] += int(seconds)
                    save_json(EXP_FILE, exp_data)

# ============================================================
# AUTO RESET EXP + AUTO CLEAN TEMP ROLE
# ============================================================

@tasks.loop(minutes=1)
async def auto_reset_exp():
    # giờ GMT+7
    now = gmt7_now()
    weekday = now.weekday()  # Mon=0
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False})

    # reset 00:00 T7
    if weekday == 5 and now.hour == 0 and now.minute == 0:
        exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
        # lưu tuần trước
        exp_data["prev_week"] = exp_data.get("users", {})
        exp_data["users"] = {}
        save_json(EXP_FILE, exp_data)
        cfg["exp_locked"] = True
        save_json(CONFIG_FILE, cfg)
        print("[EXP] reset tuần")

    # mở lại 14:00 T2
    if weekday == 0 and now.hour == 14 and now.minute == 0:
        cfg["exp_locked"] = False
        save_json(CONFIG_FILE, cfg)
        print("[EXP] mở lại exp tuần")

    # nếu nằm trong khoảng T7 -> T2 14h thì khóa
    in_lock = False
    if weekday in (5, 6):  # T7, CN
        in_lock = True
    if weekday == 0 and now.hour < 14:
        in_lock = True

    cfg["exp_locked"] = in_lock
    save_json(CONFIG_FILE, cfg)


@tasks.loop(minutes=5)
async def temp_role_cleaner():
    # gỡ role tạm thời hết hạn
    data = load_json(TEMP_ROLE_FILE, {"entries": []})
    changed = False
    now = now_utc()
    new_entries = []
    for e in data["entries"]:
        expire = datetime.fromisoformat(e["expire_at"])
        if now >= expire:
            # gỡ role
            guild = bot.get_guild(e["guild_id"])
            if guild:
                member = guild.get_member(e["user_id"])
                role = guild.get_role(e["role_id"])
                if member and role:
                    try:
                        await member.remove_roles(role, reason="role tạm thời hết hạn")
                    except:
                        pass
            changed = True
        else:
            new_entries.append(e)
    if changed:
        data["entries"] = new_entries
        save_json(TEMP_ROLE_FILE, data)

# ============================================================
# ON_MESSAGE: tính exp chat + từ khóa cấm
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    guild = message.guild
    if not guild:
        return

    # TỪ KHÓA CẤM
    bw = load_json(BADWORDS_FILE, {"words": [], "mode": "delete_warn"})
    lower = message.content.lower()
    violated = None
    for w in bw["words"]:
        if w and w.lower() in lower:
            violated = w
            break

    if violated:
        # xóa
        try:
            await message.delete()
        except:
            pass

        mode = bw.get("mode", "delete_warn")
        if mode in ("delete_warn", "delete_warn_dm"):
            try:
                await message.channel.send(
                    f"{message.author.mention} 🚫 từ này không được phép dùng.",
                    delete_after=6
                )
            except:
                pass
        if mode == "delete_warn_dm":
            try:
                await message.author.send(f"Bạn đã dùng từ cấm: `{violated}` trong {guild.name}")
            except:
                pass

        # log
        cfg = load_json(CONFIG_FILE, {"guilds": {}})
        gconf = cfg["guilds"].get(str(guild.id), {})
        log_ch_id = gconf.get("badword_log_channel_id")
        if log_ch_id:
            ch = guild.get_channel(log_ch_id)
            if ch:
                await ch.send(
                    f"⚠️ {message.author} dùng từ cấm `{violated}` tại <#{message.channel.id}>: ```{message.content}```"
                )
        # đếm vi phạm
        viol = load_json(VIOLATIONS_FILE, {"users": {}})
        u = viol["users"].get(str(message.author.id), {"count": 0})
        u["count"] += 1
        viol["users"][str(message.author.id)] = u
        save_json(VIOLATIONS_FILE, viol)

        # nếu quá 3 lần -> mute 10 phút (nếu bot đủ quyền)
        if u["count"] >= 3:
            try:
                until = datetime.now(timezone.utc) + timedelta(minutes=10)
                await message.author.edit(timeout=until, reason="vi phạm từ cấm nhiều lần")
                if log_ch_id:
                    await ch.send(f"⛔ {message.author.mention} đã bị mute 10 phút.")
            except:
                pass

        return  # không tính exp nữa

    # TÍNH EXP CHAT
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False})
    if not cfg.get("exp_locked", False):
        gconf = cfg["guilds"].get(str(guild.id), {})
        exp_chs = gconf.get("exp_channels", [])
        allow = (not exp_chs) or (message.channel.id in exp_chs)
        if allow:
            exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
            users = exp_data["users"]
            uid = str(message.author.id)
            if uid not in users:
                users[uid] = {
                    "exp_chat": 0,
                    "exp_voice": 0,
                    "last_msg": None,
                    "voice_seconds_week": 0
                }
            # cooldown 10s
            last = users[uid]["last_msg"]
            now_iso = now_utc().isoformat()
            add = True
            if last:
                last_dt = datetime.fromisoformat(last)
                if (now_utc() - last_dt).total_seconds() < 10:
                    add = False
            if add:
                users[uid]["exp_chat"] += random.randint(5, 15)
                users[uid]["last_msg"] = now_iso
                save_json(EXP_FILE, exp_data)

    await bot.process_commands(message)

# ============================================================
# COMMANDS: USER
# ============================================================

@bot.command(name="lenh")
async def cmd_lenh(ctx: commands.Context):
    msg = (
        "📜 LỆNH NGƯỜI CHƠI:\n"
        "/lenh - xem lệnh\n"
        "/hoso - xem hồ sơ tu luyện\n"
        "/topnhiethuyet - top toàn server\n"
        "/topnhiethuyet @role - top theo role\n"
        "/topnhiethuyet voice - top theo voice\n"
        "/thusobaodanh - xem số báo danh của bạn\n"
    )
    await ctx.reply(msg)

@bot.command(name="hoso")
async def cmd_hoso(ctx: commands.Context, member: Optional[discord.Member] = None):
    if member is None:
        member = ctx.author
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    u = exp_data["users"].get(str(member.id))
    if not u:
        await ctx.reply(f"📄 Hồ sơ tu luyện của {member.mention}:\n- EXP chat: 0\n- EXP voice: 0\n- Nhiệt huyết: 0/10")
        return
    total = u.get("exp_chat",0) + u.get("exp_voice",0)
    # đánh giá nhiệt huyết đơn giản
    score = min(10, total // 200)  # cứ 200 exp = 1 điểm
    await ctx.reply(
        f"📄 Hồ sơ tu luyện của {member.mention}:\n"
        f"- EXP chat: {u.get('exp_chat',0)}\n"
        f"- EXP voice: {u.get('exp_voice',0)}\n"
        f"- Tổng: {total}\n"
        f"- Nhiệt huyết: {score}/10\n"
        f"- Lần chat cuối: {u.get('last_msg','N/A')}"
    )

@bot.command(name="topnhiethuyet")
async def cmd_top(ctx: commands.Context, target: Optional[str] = None):
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    users = exp_data["users"]

    # nếu target là mention role
    role = None
    only_voice = False
    if target:
        if target.lower() == "voice":
            only_voice = True
        elif ctx.message.role_mentions:
            role = ctx.message.role_mentions[0]

    scores = []
    for uid, info in users.items():
        member = ctx.guild.get_member(int(uid))
        if not member:
            continue
        if role and role not in member.roles:
            continue
        chat_exp = info.get("exp_chat",0)
        voice_exp = info.get("exp_voice",0)
        if only_voice:
            total = voice_exp
        else:
            total = chat_exp + voice_exp
        scores.append((member, chat_exp, voice_exp, total))

    scores.sort(key=lambda x: x[3], reverse=True)

    lines = []
    title = "🔥 TOP NHIỆT HUYẾT"
    if role:
        title += f" — {role.name}"
    if only_voice:
        title += " (VOICE)"

    lines.append(title)
    sum_chat = 0
    sum_voice = 0
    for i, (member, chat_exp, voice_exp, total) in enumerate(scores[:20], start=1):
        lines.append(f"{i}. {member.display_name} — {total} (chat {chat_exp}, voice {voice_exp})")
        sum_chat += chat_exp
        sum_voice += voice_exp
    lines.append("")
    lines.append(f"Tổng cộng: {sum_chat + sum_voice} exp (chat {sum_chat} | voice {sum_voice})")

    await ctx.reply("\n".join(lines))

@bot.command(name="thusobaodanh")
async def cmd_thusbd(ctx: commands.Context, member: Optional[discord.Member] = None):
    if member is None:
        member = ctx.author
    sbd = load_json(SBD_FILE, {"members": {}})
    code = sbd["members"].get(str(member.id))
    if not code:
        await ctx.reply(f"{member.mention} chưa có số báo danh.")
    else:
        await ctx.reply(f"📄 Số báo danh của {member.mention}: **{code}**")

# ============================================================
# COMMANDS: ADMIN DISCORD
# ============================================================

@bot.command(name="lenhquantri")
@commands.has_permissions(manage_guild=True)
async def cmd_lenhquantri(ctx: commands.Context):
    msg = (
        "🛠 LỆNH QUẢN TRỊ:\n"
        "/kenhchat #kenh - kênh tính exp\n"
        "/setwelcome #kenh - kênh chào mừng\n"
        "/setleave #kenh - kênh tạm biệt\n"
        "/setrolewelcome @role - role cấp cho người mới\n"
        "/setlogcanhbao #kenh - kênh log từ cấm\n"
        "/tukhoa <từ> - thêm từ cấm\n"
        "/xoatukhoa <từ> - xoá từ cấm\n"
        "/reactionrole_tao <link/id> 😁 @role - tạo role phản ứng\n"
        "/reactionrole_xoa <link/id> - xoá\n"
        "/tuyenchieu_tao <link/id> 😀 @role - phong hàm\n"
        "/tuyenchieu_xoa <link/id>\n"
        "/capsobaodanh @user <số>\n"
        "/setvoice #kenh - (dự phòng) nếu muốn chỉ thống kê 1 số kênh voice\n"
    )
    await ctx.reply(msg)

@bot.command(name="kenhchat")
@commands.has_permissions(manage_guild=True)
async def cmd_kenhchat(ctx: commands.Context, channel: discord.TextChannel):
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False})
    gid = str(ctx.guild.id)
    if gid not in cfg["guilds"]:
        cfg["guilds"][gid] = {}
    lst = cfg["guilds"][gid].get("exp_channels", [])
    if channel.id not in lst:
        lst.append(channel.id)
    cfg["guilds"][gid]["exp_channels"] = lst
    save_json(CONFIG_FILE, cfg)
    await ctx.reply(f"✅ Đã đặt {channel.mention} là kênh tính exp")

@bot.command(name="setwelcome")
@commands.has_permissions(manage_guild=True)
async def cmd_setwelcome(ctx: commands.Context, channel: discord.TextChannel):
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False})
    gid = str(ctx.guild.id)
    if gid not in cfg["guilds"]:
        cfg["guilds"][gid] = {}
    cfg["guilds"][gid]["welcome_channel_id"] = channel.id
    save_json(CONFIG_FILE, cfg)
    await ctx.reply(f"✅ Đã đặt kênh chào mừng: {channel.mention}")

@bot.command(name="setleave")
@commands.has_permissions(manage_guild=True)
async def cmd_setleave(ctx: commands.Context, channel: discord.TextChannel):
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False})
    gid = str(ctx.guild.id)
    if gid not in cfg["guilds"]:
        cfg["guilds"][gid] = {}
    cfg["guilds"][gid]["leave_channel_id"] = channel.id
    save_json(CONFIG_FILE, cfg)
    await ctx.reply(f"✅ Đã đặt kênh tạm biệt: {channel.mention}")

@bot.command(name="setrolewelcome")
@commands.has_permissions(manage_guild=True)
async def cmd_setrolewelcome(ctx: commands.Context, role: discord.Role):
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False})
    gid = str(ctx.guild.id)
    if gid not in cfg["guilds"]:
        cfg["guilds"][gid] = {}
    cfg["guilds"][gid]["welcome_role_id"] = role.id
    save_json(CONFIG_FILE, cfg)
    await ctx.reply(f"✅ Người mới sẽ được cấp {role.mention}")

@bot.command(name="setlogcanhbao")
@commands.has_permissions(manage_guild=True)
async def cmd_setlogcanhbao(ctx: commands.Context, channel: discord.TextChannel):
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False})
    gid = str(ctx.guild.id)
    if gid not in cfg["guilds"]:
        cfg["guilds"][gid] = {}
    cfg["guilds"][gid]["badword_log_channel_id"] = channel.id
    save_json(CONFIG_FILE, cfg)
    await ctx.reply(f"✅ Kênh log cảnh báo: {channel.mention}")

@bot.command(name="tukhoa")
@commands.has_permissions(manage_guild=True)
async def cmd_tukhoa(ctx: commands.Context, *, word: str):
    bw = load_json(BADWORDS_FILE, {"words": [], "mode": "delete_warn"})
    if word.lower() not in [w.lower() for w in bw["words"]]:
        bw["words"].append(word)
    save_json(BADWORDS_FILE, bw)
    await ctx.reply(f"✅ Đã thêm từ cấm `{word}`")

@bot.command(name="xoatukhoa")
@commands.has_permissions(manage_guild=True)
async def cmd_xoatukhoa(ctx: commands.Context, *, word: str):
    bw = load_json(BADWORDS_FILE, {"words": [], "mode": "delete_warn"})
    bw["words"] = [w for w in bw["words"] if w.lower() != word.lower()]
    save_json(BADWORDS_FILE, bw)
    await ctx.reply(f"✅ Đã xoá từ cấm `{word}`")

@bot.command(name="capsobaodanh")
@commands.has_permissions(manage_guild=True)
async def cmd_capsobaodanh(ctx: commands.Context, member: discord.Member, sobd: str):
    sbd = load_json(SBD_FILE, {"members": {}})
    sbd["members"][str(member.id)] = sobd
    save_json(SBD_FILE, sbd)
    await ctx.reply(f"✅ Đã cấp số báo danh `{sobd}` cho {member.mention}")

# ============================================================
# REACTION ROLE & TUYÊN CHIẾU
# ============================================================

def parse_message_ref(text: str):
    text = text.strip()
    if text.isdigit():
        return (None, None, int(text))
    if "discord.com/channels/" in text:
        parts = text.split("/")
        gid = int(parts[-3])
        cid = int(parts[-2])
        mid = int(parts[-1])
        return (gid, cid, mid)
    return None

@bot.command(name="reactionrole_tao")
@commands.has_permissions(manage_guild=True)
async def cmd_reactionrole_tao(ctx: commands.Context, message_ref: str, emoji: str, role: discord.Role):
    parsed = parse_message_ref(message_ref)
    if not parsed:
        await ctx.reply("❌ Không đọc được link / ID tin nhắn.")
        return
    gid, cid, mid = parsed
    if gid is None:
        gid = ctx.guild.id

    data = load_json(REACTION_FILE, {"messages": {}})
    if str(gid) not in data["messages"]:
        data["messages"][str(gid)] = {}
    if str(mid) not in data["messages"][str(gid)]:
        data["messages"][str(gid)][str(mid)] = {
            "type": "reaction",
            "emojis": {}
        }
    data["messages"][str(gid)][str(mid)]["emojis"][emoji] = {
        "add_roles": [role.id],
        "remove_roles": [],
        "mode": "add"
    }
    save_json(REACTION_FILE, data)

    if cid:
        ch = ctx.guild.get_channel(cid)
        if ch:
            try:
                msg = await ch.fetch_message(mid)
                await msg.add_reaction(emoji)
            except:
                pass

    await ctx.reply(f"✅ Đã tạo reaction role cho tin `{mid}` với emoji {emoji} -> {role.mention}")

@bot.command(name="reactionrole_xoa")
@commands.has_permissions(manage_guild=True)
async def cmd_reactionrole_xoa(ctx: commands.Context, message_ref: str):
    parsed = parse_message_ref(message_ref)
    if not parsed:
        await ctx.reply("❌ Không đọc được link / ID tin nhắn.")
        return
    gid, cid, mid = parsed
    if gid is None:
        gid = ctx.guild.id
    data = load_json(REACTION_FILE, {"messages": {}})
    gdict = data["messages"].get(str(gid), {})
    if str(mid) in gdict:
        del gdict[str(mid)]
        data["messages"][str(gid)] = gdict
        save_json(REACTION_FILE, data)
        await ctx.reply("✅ Đã xoá reaction role.")
    else:
        await ctx.reply("❌ Tin này chưa cài reaction role.")

@bot.command(name="tuyenchieu_tao")
@commands.has_permissions(manage_guild=True)
async def cmd_tuyenchieu_tao(ctx: commands.Context, message_ref: str, emoji: str, role: discord.Role, mode: str = "them"):
    # mode = "them" hoặc "thay"
    parsed = parse_message_ref(message_ref)
    if not parsed:
        await ctx.reply("❌ Không đọc được link / ID tin nhắn.")
        return
    gid, cid, mid = parsed
    if gid is None:
        gid = ctx.guild.id

    data = load_json(REACTION_FILE, {"messages": {}})
    if str(gid) not in data["messages"]:
        data["messages"][str(gid)] = {}
    if str(mid) not in data["messages"][str(gid)]:
        data["messages"][str(gid)][str(mid)] = {
            "type": "tuyenchieu",
            "emojis": {}
        }

    # nếu mode=thay -> gỡ các role cũ thuộc nhóm phong hàm
    if mode == "thay":
        remove_roles = [role.id]  # thực tế sẽ cấu hình thêm trong web
    else:
        remove_roles = []

    data["messages"][str(gid)][str(mid)]["emojis"][emoji] = {
        "add_roles": [role.id],
        "remove_roles": remove_roles,
        "mode": mode
    }
    save_json(REACTION_FILE, data)

    if cid:
        ch = ctx.guild.get_channel(cid)
        if ch:
            try:
                msg = await ch.fetch_message(mid)
                await msg.add_reaction(emoji)
            except:
                pass

    await ctx.reply(f"✅ Đã tạo tuyên chiếu ({mode}) trên tin `{mid}` -> {role.mention}")

@bot.command(name="tuyenchieu_xoa")
@commands.has_permissions(manage_guild=True)
async def cmd_tuyenchieu_xoa(ctx: commands.Context, message_ref: str):
    parsed = parse_message_ref(message_ref)
    if not parsed:
        await ctx.reply("❌ Không đọc được link / ID tin nhắn.")
        return
    gid, cid, mid = parsed
    if gid is None:
        gid = ctx.guild.id
    data = load_json(REACTION_FILE, {"messages": {}})
    gdict = data["messages"].get(str(gid), {})
    if str(mid) in gdict:
        del gdict[str(mid)]
        data["messages"][str(gid)] = gdict
        save_json(REACTION_FILE, data)
        await ctx.reply("✅ Đã xoá tuyên chiếu.")
    else:
        await ctx.reply("❌ Tin này chưa cài tuyên chiếu.")

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    data = load_json(REACTION_FILE, {"messages": {}})
    gdict = data["messages"].get(str(payload.guild_id), {})
    mconf = gdict.get(str(payload.message_id))
    if not mconf:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member:
        return
    emoji = str(payload.emoji)
    econfs = mconf.get("emojis", {})
    ec = econfs.get(emoji)
    if not ec:
        return
    # add roles
    for rid in ec.get("add_roles", []):
        r = guild.get_role(rid)
        if r:
            try:
                await member.add_roles(r, reason="reaction/tuyenchieu")
            except:
                pass
    # remove roles
    for rid in ec.get("remove_roles", []):
        r = guild.get_role(rid)
        if r:
            try:
                await member.remove_roles(r, reason="reaction/tuyenchieu remove")
            except:
                pass

# ============================================================
# CHỦ BOT
# ============================================================

@bot.command(name="lenhchubot")
async def cmd_lenhchubot(ctx: commands.Context):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Bạn không phải chủ bot.")
        return
    msg = (
        "👑 LỆNH CHỦ BOT:\n"
        "/datprefix <chuỗi> - đặt tiền tố biệt danh bang\n"
        "/setlink <link> @role... - (dự phòng) buff mem ảo\n"
        "/xemlink - xem link buff\n"
        "/xoalink <link> - tắt link\n"
        "/batbuff / /tatbuff - bật tắt buff toàn bang\n"
        "/sheet_lienket <link> - lưu link sheet\n"
        "/xuatdulieu - xuất toàn bộ json\n"
    )
    await ctx.reply(msg)

@bot.command(name="datprefix")
async def cmd_datprefix(ctx: commands.Context, *, prefix: str):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Bạn không phải chủ bot.")
        return
    data = load_json(PREFIX_FILE, {"guilds": {}})
    data["guilds"][str(ctx.guild.id)] = prefix
    save_json(PREFIX_FILE, data)
    await ctx.reply(f"✅ Đã đặt prefix: `{prefix}`")

# --- buff mem ---
@bot.command(name="setlink")
@only_owner()
async def cmd_setlink(ctx: commands.Context, invite_url: str, *roles: discord.Role):
    """
    /setlink <invite_url> <@role1> <@role2> ...
    Gán 1 link buff với 1 danh sách role.
    """
    if not roles:
        await ctx.reply("❌ Bạn phải tag ít nhất 1 role.")
        return

    code = invite_url.strip().split("/")[-1]
    gid = str(ctx.guild.id)

    data = get_invite_map()
    if gid not in data["guilds"]:
        data["guilds"][gid] = {
            "buff_enabled": True,
            "links": {}
        }

    data["guilds"][gid]["links"][code] = {
        "role_ids": [r.id for r in roles],
        "active": True
    }

    set_invite_map(data)
    await refresh_guild_invites(ctx.guild)

    role_mentions = " ".join(r.mention for r in roles)
    await ctx.reply(
        f"✅ Đã gán link `{code}` với các role: {role_mentions}\n"
        f"Ai join bằng link này sẽ được buff mem ảo."
    )


@bot.command(name="xemlink")
@only_owner()
async def cmd_xemlink(ctx: commands.Context):
    """
    /xemlink
    Xem tất cả link buff + role tương ứng
    """
    gid = str(ctx.guild.id)
    data = get_invite_map()
    guild_conf = data["guilds"].get(gid)

    if not guild_conf or not guild_conf.get("links"):
        await ctx.reply("📭 Chưa có link buff nào trong bang này.")
        return

    buff_enabled = guild_conf.get("buff_enabled", True)
    status_txt = "BẬT" if buff_enabled else "TẮT"

    lines = [f"Chế độ buff toàn bang: {status_txt}"]
    for code, conf in guild_conf["links"].items():
        active = conf.get("active", True)
        role_ids = conf.get("role_ids", [])
        role_mentions = []
        for rid in role_ids:
            r = ctx.guild.get_role(rid)
            role_mentions.append(r.mention if r else str(rid))
        lines.append(
            f"- `{code}` -> Roles: {' '.join(role_mentions)} | Trạng thái: {'ON' if active else 'OFF'}"
        )

    await ctx.reply("\n".join(lines))


@bot.command(name="xoalink")
@only_owner()
async def cmd_xoalink(ctx: commands.Context, invite_url: str):
    """
    /xoalink <invite_url>
    Tắt 1 link buff cụ thể (active=false)
    """
    code = invite_url.strip().split("/")[-1]
    gid = str(ctx.guild.id)

    data = get_invite_map()
    guild_conf = data["guilds"].get(gid)

    if not guild_conf or code not in guild_conf.get("links", {}):
        await ctx.reply("❌ Link này chưa được cấu hình.")
        return

    guild_conf["links"][code]["active"] = False
    data["guilds"][gid] = guild_conf
    set_invite_map(data)

    await ctx.reply(f"📴 Đã tắt link `{code}`. Link này sẽ không buff nữa.")


@bot.command(name="batbuff")
@only_owner()
async def cmd_batbuff(ctx: commands.Context):
    """
    /batbuff
    Bật buff mem ảo toàn bang
    """
    gid = str(ctx.guild.id)
    data = get_invite_map()
    if gid not in data["guilds"]:
        data["guilds"][gid] = {
            "buff_enabled": True,
            "links": {}
        }
    else:
        data["guilds"][gid]["buff_enabled"] = True

    set_invite_map(data)
    await ctx.reply("✅ ĐÃ BẬT buff mem ảo cho bang này.")


@bot.command(name="tatbuff")
@only_owner()
async def cmd_tatbuff(ctx: commands.Context):
    """
    /tatbuff
    Tắt buff mem ảo toàn bang
    """
    gid = str(ctx.guild.id)
    data = get_invite_map()
    if gid not in data["guilds"]:
        data["guilds"][gid] = {
            "buff_enabled": False,
            "links": {}
        }
    else:
        data["guilds"][gid]["buff_enabled"] = False

    set_invite_map(data)
    await ctx.reply("⛔ ĐÃ TẮT buff mem ảo cho bang này.")



# ============================================================
# PHẦN WEB ADMIN (FLASK)
# ============================================================

app = Flask(__name__)

DASHBOARD_HTML = """
<!doctype html>
<title>Bảng điều khiển - BANG_CHU_SUPREME</title>
<h1>Bảng điều khiển</h1>
<p>Bot: {{bot_name}}</p>
<p>Số user đã ghi nhận: {{total_users}}</p>
<p>EXP đang {{'bị khóa' if exp_locked else 'mở'}}</p>
<h2>Top nhiệt huyết (10)</h2>
<pre>{{top_text}}</pre>
<h2>Menu</h2>
<ul>
<li><a href="/badwords">Từ khóa cấm</a></li>
<li><a href="/reactions">Reaction / Tuyên chiếu</a></li>
<li><a href="/buff">Buff mem</a></li>
<li><a href="/logs">Logs</a></li>
<li><a href="/helpbot">Hướng dẫn lệnh</a></li>
</ul>
"""

@app.route("/")
def web_dashboard():
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    users = exp_data["users"]
    items = []
    for uid, info in users.items():
        total = info.get("exp_chat",0) + info.get("exp_voice",0)
        items.append((uid, total))
    items.sort(key=lambda x: x[1], reverse=True)
    top_lines = []
    for i, (uid, total) in enumerate(items[:10], start=1):
        top_lines.append(f"{i}. {uid} — {total}")
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False})
    global_users = load_json(GLOBAL_MEMBERS_FILE, {"users": []})
    return render_template_string(
        DASHBOARD_HTML,
        bot_name=str(bot.user) if bot.user else "Chưa login",
        total_users=len(global_users["users"]),
        exp_locked=cfg.get("exp_locked", False),
        top_text="\n".join(top_lines)
    )

@app.route("/badwords", methods=["GET","POST"])
def web_badwords():
    if request.method == "POST":
        word = request.form.get("word","").strip()
        mode = request.form.get("mode","delete_warn")
        data = load_json(BADWORDS_FILE, {"words": [], "mode": "delete_warn"})
        if word and word.lower() not in [w.lower() for w in data["words"]]:
            data["words"].append(word)
        data["mode"] = mode
        save_json(BADWORDS_FILE, data)
    data = load_json(BADWORDS_FILE, {"words": [], "mode": "delete_warn"})
    html = """
    <h1>Từ khóa cấm</h1>
    <form method="post">
    Từ: <input name="word">
    Chế độ:
    <select name="mode">
      <option value="delete_only" {% if data.mode=='delete_only' %}selected{% endif %}>Xóa không báo</option>
      <option value="delete_warn" {% if data.mode=='delete_warn' %}selected{% endif %}>Xóa + cảnh báo</option>
      <option value="delete_warn_dm" {% if data.mode=='delete_warn_dm' %}selected{% endif %}>Xóa + DM</option>
    </select>
    <button>Lưu</button>
    </form>
    <h2>Danh sách</h2>
    <ul>
    {% for w in data.words %}
      <li>{{w}}</li>
    {% endfor %}
    </ul>
    <a href="/">← về dashboard</a>
    """
    return render_template_string(html, data=data)

@app.route("/reactions")
def web_reactions():
    data = load_json(REACTION_FILE, {"messages": {}})
    html = """
    <h1>Reaction / Tuyên chiếu</h1>
    <pre>{{data|tojson(indent=2)}}</pre>
    <a href="/">← về dashboard</a>
    """
    return render_template_string(html, data=data)

@app.route("/buff")
def web_buff():
    data = load_json(BUFF_FILE, {"guilds": {}})
    html = """
    <h1>Buff mem</h1>
    <pre>{{data|tojson(indent=2)}}</pre>
    <p>Chỉnh sửa bằng lệnh /setlink, /xemlink, /xoalink, /batbuff, /tatbuff trong Discord.</p>
    <a href="/">← về dashboard</a>
    """
    return render_template_string(html, data=data)



@app.route("/logs")
def web_logs():
    data = load_json(LOGS_FILE, [])
    html = """
    <h1>Logs</h1>
    <pre>{{data|tojson(indent=2)}}</pre>
    <a href="/">← về dashboard</a>
    """
    return render_template_string(html, data=data)

@app.route("/helpbot")
def web_helpbot():
    html = """
    <h1>Hướng dẫn lệnh</h1>
    <h2>Người chơi</h2>
    <pre>
/lenh
/hoso
/topnhiethuyet
/thusobaodanh
    </pre>
    <h2>Admin Discord</h2>
    <pre>
/lenhquantri
/kenhchat #kenh
/setwelcome #kenh
/setleave #kenh
/setrolewelcome @role
/setlogcanhbao #kenh
/tukhoa từ
/xoatukhoa từ
/reactionrole_tao ...
/tuyenchieu_tao ...
/capsobaodanh @user số
    </pre>
    <h2>Chủ bot</h2>
    <pre>
/lenhchubot
/datprefix ...
/setlink ...
/xemlink
/xoalink ...
/batbuff / /tatbuff
    </pre>
    <a href="/">← về dashboard</a>
    """
    return render_template_string(html)

# ============================================================
# RUN BOT + WEB
# ============================================================

def run_flask():
    # Railway thường dùng 0.0.0.0 và PORT env
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

def run_discord():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Thiếu DISCORD_TOKEN")
    elif OWNER_DISCORD_ID == 0:
        print("❌ Thiếu OWNER_DISCORD_ID")
    else:
        # chạy web trên thread riêng
        t = threading.Thread(target=run_flask, daemon=True)
        t.start()
        # chạy bot
        run_discord()
