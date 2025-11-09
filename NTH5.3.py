# -*- coding: utf-8 -*-
"""
Nghich Thuy Han New - BANG_CHU_SUPREME
1 file duy nhất
"""

import os, json, random, math, asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

# =============== CẤU HÌNH CƠ BẢN ===============
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OWNER_DISCORD_ID = 821066331826421840  # ID của bạn

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

EXP_FILE          = os.path.join(DATA_DIR, "exp_week.json")
BUFF_FILE         = os.path.join(DATA_DIR, "buff_links.json")
NAMES_FILE        = os.path.join(DATA_DIR, "used_names.json")
INVITES_FILE      = os.path.join(DATA_DIR, "invites_cache.json")
CONFIG_FILE       = os.path.join(DATA_DIR, "config.json")
TEAMCONF_FILE     = os.path.join(DATA_DIR, "team_config.json")
ATTEND_FILE       = os.path.join(DATA_DIR, "attendance.json")
TEAMSCORE_FILE    = os.path.join(DATA_DIR, "team_scores.json")
LEVEL_REWARD_FILE = os.path.join(DATA_DIR, "level_rewards.json")

default_files = [
    (EXP_FILE,          {"users": {}, "prev_week": {}}),
    (BUFF_FILE,         {"guilds": {}}),
    (NAMES_FILE,        {}),
    (INVITES_FILE,      {}),
    (CONFIG_FILE,       {"guilds": {}, "exp_locked": False, "last_reset": ""}),
    (TEAMCONF_FILE,     {"guilds": {}}),
    (ATTEND_FILE,       {"guilds": {}}),
    (TEAMSCORE_FILE,    {"guilds": {}}),
    (LEVEL_REWARD_FILE, {"guilds": {}}),
]
for p, d in default_files:
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

# =============== HÀM TIỆN ÍCH ===============
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now_utc():
    return datetime.now(timezone.utc)

def gmt7_now():
    return now_utc() + timedelta(hours=7)

def today_str_gmt7():
    return gmt7_now().date().isoformat()

def is_owner(uid: int) -> bool:
    return uid == OWNER_DISCORD_ID

def is_admin_ctx(ctx) -> bool:
    return (
        ctx.author.guild_permissions.manage_guild
        or ctx.author.guild_permissions.administrator
        or is_owner(ctx.author.id)
    )

# =============== KHÓA EXP THEO LỊCH ===============
# T7, CN khóa
# Thứ 2 trước 14h khóa
def is_weekend_lock():
    n = gmt7_now()
    wd = n.weekday()        # Mon=0
    if wd in (5, 6):        # T7, CN
        return True
    if wd == 0 and n.hour < 14:
        return True
    return False

# =============== BỘ TÊN ẢO ===============
BASE_NAMES_WITH_ACCENT = [
    "AnAn",
    "AnAnh",
    "AnBảo",
    "AnChi",
    "AnDiệp",
    "AnDương",
    "AnGiang",
    "AnHà",
    "AnHân",
    "AnHuyền",
    "AnKim",
    "AnKhánh",
    "AnKhuê",
    "AnLan",
    "AnLinh",
    "AnLoan",
    "AnLy",
    "AnMai",
    "AnMinh",
    "AnMy",
    "AnNgân",
    "AnNgọc",
    "AnNhư",
    "AnNhi",
    "AnOanh",
    "AnPhương",
    "AnQuỳnh",
    "AnThảo",
    "AnThư",
    "AnTrang",
    "AnTrâm",
    "AnTuyết",
    "AnUyên",
    "AnVi",
    "AnVy",
    "AnYến",
    "AnÁnh",
    "AnĐan",
    "AnĐào",
    "AnĐình",
    "BảoAn",
    "BảoAnh",
    "BảoChâu",
    "BảoChi",
    "BảoDương",
    "BảoGiang",
    "BảoHà",
    "BảoHân",
    "BảoHuyền",
    "BảoKhánh",
    "BảoKhang",
    "BảoLan",
    "BảoLinh",
    "BảoLoan",
    "BảoLy",
    "BảoMinh",
    "BảoMy",
    "BảoNgân",
    "BảoNgọc",
    "BảoNhi",
    "BảoNhư",
    "BảoOanh",
    "BảoPhúc",
    "BảoPhương",
    "BảoQuỳnh",
    "BảoThảo",
    "BảoThư",
    "BảoTrang",
    "BảoTrâm",
    "BảoTuyền",
    "BảoUyên",
    "BảoVi",
    "BảoVy",
    "BảoYến",
    "BảoĐan",
    "BảoĐào",
    "BảoĐăng",
    "BảoĐình",
    "DiệuAnh",
    "DiệuHà",
    "DiệuHân",
    "DiệuHuyền",
    "DiệuKhánh",
    "DiệuLinh",
    "DiệuLoan",
    "DiệuLy",
    "DiệuMinh",
    "DiệuMy",
    "DiệuNgân",
    "DiệuNgọc",
    "DiệuNhư",
    "DiệuNhi",
    "DiệuOanh",
    "DiệuPhương",
    "DiệuQuỳnh",
    "DiệuThảo",
    "DiệuThư",
    "DiệuTrang",
    "DiệuTrâm",
    "DiệuTú",
    "DiệuUyên",
    "DiệuVi",
    "DiệuVy",
    "DiệuYến",
    "DiệuÁnh",
    "DiệuĐan",
    "DiệuĐào",
    "DiệuĐình",
    "GiaAnh",
    "GiaAn",
    "GiaBảo",
    "GiaHân",
    "GiaHuyền",
    "GiaKhánh",
    "GiaKhang",
    "GiaLan",
    "GiaLinh",
    "GiaLoan",
    "GiaLy",
    "GiaMinh",
    "GiaMy",
    "GiaNgân",
    "GiaNgọc",
    "GiaNhư",
    "GiaNhi",
    "GiaOanh",
    "GiaPhương",
    "GiaQuỳnh",
    "GiaThảo",
    "GiaThư",
    "GiaTrang",
    "GiaTrâm",
    "GiaUyên",
    "GiaVi",
    "GiaVy",
    "GiaYến",
    "GiaĐan",
    "GiaĐào",
    "GiaĐình",
    "HoàngAnh",
    "HoàngAn",
    "HoàngBảo",
    "HoàngChâu",
    "HoàngDiệp",
    "HoàngDương",
    "HoàngGia",
    "HoàngHà",
    "HoàngHân",
    "HoàngHuyền",
    "HoàngKhánh",
    "HoàngKhang",
    "HoàngLan",
    "HoàngLinh",
    "HoàngLoan",
    "HoàngLy",
    "HoàngMinh",
    "HoàngMy",
    "HoàngNgân",
    "HoàngNgọc",
    "HoàngNhi",
    "HoàngNhư",
    "HoàngOanh",
    "HoàngPhương",
    "HoàngQuỳnh",
    "HoàngThảo",
    "HoàngThư",
    "HoàngTrang",
    "HoàngTrâm",
    "HoàngUyên",
    "HoàngVi",
    "HoàngVy",
    "HoàngYến",
    "HoàngÁnh",
    "HoàngĐan",
    "HoàngĐào",
    "HoàngĐăng",
    "KhánhAn",
    "KhánhAnh",
    "KhánhBảo",
    "KhánhChi",
    "KhánhDiệp",
    "KhánhDương",
    "KhánhHà",
    "KhánhHân",
    "KhánhHuyền",
    "KhánhKhang",
    "KhánhLan",
    "KhánhLinh",
    "KhánhLoan",
    "KhánhLy",
    "KhánhMinh",
    "KhánhMy",
    "KhánhNgân",
    "KhánhNgọc",
    "KhánhNhi",
    "KhánhNhư",
    "KhánhOanh",
    "KhánhPhương",
    "KhánhQuỳnh",
    "KhánhThảo",
    "KhánhThư",
    "KhánhTrang",
    "KhánhTrâm",
    "KhánhUyên",
    "KhánhVi",
    "KhánhVy",
    "KhánhYến",
    "KhánhĐan",
    "KhánhĐào",
    "KhánhĐình",
    "LanAnh",
    "LanAn",
    "LanBảo",
    "LanChi",
    "LanDiệp",
    "LanDương",
    "LanHà",
    "LanHân",
    "LanHuyền",
    "LanKhánh",
    "LanKhuê",
    "LanLinh",
    "LanLoan",
    "LanLy",
    "LanMinh",
    "LanMy",
    "LanNgân",
    "LanNgọc",
    "LanNhi",
    "LanNhư",
    "LanOanh",
    "LanPhương",
    "LanQuỳnh",
    "LanThảo",
    "LanThư",
    "LanTrang",
    "LanTrâm",
    "LanTuyền",
    "LanUyên",
    "LanVi",
    "LanVy",
    "LanYến",
    "LanÁnh",
    "LanĐan",
    "LanĐào",
    "LanĐình",
    "NgọcAnh",
    "NgọcAn",
    "NgọcBảo",
    "NgọcChi",
    "NgọcDương",
    "NgọcHà",
    "NgọcHân",
    "NgọcHuyền",
    "NgọcKhánh",
    "NgọcKhuê",
    "NgọcLan",
    "NgọcLinh",
    "NgọcLoan",
    "NgọcLy",
    "NgọcMinh",
    "NgọcMy",
    "NgọcNgân",
    "NgọcNhi",
    "NgọcNhư",
    "NgọcOanh",
    "NgọcPhương",
    "NgọcQuỳnh",
    "NgọcThảo",
    "NgọcThư",
    "NgọcTrang",
    "NgọcTrâm",
    "NgọcTuyền",
    "NgọcUyên",
    "NgọcVi",
    "NgọcVy",
    "NgọcYến",
    "NgọcÁnh",
    "NgọcĐan",
    "NgọcĐào",
    "NgọcĐỉnh",
    "PhươngAnh",
    "PhươngAn",
    "PhươngBảo",
    "PhươngChi",
    "PhươngDuyên",
    "PhươngHà",
    "PhươngHân",
    "PhươngHuyền",
    "PhươngKhánh",
    "PhươngKhuê",
    "PhươngLan",
    "PhươngLinh",
    "PhươngLoan",
    "PhươngLy",
    "PhươngMinh",
    "PhươngMy",
    "PhươngNgân",
    "PhươngNgọc",
    "PhươngNhi",
    "PhươngNhư",
    "PhươngOanh",
    "PhươngQuỳnh",
    "PhươngThảo",
    "PhươngThư",
    "PhươngTrang",
    "PhươngTrâm",
    "PhươngTuyết",
    "PhươngUyên",
    "PhươngVi",
    "PhươngVy",
    "PhươngYến",
    "PhươngÁnh",
    "PhươngĐan",
    "PhươngĐình",
    "QuỳnhAnh",
    "QuỳnhAn",
    "QuỳnhBảo",
    "QuỳnhChi",
    "QuỳnhDương",
    "QuỳnhHà",
    "QuỳnhHân",
    "QuỳnhHuyền",
    "QuỳnhKhánh",
    "QuỳnhLan",
    "QuỳnhLinh",
    "QuỳnhLoan",
    "QuỳnhLy",
    "QuỳnhMinh",
    "QuỳnhMy",
    "QuỳnhNgân",
    "QuỳnhNgọc",
    "QuỳnhNhi",
    "QuỳnhNhư",
    "QuỳnhOanh",
    "QuỳnhPhương",
    "QuỳnhThảo",
    "QuỳnhThư",
    "QuỳnhTrang",
    "QuỳnhTrâm",
    "QuỳnhTuyền",
    "QuỳnhUyên",
    "QuỳnhVi",
    "QuỳnhVy",
    "QuỳnhYến",
    "QuỳnhÁnh",
    "QuỳnhĐan",
    "QuỳnhĐào",
    "QuỳnhĐình"
]

BASE_NAMES_NO_ACCENT = [
    "baoanh",
    "baoan",
    "baobao",
    "baochau",
    "baochi",
    "baoduyen",
    "baohan",
    "baohuyen",
    "baokhanh",
    "baokhang",
    "baokhue",
    "baolan",
    "baolinh",
    "baoloan",
    "baoly",
    "baominh",
    "baomy",
    "baongan",
    "baongoc",
    "baonhi",
    "baonhu",
    "baooanh",
    "baophuong",
    "baoquynh",
    "baothao",
    "baothu",
    "baotrang",
    "baotram",
    "baotuyen",
    "baouyen",
    "baovi",
    "baovy",
    "baoyen",
    "baodang",
    "baodao",
    "baodinh",
    "minhanh",
    "minhan",
    "minhbao",
    "minhchau",
    "minhchi",
    "minhduong",
    "minhha",
    "minhhan",
    "minhhuyen",
    "minhkhanh",
    "minhkhu e".replace(" ",""),
    "minhlan",
    "minhlinh",
    "minhloan",
    "minhly",
    "minhminh",
    "minhmy",
    "minhngan",
    "minhngoc",
    "minhnhi",
    "minhnhu",
    "minhoanh",
    "minhphuong",
    "minhquynh",
    "minhthao",
    "minhthu",
    "minhtrang",
    "minhtram",
    "minhtuyen",
    "minhuyen",
    "minhvi",
    "minhvy",
    "minhyen",
    "minhdang",
    "minhdao",
    "minhdinh",
    "tuananh",
    "tuanan",
    "tuanbao",
    "tuanchau",
    "tuanchi",
    "tuanduyen",
    "tuanha",
    "tuanhan",
    "tuanhuyen",
    "tuankhanh",
    "tuankhang",
    "tuanlan",
    "tuanlinh",
    "tuanloan",
    "tuanly",
    "tuanminh",
    "tuanmy",
    "tuangan",
    "tuangoc",
    "tuannhi",
    "tuannhu",
    "tuanoanh",
    "tuanphuong",
    "tuanquynh",
    "tuanthao",
    "tuanthu",
    "tuantrang",
    "tuantram",
    "tuantuyen",
    "tuanuyen",
    "tuanvi",
    "tuanvy",
    "tuanyen",
    "tuandao",
    "tuandinh",
    "huyanh",
    "huyan",
    "huybao",
    "huychau",
    "huychi",
    "huyduong",
    "huyha",
    "huyhan",
    "huyhuyen",
    "huykhanh",
    "huykhang",
    "huylan",
    "huylinh",
    "huyloan",
    "huyly",
    "huyminh",
    "huymy",
    "huyngan",
    "huyngoc",
    "huynhi",
    "huynhu",
    "huynh oanh".replace(" ",""),
    "huyphuong",
    "huyquynh",
    "huythao",
    "huythu",
    "huytrang",
    "huytram",
    "huytuyen",
    "huyuyen",
    "huyvi",
    "huyvy",
    "huyen",
    "huydao",
    "huydinh",
    "khanhanh",
    "khanhan",
    "khanhbao",
    "khanhchau",
    "khanhchi",
    "khanhduong",
    "khanhha",
    "khanhhan",
    "khanhhuyen",
    "khanhkhang",
    "khanhkhu e".replace(" ",""),
    "khanhlan",
    "khanhlinh",
    "khanhloan",
    "khanhly",
    "khanhminh",
    "khanhmy",
    "khanhngan",
    "khanhngoc",
    "khanhnhi",
    "khanhnhu",
    "khanhoanh",
    "khanhphuong",
    "khanhquynh",
    "khanhthao",
    "khanhthu",
    "khanhtrang",
    "khanhtram",
    "khanhtuyen",
    "khanhuyen",
    "khanhvi",
    "khanhvy",
    "khanhyen",
    "khanhdao",
    "khanhdinh",
    "ngocanh",
    "ngocan",
    "ngocbao",
    "ngocchau",
    "ngocchi",
    "ngocduong",
    "ngocha",
    "ngochan",
    "ngochuyen",
    "ngockhanh",
    "ngockhang",
    "ngoclan",
    "ngoclinh",
    "ngocloan",
    "ngocly",
    "ngocminh",
    "ngocmy",
    "ngocngan",
    "ngocnhi",
    "ngocnhu",
    "ngocoanh",
    "ngocphuong",
    "ngocquynh",
    "ngocthao",
    "ngocthu",
    "ngoctrang",
    "ngoctram",
    "ngoctuyen",
    "ngocuyen",
    "ngocvi",
    "ngocvy",
    "ngocyen",
    "ngocdao",
    "ngocdinh",
    "phuonganh",
    "phuongan",
    "phuongbao",
    "phuongchau",
    "phuongchi",
    "phuongduyen",
    "phuongha",
    "phuonghan",
    "phuonghuyen",
    "phuongkhanh",
    "phuongkhang",
    "phuonglan",
    "phuonglinh",
    "phuongloan",
    "phuongly",
    "phuongminh",
    "phuongmy",
    "phuongngan",
    "phuongngoc",
    "phuongnhi",
    "phuongnhu",
    "phuongoanh",
    "phuongquynh",
    "phuongthao",
    "phuongthu",
    "phuongtrang",
    "phuongtram",
    "phuongtuyen",
    "phuonguyen",
    "phuongvi",
    "phuongvy",
    "phuongyen",
    "phuongdao",
    "phuongdinh"
]

SUFFIX_TOKENS = [
    "vip", "pro", "dz", "cute", "tv", "vn", "x", "z", "no1",
    "real", "off", "idol", "baby", "chanh", "love"
]

DECOR_TOKENS = [
    "♡", "☆", "ツ", "✦"
]

POPULAR_NUMBERS = [
    "69", "99", "888", "123", "2007", "2008", "2005", "2009",
    "03", "07", "09", "2003", "2004", "97", "98"
]

def get_used_names():
    return load_json(NAMES_FILE, {})

def set_used_names(data):
    save_json(NAMES_FILE, data)

def generate_nickname(gid: int) -> str:
    used = get_used_names()
    recent = used.get(str(gid), [])
    for _ in range(60):
        base = random.choice(BASE_NAMES_WITH_ACCENT if random.random()<0.6 else BASE_NAMES_NO_ACCENT)
        name = base
        style = random.randint(0, 5)
        if style == 0:
            name = f"{base}{random.choice(POPULAR_NUMBERS)}"
        elif style == 1:
            name = f"{base}{random.choice(SUFFIX_TOKENS)}"
        elif style == 2:
            name = f"{base}{random.choice(SUFFIX_TOKENS)}{random.choice(POPULAR_NUMBERS)}"
        if random.random() < 0.25:
            name = f"{name}{random.choice(DECOR_TOKENS)}"
        name = name[:32]
        if name not in recent:
            recent.insert(0, name)
            used[str(gid)] = recent[:200]
            set_used_names(used)
            return name
    return base[:32]

# =============== BUFF MEM THEO LINK MỜI ===============
invite_cache = {}

async def refresh_invites_for_guild(guild: discord.Guild):
    invs = await guild.invites()
    invite_cache[guild.id] = {i.code: i.uses for i in invs}
    all_inv = load_json(INVITES_FILE, {})
    all_inv[str(guild.id)] = invite_cache[guild.id]
    save_json(INVITES_FILE, all_inv)

async def detect_used_invite(member: discord.Member):
    after = await member.guild.invites()
    before = invite_cache.get(member.guild.id, {})
    used_code = None
    for inv in after:
        if inv.uses > before.get(inv.code, 0):
            used_code = inv.code
            break
    invite_cache[member.guild.id] = {i.code: i.uses for i in after}
    all_inv = load_json(INVITES_FILE, {})
    all_inv[str(member.guild.id)] = invite_cache[member.guild.id]
    save_json(INVITES_FILE, all_inv)
    return used_code

async def apply_buff_rule(member: discord.Member, code: str):
    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].get(str(member.guild.id))
    if not g or not g.get("buff_enabled", True):
        return
    conf = g.get("links", {}).get(code)
    if not conf:
        return
    nick = generate_nickname(member.guild.id)
    try:
        await member.edit(nick=nick, reason="buff mem")
    except:
        pass
    for rid in conf.get("role_ids", []):
        r = member.guild.get_role(rid)
        if r:
            try:
                await member.add_roles(r)
            except:
                pass

# =============== EXP, LEVEL, NHIỆT, TEAM ===============
def calc_level_from_total_exp(total_exp: int):
    lvl = 0
    spent = 0
    while True:
        need = 5 * (lvl ** 2) + 50 * lvl + 100
        if total_exp < need:
            return lvl, need - total_exp, spent
        total_exp -= need
        spent += need
        lvl += 1

voice_state_map = {}  # {guild_id: {user_id: start_time}}

def ensure_user(exp_data, uid: str):
    if uid not in exp_data["users"]:
        exp_data["users"][uid] = {
            "exp_chat": 0,
            "exp_voice": 0,
            "last_msg": None,
            "voice_seconds_week": 0,
            "heat": 0.0
        }
    else:
        exp_data["users"][uid].setdefault("heat", 0.0)

def add_heat(user_obj: dict, amount: float):
    user_obj["heat"] = float(min(10.0, user_obj.get("heat", 0.0) + amount))

def team_boost_today(gid: int, member: discord.Member):
    att = load_json(ATTEND_FILE, {"guilds": {}})
    teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
    g_conf = teamconf["guilds"].get(str(gid), {})
    g_att = att["guilds"].get(str(gid), {})
    today = today_str_gmt7()
    for rid, c in g_conf.get("teams", {}).items():
        role = member.guild.get_role(int(rid))
        if role and role in member.roles:
            day_info = g_att.get(str(rid), {}).get(today, {})
            if day_info.get("boost", False):
                return True
    return False

def add_team_score(gid: int, rid: int, date: str, amount: float):
    ts = load_json(TEAMSCORE_FILE, {"guilds": {}})
    g = ts["guilds"].setdefault(str(gid), {})
    r = g.setdefault(str(rid), {})
    r[date] = r.get(date, 0) + amount
    save_json(TEAMSCORE_FILE, ts)

# =============== SỰ KIỆN VOICE: EXP VOICE + NHIỆT + ĐIỂM TEAM ===============
@bot.event
async def on_voice_state_update(member, before, after):
    def open_mic(v):
        return v.channel and not v.self_mute and not v.mute and not v.self_deaf and not v.deaf

    gid = member.guild.id
    voice_state_map.setdefault(gid, {})

    if is_weekend_lock():
        return

    was = open_mic(before)
    now = open_mic(after)

    if now and not was:
        # bắt đầu
        voice_state_map[gid][member.id] = now_utc()
    elif was and not now:
        start = voice_state_map[gid].pop(member.id, None)
        if start:
            secs = (now_utc() - start).total_seconds()
            if secs > 5:
                bonus = int(secs // 30)
                exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
                uid = str(member.id)
                ensure_user(exp_data, uid)
                u = exp_data["users"][uid]

                if bonus > 0:
                    if team_boost_today(gid, member):
                        bonus *= 2
                    u["exp_voice"] += bonus
                u["voice_seconds_week"] += int(secs)

                # nhiệt từ voice
                heat_add = (secs / 600.0) * 0.2  # 10p = 0.2
                add_heat(u, heat_add)

                save_json(EXP_FILE, exp_data)
                total_now = u["exp_chat"] + u["exp_voice"]
                try_grant_level_reward(member, total_now)

                # điểm team từ voice (nếu user active)
                att = load_json(ATTEND_FILE, {"guilds": {}})
                g_att = att["guilds"].get(str(gid), {})
                today = today_str_gmt7()
                for rid, daymap in g_att.items():
                    di = daymap.get(today)
                    if not di:
                        continue
                    if str(member.id) in di.get("active_members", []):
                        team_pts = (secs / 60.0) * 0.2
                        if di.get("boost", False):
                            team_pts *= 2
                        add_team_score(gid, int(rid), today, team_pts)
                        break

def try_grant_level_reward(member: discord.Member, new_total_exp: int):
    level, to_next, _ = calc_level_from_total_exp(new_total_exp)
    data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
    g = data["guilds"].get(str(member.guild.id), {})
    rid = g.get(str(level))
    if not rid:
        return
    role = member.guild.get_role(rid)
    if role and role not in member.roles:
        asyncio.create_task(member.add_roles(role, reason=f"Đạt level {level}"))

# =============== SỰ KIỆN MESSAGE: EXP CHAT + NHIỆT + ĐIỂM TEAM ===============
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    if not is_weekend_lock():
        cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False, "last_reset": ""})
        gconf = cfg["guilds"].get(str(message.guild.id), {})
        exp_chs = gconf.get("exp_channels", [])
        allow = (not exp_chs) or (message.channel.id in exp_chs)
        if allow:
            exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
            uid = str(message.author.id)
            ensure_user(exp_data, uid)
            u = exp_data["users"][uid]
            last = u.get("last_msg")
            if not last or (now_utc() - datetime.fromisoformat(last)).total_seconds() >= 10:
                add_exp = random.randint(5, 15)
                if team_boost_today(message.guild.id, message.author):
                    add_exp *= 2
                u["exp_chat"] += add_exp
                u["last_msg"] = now_utc().isoformat()

                # nhiệt từ chat
                add_heat(u, (add_exp / 20.0) * 0.1)

                save_json(EXP_FILE, exp_data)
                total_now = u["exp_chat"] + u["exp_voice"]
                try_grant_level_reward(message.author, total_now)

                # điểm team từ chat nếu active
                att = load_json(ATTEND_FILE, {"guilds": {}})
                g_att = att["guilds"].get(str(message.guild.id), {})
                today = today_str_gmt7()
                for rid, daymap in g_att.items():
                    di = daymap.get(today)
                    if not di:
                        continue
                    if str(message.author.id) in di.get("active_members", []):
                        add_team_score(message.guild.id, int(rid), today, 0.1)
                        break

    await bot.process_commands(message)

# =============== READY & JOIN ===============
@bot.event
async def on_ready():
    print("✅ Bot online:", bot.user)
    for g in bot.guilds:
        try:
            await refresh_invites_for_guild(g)
        except:
            pass
    auto_weekly_reset.start()
    auto_diemdanh_dm.start()

@bot.event
async def on_member_join(member: discord.Member):
    code = await detect_used_invite(member)
    if code:
        await apply_buff_rule(member, code)

# =============== VIEW KÊNH EXP ===============
class KenhExpView(discord.ui.View):
    def __init__(self, ctx, cfg):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cfg = cfg

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    @discord.ui.button(label="➕ Set kênh này", style=discord.ButtonStyle.success)
    async def set_this(self, interaction: discord.Interaction, button):
        gid = str(self.ctx.guild.id)
        g = self.cfg["guilds"].setdefault(gid, {})
        lst = g.get("exp_channels", [])
        if interaction.channel.id not in lst:
            lst.append(interaction.channel.id)
        g["exp_channels"] = lst
        save_json(CONFIG_FILE, self.cfg)
        await interaction.response.edit_message(content=f"✅ Đã set {interaction.channel.mention} tính exp", view=self)

    @discord.ui.button(label="🗑 Xóa kênh này", style=discord.ButtonStyle.danger)
    async def del_this(self, interaction: discord.Interaction, button):
        gid = str(self.ctx.guild.id)
        g = self.cfg["guilds"].setdefault(gid, {})
        lst = g.get("exp_channels", [])
        if interaction.channel.id in lst:
            lst.remove(interaction.channel.id)
        g["exp_channels"] = lst
        save_json(CONFIG_FILE, self.cfg)
        await interaction.response.edit_message(content=f"🗑 Đã xóa {interaction.channel.mention} khỏi exp", view=self)

    @discord.ui.button(label="➕ Thêm kênh phụ", style=discord.ButtonStyle.secondary)
    async def hint(self, interaction: discord.Interaction, button):
        await interaction.response.send_message("👉 Thêm nhiều kênh: `/kenhchat #k1 #k2 #k3`", ephemeral=True)

    @discord.ui.button(label="📜 Danh sách", style=discord.ButtonStyle.primary)
    async def list_all(self, interaction: discord.Interaction, button):
        gid = str(self.ctx.guild.id)
        g = self.cfg["guilds"].setdefault(gid, {})
        lst = g.get("exp_channels", [])
        if not lst:
            await interaction.response.send_message("📭 Chưa có kênh exp.", ephemeral=True)
        else:
            chans = []
            for cid in lst:
                c = self.ctx.guild.get_channel(cid)
                if c:
                    chans.append(c.mention)
            await interaction.response.send_message("📜 Kênh exp: " + ", ".join(chans), ephemeral=True)

# =============== PHÂN TRANG CHUNG ===============
class PageView(discord.ui.View):
    def __init__(self, ctx, pages):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.pages = pages
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button):
        if self.index > 0:
            self.index -= 1
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button):
        if self.index < len(self.pages)-1:
            self.index += 1
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)
        else:
            await interaction.response.defer()

# =============== LỆNH NGƯỜI DÙNG / ADMIN / CHỦ BOT ===============
@bot.command(name="lenh")
async def cmd_lenh(ctx):
    await ctx.reply(
        "📜 LỆNH NGƯỜI DÙNG:\n"
        "/hoso – xem hồ sơ tu luyện\n"
        "/bangcapdo – bảng exp lên cấp\n"
        "/topnhiet – top nhiệt huyết (cá nhân)\n"
        "/diemdanh – điểm danh theo team (nếu admin bật)\n"
        "/bxhkimlan – xem các team điểm danh 7 ngày\n"
        "/bxhkimlan @team – xem chi tiết 1 team"
    )

@bot.command(name="lenhadmin")
async def cmd_lenhadmin(ctx):
    if not is_admin_ctx(ctx):
        await ctx.reply("⛔ Bạn không phải admin.")
        return
    await ctx.reply(
        "🛠 LỆNH ADMIN:\n"
        "/kenhchat [#k...] – quản lý kênh tính exp\n"
        "/setdiemdanh @role... [#kenh] [giờ phút tối thiểu] – bật điểm danh\n"
        "/thongke – thống kê exp theo cấp độ\n"
        "/topnhiet [tuantruoc] – top nhiệt huyết\n"
        "/setthuongcap <level> @role – đạt lvl tặng role\n"
        "/xemthuongcap – xem mốc thưởng\n"
        "/bxhkimlan – xem tổng quan team 7 ngày"
    )

@bot.command(name="lenhchubot")
async def cmd_lenhchubot(ctx):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Không phải chủ bot.")
        return
    await ctx.reply(
        "👑 LỆNH CHỦ BOT:\n"
        "/setlink <link> [@role ...]\n"
        "/xemlink\n"
        "/xoalink <link>\n"
        "/batbuff /tatbuff"
    )

# =============== /kenhchat ===============
@bot.command(name="kenhchat")
@commands.has_permissions(manage_guild=True)
async def cmd_kenhchat(ctx, *channels: discord.TextChannel):
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False, "last_reset": ""})
    if channels:
        gid = str(ctx.guild.id)
        g = cfg["guilds"].setdefault(gid, {})
        lst = g.get("exp_channels", [])
        for ch in channels:
            if ch.id not in lst:
                lst.append(ch.id)
        g["exp_channels"] = lst
        save_json(CONFIG_FILE, cfg)
        await ctx.reply("✅ Đã thêm kênh vào danh sách exp.")
    else:
        await ctx.reply("Quản lý kênh exp:", view=KenhExpView(ctx, cfg))

# =============== /hoso ===============
@bot.command(name="hoso")
async def cmd_hoso(ctx, member: discord.Member=None):
    if member is None:
        member = ctx.author
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    u = exp_data["users"].get(str(member.id))
    if not u:
        await ctx.reply("📭 Chưa có dữ liệu.")
        return
    total = u.get("exp_chat",0) + u.get("exp_voice",0)
    level, to_next, spent = calc_level_from_total_exp(total)
    exp_in_level = total - spent
    heat = u.get("heat", 0.0)
    await ctx.reply(
        f"📄 Hồ sơ của {member.mention}:\n"
        f"- Level: **{level}**\n"
        f"- Tiến độ: {exp_in_level}/{exp_in_level + to_next} exp\n"
        f"- Chat: {u.get('exp_chat',0)} | Voice: {u.get('exp_voice',0)}\n"
        f"- Thoại: {math.floor(u.get('voice_seconds_week',0)/60)} phút\n"
        f"- Nhiệt huyết: **{heat:.1f}/10**"
    )

# =============== /bangcapdo ===============
@bot.command(name="bangcapdo")
async def cmd_bangcapdo(ctx, max_level: int=10):
    lines = ["📘 BẢNG EXP LÊN CẤP:"]
    total = 0
    for lvl in range(0, max_level+1):
        need = 5*(lvl**2) + 50*lvl + 100
        total += need
        lines.append(f"- Level {lvl}: cần {need} exp (tổng tới đây: {total})")
    await ctx.reply("\n".join(lines))

# =============== /thongke (exp) ===============
@bot.command(name="thongke")
async def cmd_thongke(ctx):
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    users = exp_data.get("users", {})
    role_filter = ctx.message.role_mentions[0] if ctx.message.role_mentions else None
    rows = []
    for uid, info in users.items():
        m = ctx.guild.get_member(int(uid))
        if not m:
            continue
        if role_filter and role_filter not in m.roles:
            continue
        total = info.get("exp_chat",0) + info.get("exp_voice",0)
        level, to_next, spent = calc_level_from_total_exp(total)
        exp_in_level = total - spent
        rows.append((
            m,
            total,
            level,
            exp_in_level,
            exp_in_level + to_next,
            math.floor(info.get("voice_seconds_week",0)/60),
            info.get("heat",0.0)
        ))
    rows.sort(key=lambda x: x[1], reverse=True)
    if not rows:
        await ctx.reply("📭 Không có dữ liệu.")
        return

    pages = []
    per = 10
    for i in range(0, len(rows), per):
        chunk = rows[i:i+per]
        e = discord.Embed(title="📑 THỐNG KÊ EXP", description=f"Trang {i//per + 1}", color=0x3498DB)
        for idx,(m,total,lv,ein,eneed,vm,heat) in enumerate(chunk, start=i+1):
            e.add_field(
                name=f"{idx}. {m.display_name}",
                value=f"Lv.{lv} • {ein}/{eneed} exp  |  Thoại: {vm}p  |  Nhiệt: {heat:.1f}/10",
                inline=False
            )
        pages.append(e)
    if len(pages) == 1:
        await ctx.reply(embed=pages[0])
    else:
        await ctx.reply(embed=pages[0], view=PageView(ctx, pages))

# =============== /topnhiet ===============
@bot.command(name="topnhiet")
async def cmd_topnhiet(ctx, mode: str=None):
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    if mode == "tuantruoc":
        source = exp_data.get("prev_week", {})
        title_suf = " (tuần trước)"
    else:
        source = exp_data.get("users", {})
        title_suf = ""
    rows = []
    for uid, info in source.items():
        m = ctx.guild.get_member(int(uid))
        if not m:
            continue
        total = info.get("exp_chat",0) + info.get("exp_voice",0)
        level, to_next, spent = calc_level_from_total_exp(total)
        exp_in_level = total - spent
        rows.append((m, info.get("heat",0.0), level, exp_in_level, exp_in_level+to_next, math.floor(info.get("voice_seconds_week",0)/60)))
    rows.sort(key=lambda x: x[1], reverse=True)
    if not rows:
        await ctx.reply("📭 Không có dữ liệu.")
        return
    pages = []
    per = 10
    for i in range(0, len(rows), per):
        chunk = rows[i:i+per]
        e = discord.Embed(title=f"🔥 TOP NHIỆT HUYẾT{title_suf}", description=f"Trang {i//per+1}", color=0xFF8C00)
        for idx,(m,heat,lv,ein,eneed,vm) in enumerate(chunk, start=i+1):
            e.add_field(
                name=f"{idx}. {m.display_name}",
                value=f"Lv.{lv} • {ein}/{eneed} exp  |  Thoại: {vm}p  |  Nhiệt: {heat:.1f}/10",
                inline=False
            )
        pages.append(e)
    if len(pages) == 1:
        await ctx.reply(embed=pages[0])
    else:
        await ctx.reply(embed=pages[0], view=PageView(ctx, pages))

# =============== /setthuongcap, /xemthuongcap ===============
@bot.command(name="setthuongcap")
@commands.has_permissions(manage_guild=True)
async def cmd_setthuongcap(ctx, level: int, role: discord.Role):
    data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
    g = data["guilds"].setdefault(str(ctx.guild.id), {})
    g[str(level)] = role.id
    save_json(LEVEL_REWARD_FILE, data)
    await ctx.reply(f"✅ Khi đạt level {level} sẽ được role {role.mention}")

@bot.command(name="xemthuongcap")
async def cmd_xemthuongcap(ctx):
    data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
    g = data["guilds"].get(str(ctx.guild.id), {})
    if not g:
        await ctx.reply("📭 Chưa có mốc thưởng.")
        return
    lines = ["🎁 Mốc thưởng cấp:"]
    for lv, rid in sorted(g.items(), key=lambda x: int(x[0])):
        r = ctx.guild.get_role(rid)
        lines.append(f"- Level {lv} → {r.mention if r else rid}")
    await ctx.reply("\n".join(lines))

# =============== /setdiemdanh ===============
@bot.command(name="setdiemdanh")
@commands.has_permissions(manage_guild=True)
async def cmd_setdiemdanh(ctx, *, _rest: str=""):
    roles = ctx.message.role_mentions
    channels = ctx.message.channel_mentions
    parts = ctx.message.content.split()
    nums = [p for p in parts if p.isdigit()]
    start_hour = 20
    start_min = 0
    min_count = 9
    if len(nums) >= 1: start_hour = int(nums[0])
    if len(nums) >= 2: start_min = int(nums[1])
    if len(nums) >= 3: min_count = int(nums[2])
    if not roles:
        await ctx.reply("❌ Bạn phải tag ít nhất 1 role.")
        return
    channel = channels[0] if channels else None

    tc = load_json(TEAMCONF_FILE, {"guilds": {}})
    g = tc["guilds"].setdefault(str(ctx.guild.id), {"teams": {}})
    for r in roles:
        g["teams"][str(r.id)] = {
            "name": r.name,
            "channel_id": channel.id if channel else None,
            "start_hour": start_hour,
            "start_minute": start_min,
            "min_count": min_count,
            "max_tag": 3
        }
    save_json(TEAMCONF_FILE, tc)
    await ctx.reply(f"✅ Đã cấu hình điểm danh cho {len(roles)} role.")

# =============== /diemdanh ===============
@bot.command(name="diemdanh")
async def cmd_diemdanh(ctx):
    if is_weekend_lock():
        await ctx.reply("⛔ Cuối tuần nghỉ điểm danh.")
        return

    member = ctx.author
    guild_id = str(ctx.guild.id)
    teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
    att = load_json(ATTEND_FILE, {"guilds": {}})
    teams = teamconf["guilds"].get(guild_id, {}).get("teams", {})
    g_att = att["guilds"].setdefault(guild_id, {})
    role_id = None
    conf = None
    for rid, c in teams.items():
        role = ctx.guild.get_role(int(rid))
        if role and role in member.roles:
            role_id = int(rid)
            conf = c
            break
    if not conf:
        await ctx.reply("⛔ Bạn không thuộc team nào đang bật điểm danh.")
        return

    now = gmt7_now()
    if (now.hour, now.minute) < (conf.get("start_hour",20), conf.get("start_minute",0)):
        await ctx.reply("⏰ Chưa tới giờ điểm danh.")
        return

    today = today_str_gmt7()
    day_data = g_att.setdefault(str(role_id), {}).setdefault(today, {
        "checked": [],
        "dm_sent": [],
        "tag_count": 0,
        "boost": False,
        "total_at_day": 0,
        "active_members": []
    })

    role_obj = ctx.guild.get_role(role_id)
    total_members = len(role_obj.members) if role_obj else 0
    day_data["total_at_day"] = total_members

    uid = str(member.id)
    if uid in day_data["checked"]:
        await ctx.reply("✅ Bạn đã điểm danh hôm nay rồi.")
        return

    # đánh dấu
    day_data["checked"].append(uid)
    if uid not in day_data["active_members"]:
        day_data["active_members"].append(uid)

    # cộng điểm team: điểm danh = +1
    add_team_score(ctx.guild.id, role_id, today, 1)

    # cộng nhiệt cá nhân
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    ensure_user(exp_data, uid)
    u = exp_data["users"][uid]
    add_heat(u, 0.5)  # điểm danh = +0.5
    save_json(EXP_FILE, exp_data)

    g_att[str(role_id)][today] = day_data
    att["guilds"][guild_id] = g_att
    save_json(ATTEND_FILE, att)

    checked = len(day_data["checked"])
    await ctx.reply(f"✅ Điểm danh thành công cho **{conf.get('name','Team')}** ({checked}/{total_members})")

    # tag nhắc những người chưa điểm danh
    if day_data["tag_count"] < conf.get("max_tag",3) and role_obj:
        not_checked = [m for m in role_obj.members if str(m.id) not in day_data["checked"]]
        if not_checked:
            ch = ctx.guild.get_channel(conf.get("channel_id")) or ctx.channel
            await ch.send(
                f"Các bạn thân yêu ơi! Đã đến giờ hoạt động team rồi, hãy online đi hoạt động cùng **{conf.get('name','Team')}** nha 💛\n"
                f"Chưa điểm danh: {' '.join(m.mention for m in not_checked[:20])}"
            )
            day_data["tag_count"] += 1
            g_att[str(role_id)][today] = day_data
            att["guilds"][guild_id] = g_att
            save_json(ATTEND_FILE, att)

    # kiểm tra kích hoạt boost
    need = conf.get("min_count", 9)
    enough_count = checked >= need
    enough_percent = total_members > 0 and checked / total_members >= 0.75
    if not day_data.get("boost", False) and (enough_count or enough_percent):
        day_data["boost"] = True
        g_att[str(role_id)][today] = day_data
        att["guilds"][guild_id] = g_att
        save_json(ATTEND_FILE, att)
        add_team_score(ctx.guild.id, role_id, today, 5)  # thưởng team
        # thưởng thêm nhiệt cho người vừa kích hoạt
        exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
        ensure_user(exp_data, uid)
        u = exp_data["users"][uid]
        add_heat(u, 0.3)
        save_json(EXP_FILE, exp_data)
        ch = ctx.guild.get_channel(conf.get("channel_id")) or ctx.channel
        await ch.send(f"🎉 Team **{conf.get('name','Team')}** đã kích hoạt x2 hôm nay!")

# =============== /bxhkimlan (tổng & chi tiết) ===============
@bot.command(name="bxhkimlan")
async def cmd_bxhkimlan(ctx, role: discord.Role=None):
    teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
    att = load_json(ATTEND_FILE, {"guilds": {}})
    teamscore = load_json(TEAMSCORE_FILE, {"guilds": {}})

    gid = str(ctx.guild.id)
    teams_conf = teamconf["guilds"].get(gid, {}).get("teams", {})
    att_guild = att["guilds"].get(gid, {})
    score_guild = teamscore["guilds"].get(gid, {})
    today = today_str_gmt7()

    # --- không tag -> tổng hợp tất cả team ---
    if role is None:
        if not teams_conf:
            await ctx.reply("📭 Chưa có team nào.")
            return
        results = []
        for rid, conf in teams_conf.items():
            r_obj = ctx.guild.get_role(int(rid))
            name = conf.get("name") or (r_obj.name if r_obj else f"Role {rid}")
            role_days = att_guild.get(rid, {})
            days = sorted(role_days.keys(), reverse=True)[:7]
            total_quy = 0
            total_rate = 0
            count_day = 0
            good_days = []
            bad_days = []
            for d in days:
                info = role_days[d]
                tot = info.get("total_at_day", 0)
                chk = len(info.get("checked", []))
                boosted = info.get("boost", False)
                total_quy += score_guild.get(d, 0)
                if tot > 0:
                    rate = chk / tot
                    total_rate += rate
                    count_day += 1
                    wd = datetime.fromisoformat(d).weekday()
                    thu = ["T2","T3","T4","T5","T6","T7","CN"][wd]
                    if chk == tot:
                        good_days.append(f"{thu} {chk}/{tot}" + (" (x2)" if boosted else ""))
                    else:
                        bad_days.append(f"{thu} {chk}/{tot}")
            avg = (total_rate / count_day * 100) if count_day else 0
            results.append({
                "name": name,
                "quy": total_quy,
                "good": good_days,
                "bad": bad_days,
                "avg": avg
            })
        results.sort(key=lambda x: x["quy"], reverse=True)
        pages = []
        per = 10
        for i in range(0, len(results), per):
            chunk = results[i:i+per]
            e = discord.Embed(
                title="📊 BẢNG ĐIỂM DANH CÁC TEAM (7 ngày)",
                description=f"Trang {i//per + 1}",
                color=0x2ecc71
            )
            for idx, t in enumerate(chunk, start=i+1):
                good = ", ".join(t["good"]) if t["good"] else "—"
                bad = ", ".join(t["bad"]) if t["bad"] else "—"
                e.add_field(
                    name=f"{idx}. {t['name']}",
                    value=f"Ngày điểm danh: {good}\nNgày không đủ: {bad}\nTổng điểm quỹ: **{t['quy']:.1f}** | Tỷ lệ TB: **{t['avg']:.0f}%**",
                    inline=False
                )
            pages.append(e)
        if len(pages) == 1:
            await ctx.reply(embed=pages[0])
        else:
            await ctx.reply(embed=pages[0], view=PageView(ctx, pages))
        return

    # --- có tag -> chi tiết 1 team ---
    rid = str(role.id)
    if rid not in teams_conf:
        await ctx.reply("❌ Team này chưa được /setdiemdanh.")
        return
    role_days = att_guild.get(rid, {})
    if not role_days:
        await ctx.reply("📭 Team này chưa có dữ liệu.")
        return
    days = sorted(role_days.keys(), reverse=True)[:7]
    lines = [f"📅 BẢNG ĐIỂM DANH TEAM **{role.name}**", f"Từ {days[-1]} → {days[0]}"]
    total_quy = 0
    hit = 0
    dd_day = 0
    for d in days:
        info = role_days[d]
        tot = info.get("total_at_day", 0)
        chk = len(info.get("checked", []))
        boosted = info.get("boost", False)
        total_quy += score_guild.get(d, 0)
        wd = datetime.fromisoformat(d).weekday()
        thu = ["Thứ 2","Thứ 3","Thứ 4","Thứ 5","Thứ 6","Thứ 7","CN"][wd]
        if tot == 0:
            lines.append(f"{thu}: ❌ 0/0")
        else:
            dd_day += 1
            if chk == tot:
                icon = "✅"
                hit += 1
            elif chk == 0:
                icon = "❌"
            else:
                icon = "⚠️"
            extra = " (x2)" if boosted else ""
            lines.append(f"{thu}: {icon} {chk}/{tot}{extra}")
    rate = int(hit / dd_day * 100) if dd_day else 0
    lines.append(f"\nTổng điểm quỹ: **{total_quy:.1f}**  |  Tỷ lệ điểm danh TB: **{rate}%**")
    await ctx.reply("\n".join(lines))

# =============== DM NHẮC ĐIỂM DANH ===============
@tasks.loop(minutes=10)
async def auto_diemdanh_dm():
    if is_weekend_lock():
        return
    att = load_json(ATTEND_FILE, {"guilds": {}})
    today = today_str_gmt7()
    for guild in bot.guilds:
        g_att = att["guilds"].get(str(guild.id), {})
        for rid, daymap in g_att.items():
            di = daymap.get(today)
            if not di:
                continue
            role = guild.get_role(int(rid))
            if not role:
                continue
            dm_sent = set(di.get("dm_sent", []))
            not_checked = [m for m in role.members if str(m.id) not in di.get("checked", [])]
            to_dm = [m for m in not_checked if str(m.id) not in dm_sent]
            for m in to_dm[:10]:
                try:
                    await m.send(f"💛 Team **{role.name}** đang điểm danh, dùng /diemdanh nha.")
                except:
                    pass
                di.setdefault("dm_sent", []).append(str(m.id))
            g_att[rid][today] = di
        att["guilds"][str(guild.id)] = g_att
    save_json(ATTEND_FILE, att)

# =============== RESET TUẦN ===============
@tasks.loop(minutes=5)
async def auto_weekly_reset():
    now = gmt7_now()
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False, "last_reset": ""})
    last_reset = cfg.get("last_reset", "")
    today = now.date().isoformat()

    # 00:00 thứ 7
    if now.weekday() == 5 and now.hour == 0 and last_reset != today:
        exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
        exp_data["prev_week"] = exp_data.get("users", {})
        exp_data["users"] = {}
        save_json(EXP_FILE, exp_data)
        cfg["last_reset"] = today
        cfg["exp_locked"] = True
        save_json(CONFIG_FILE, cfg)
        print("🔁 Reset tuần.")

    # mở lại T2 14:00
    if now.weekday() == 0 and now.hour >= 14 and cfg.get("exp_locked", False):
        cfg["exp_locked"] = False
        save_json(CONFIG_FILE, cfg)
        print("🔓 Mở lại exp sau reset.")

# =============== LỆNH CHỦ BOT: BUFF LINK ===============
@bot.command(name="setlink")
async def cmd_setlink(ctx, invite_url: str, *roles: discord.Role):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ chủ bot dùng được.")
        return
    code = invite_url.strip().split("/")[-1]
    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].setdefault(str(ctx.guild.id), {"buff_enabled": True, "links": {}})
    g["links"][code] = {"role_ids": [r.id for r in roles], "active": True}
    save_json(BUFF_FILE, data)
    await ctx.reply("✅ Đã gán link buff.")

@bot.command(name="xemlink")
async def cmd_xemlink(ctx):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ chủ bot.")
        return
    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].get(str(ctx.guild.id))
    if not g:
        await ctx.reply("📭 Chưa có link.")
        return
    lines = [f"Buff: {'ON' if g.get('buff_enabled',True) else 'OFF'}"]
    for code, conf in g.get("links", {}).items():
        lines.append(f"- {code}: {conf}")
    await ctx.reply("\n".join(lines))

@bot.command(name="xoalink")
async def cmd_xoalink(ctx, invite_url: str):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ chủ bot.")
        return
    code = invite_url.strip().split("/")[-1]
    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].get(str(ctx.guild.id))
    if not g or code not in g.get("links", {}):
        await ctx.reply("❌ Không có link này.")
        return
    g["links"][code]["active"] = False
    save_json(BUFF_FILE, data)
    await ctx.reply("✅ Đã tắt link này.")

@bot.command(name="batbuff")
async def cmd_batbuff(ctx):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ chủ bot.")
        return
    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].setdefault(str(ctx.guild.id), {"buff_enabled": True, "links": {}})
    g["buff_enabled"] = True
    save_json(BUFF_FILE, data)
    await ctx.reply("✅ Đã bật buff mem.")

@bot.command(name="tatbuff")
async def cmd_tatbuff(ctx):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ chủ bot.")
        return
    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].setdefault(str(ctx.guild.id), {"buff_enabled": False, "links": {}})
    g["buff_enabled"] = False
    save_json(BUFF_FILE, data)
    await ctx.reply("✅ Đã tắt buff mem.")

# =============== CHẠY BOT ===============
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Thiếu DISCORD_TOKEN")
    else:
        bot.run(DISCORD_TOKEN)
