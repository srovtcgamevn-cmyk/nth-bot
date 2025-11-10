# -*- coding: utf-8 -*-
"""
Nghich Thuy Han New - BANG_CHU_SUPREME
1 FILE DUY NHẤT
- exp chat: 1 phút / lần
- exp voice: 1 phút / lần, phải mở mic (không mute/deaf)
- điểm danh team -> kích hoạt x2
- top nhiệt huyết / thống kê / bxh kim lan
- buff mem theo link
- thưởng cấp độ + thu hồi thứ 2
- backup tự động + backup thủ công
"""

import os, json, random, math, asyncio, shutil
from datetime import datetime, timedelta, timezone, UTC

import discord
from discord.ext import commands, tasks



# ================== CẤU HÌNH CƠ BẢN ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OWNER_DISCORD_ID = 821066331826421840  # ID của bạn

DATA_DIR = "data"
BACKUP_DIR = "backups"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


EXP_FILE          = os.path.join(DATA_DIR, "exp_week.json")
BUFF_FILE         = os.path.join(DATA_DIR, "buff_links.json")
NAMES_FILE        = os.path.join(DATA_DIR, "used_names.json")
INVITES_FILE      = os.path.join(DATA_DIR, "invites_cache.json")
CONFIG_FILE       = os.path.join(DATA_DIR, "config.json")
TEAMCONF_FILE     = os.path.join(DATA_DIR, "team_config.json")
ATTEND_FILE       = os.path.join(DATA_DIR, "attendance.json")
TEAMSCORE_FILE    = os.path.join(DATA_DIR, "team_scores.json")
LEVEL_REWARD_FILE = os.path.join(DATA_DIR, "level_rewards.json")
BACKUP_CONFIG_FILE = os.path.join(DATA_DIR, "backup_config.json")

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
    (BACKUP_CONFIG_FILE, {"guilds": {}, "last_run": ""}),
]
for p, d in default_files:
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

# intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

# ================== HÀM TIỆN ÍCH CHUNG ==================
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

# danh sách kênh thoại để bot đi tuần (per guild)
voice_patrol_config = {}  # {guild_id: [channel_id, ...]}
VOICE_PATROL_FILE = "voice_patrol.json"
voice_patrol_data = load_json(VOICE_PATROL_FILE, {"guilds": {}})
VOICE_BLOCK_FILE = "voice_blocked.json"
voice_block_data = load_json(VOICE_BLOCK_FILE, {"guilds": {}})


# ================== KHÓA EXP THEO LỊCH ==================
def is_weekend_lock():
    n = gmt7_now()
    wd = n.weekday()   # 0=Thứ2 ... 6=Chủ nhật
    hour = n.hour

    # 1) Chủ nhật: khóa cả ngày
    if wd == 6:
        return True

    # 2) Thứ 2: khóa đến 14:00
    if wd == 0:
        if hour < 14:
            return True
        return False

    # 3) Từ Thứ 3 đến Thứ 7: chỉ cho cày 09:00 -> 23:59
    # (tức là 00:00-08:59 khóa, 09:00-23:59 mở)
    if wd in (1, 2, 3, 4, 5):  # 1=Thứ3, 5=Thứ7
        if hour < 9:
            return True
        return False

    # fallback
    return False



# =============== BỘ TÊN ẢO (phiên bản mới – có dấu cách, không trùng) ===============

BASE_NAMES_WITH_ACCENT = [
    "An Vân", "Bạch Anh", "Bảo Vũ", "Cẩm Nguyệt", "Dạ Minh", "Diệp Hàn", "Gia Vân", "Hạ Mưa",
    "Hàn Yên", "Hoài Tuyết", "Hồ Thanh", "Khuê My", "Kim Thảo", "Lam Yên", "Lăng Uyển", "Lâm Tịnh",
    "Linh Hồ", "Long Yểu", "Lục Vy", "Mai Tử", "Mộc Liên", "Ngân Tâm", "Ngọc Hồ", "Nhã Vũ",
    "Nhược Y", "Oanh Tử", "Phỉ Thúy", "Phong Nguyệt", "Phương Hạ", "Quân Lam", "Quế Chi", "Quỳnh Vũ",
    "Sở My", "Tạ Vy", "Tâm Như", "Thanh Vũ", "Thiên Y", "Thiều Lan", "Thục Uyển", "Thư Vân",
    "Thương Nguyệt", "Tiểu Hàn", "Tịnh Tâm", "Trầm My", "Trân Yên", "Trang Uyển", "Triều Anh", "Trúc Vy",
    "Tuyết Di", "Uyển My", "Vân Ca", "Vân Khánh", "Vạn Thư", "Vi Yên", "Vy Hạ", "Yên Nhi", "Yểu My",
    "Yết Hoa", "Ánh Tuyết", "Ân Vy", "Ấu Lam", "Đan Tâm", "Đào Yên", "Đình My", "Bạch Hồ", "Băng Tuyền",
    "Bích Lan", "Cẩm Huyên", "Chu Yên", "Diệu Ca", "Dung Khê", "Gia Hạ", "Hà Uyển", "Hàn Ca",
    "Hạnh Vân", "Hiểu Tâm", "Hoàng Thư", "Huyền Ca", "Hương Nguyệt", "Kha My", "Khánh Yên", "Khương Tuyết",
    "Kiều Lam", "Lam Cơ", "Liễu Tuyền", "Linh Tố", "Lộ Vũ", "Ly Thảo", "Mai Nguyệt", "Mẫn Vy",
    "Mộng Thư", "Mỹ Hàn", "Ngân Huyên", "Ngôn Vy", "Nhược Ca", "Ôn My", "Phù Dung", "Phúc Yên",
    "Phụng Vân", "Quân Y", "Quế Tử", "Quỳnh Ca", "Tầm Xuân", "Tề My", "Thanh Cơ", "Thảo Yên",
    "Thi Ca", "Thiên Tâm", "Thục Chi", "Thủy Lam", "Tiểu Nguyệt", "Tịnh Nhi", "Trà Vy", "Trân Ca",
    "Triều Lam", "Trúc Hạ", "Tuyền Anh", "Uyển Ca", "Vân Giao", "Văn Hạ", "Vi Tâm", "Vy Minh",
    "Yên Hoa", "Yểu Thư", "Ái Khánh", "Âu Hạ", "Đàm My", "Đường Yên", "Đình Ca", "Bạch Tâm",
    "Băng Vân", "Bích Ngọc", "Cát My", "Cơ Uyển", "Diên Vy", "Dung Nhi", "Giang Vũ", "Hà My",
    "Hàn Tuyền", "Hạnh Chi", "Hiểu Vy", "Hoa Ca", "Hoài My", "Húc Nguyệt", "Kỳ Tâm", "Khả Vy",
    "Khương Vy", "Kim Uyển", "Lam Tuyết", "Liên Ca", "Linh Thảo", "Lộ My", "Ly Ca", "Mai Nhu",
    "Mẫn Chi", "Mộng Ca", "Mỹ Vy", "Ngân Ca", "Ngô Yên", "Nhạ Tuyết", "Phàn My", "Phó Vy",
    "Phục Yên", "Quân Hạ", "Quế Anh", "Quỳnh Tâm", "Song My", "Tạ Huyên", "Tâm Ca", "Thanh Di",
    "Thảo Vy", "Thiên Ca", "Thục Vũ", "Thủy Tâm", "Tiểu Vy", "Tịnh Ca", "Trà My", "Trân Hạ",
    "Triều Yên", "Trúc Ca", "Tuyền Vy", "Uyển Hạ", "Vân My", "Vũ Ca", "Vi Uyển", "Vy Tử",
    "Yên Tâm", "Yểu Ca", "Ánh Vy", "Ân Ca", "Đan Vy", "Đào Ca", "Đình Tâm"
]

BASE_NAMES_NO_ACCENT = [
    "an van", "bach anh", "bao vu", "cam nguyet", "da minh", "diep han", "gia van", "ha mua",
    "han yen", "hoai tuyet", "ho thanh", "khue my", "kim thao", "lam yen", "lang uyen", "lam tinh",
    "linh ho", "long yeu", "luc vy", "mai tu", "moc lien", "ngan tam", "ngoc ho", "nha vu",
    "nhuoc y", "oanh tu", "phi thuy", "phong nguyet", "phuong ha", "quan lam", "que chi", "quynh vu",
    "so my", "ta vy", "tam nhu", "thanh vu", "thien y", "thieu lan", "thuc uyen", "thu van",
    "thuong nguyet", "tieu han", "tinh tam", "tram my", "tran yen", "trang uyen", "trieu anh", "truc vy",
    "tuyet di", "uyen my", "van ca", "van khanh", "van thu", "vi yen", "vy ha", "yen nhi", "yeu my",
    "yet hoa", "anh tuyet", "an vy", "au lam", "dan tam", "dao yen", "dinh my", "bach ho", "bang tuyen",
    "bich lan", "cam huyen", "chu yen", "dieu ca", "dung khe", "gia ha", "ha uyen", "han ca",
    "hanh van", "hieu tam", "hoang thu", "huyen ca", "huong nguyet", "kha my", "khanh yen", "khuong tuyet",
    "kieu lam", "lam co", "lieu tuyen", "linh to", "lo vu", "ly thao", "mai nguyet", "man vy",
    "mong thu", "my han", "ngan huyen", "ngon vy", "nhuoc ca", "on my", "phu dung", "phuc yen",
    "phung van", "quan y", "que tu", "quynh ca", "tam xuan", "te my", "thanh co", "thao yen",
    "thi ca", "thien tam", "thuc chi", "thuy lam", "tieu nguyet", "tinh nhi", "tra vy", "tran ca",
    "trieu lam", "truc ha", "tuyen anh", "uyen ca", "van giao", "van ha", "vi tam", "vy minh",
    "yen hoa", "yeu thu", "ai khanh", "au ha", "dam my", "duong yen", "dinh ca", "bach tam",
    "bang van", "bich ngoc", "cat my", "co uyen", "dien vy", "dung nhi", "giang vu", "ha my",
    "han tuyen", "hanh chi", "hieu vy", "hoa ca", "hoai my", "huc nguyet", "ky tam", "kha vy",
    "khuong vy", "kim uyen", "lam tuyet", "lien ca", "linh thao", "lo my", "ly ca", "mai nhu",
    "man chi", "mong ca", "my vy", "ngan ca", "ngo yen", "nha tuyet", "phan my", "pho vy",
    "phuc yen", "quan ha", "que anh", "quynh tam", "song my", "ta huyen", "tam ca", "thanh di",
    "thao vy", "thien ca", "thuc vu", "thuy tam", "tieu vy", "tinh ca", "tra my", "tran ha",
    "trieu yen", "truc ca", "tuyen vy", "uyen ha", "van my", "vu ca", "vi uyen", "vy tu",
    "yen tam", "yeu ca", "anh vy", "an ca", "dan vy", "dao ca", "dinh tam"
]

SUFFIX_TOKENS = [
    # ---- Nhóm phong cách tu tiên / kiếm hiệp ----
    "kiem", "kiemton", "kiemha", "thienha", "linh", "thanh", "son", "phong", "vuong", "tien",
    "than", "nguyet", "long", "ngan", "bach", "huyen", "hieu", "anh", "lam", "ha",
    "tuyet", "dao", "phongvan", "am", "duong", "tich", "vien", "vo", "minh", "chi",
    # ---- Nhóm phong cách game thủ hiện đại ----
    "pro", "pro99", "vip", "vipx", "real", "realz", "no1", "top1", "main", "mainx",
    "ez", "zz", "x", "zx", "xx", "one", "neo", "rise", "king", "queen",
    "dark", "light", "lord", "god", "ghost", "demon", "angel", "night", "sun", "moon",
    "fire", "ice", "wind", "earth", "storm", "bolt", "nova", "flare", "core", "soul",
    # ---- Nhóm ký hiệu & biến thể vui ----
    "babyx", "baby", "chanh", "cute", "dz", "tv", "vn", "idol", "love", "lover",
    "boy", "girl", "x2", "x3", "dev", "admin", "prodev", "local", "player", "npc",
    "alpha", "beta", "omega", "clan", "team", "guild", "solo", "mainacc", "alt", "shadow",
    # ---- Nhóm pha trộn Việt / Tây ----
    "ngoc", "vy", "yuki", "sakura", "miko", "rina", "luna", "arya", "taro", "ryu",
    "akira", "ren", "kai", "shin", "aqua", "nova", "flare", "astra", "echo", "void",
    # ---- Đặc biệt dành cho fan Nghịch Thủy Hàn ----
    "nths", "nth", "bt1727", "kim", "han", "mo", "dao", "duyen", "thach", "ngoc"
]

DECOR_TOKENS = [
    # ---- Ký hiệu ma thuật / tu tiên ----
    "☯", "⚜", "⚡", "⚔", "❖", "☾", "❀", "✧", "✦", "☄", "♛", "♚", "♤", "♧", "♢", "♩", "♬",
    "⛩", "⛓", "☠", "🔥", "💀", "🌙", "🌸", "🌌", "✨", "💫", "🕊", "🌿", "🌀", "⚙", "🕯", "🌑",
    # ---- Ký hiệu kiểu hiện đại / sci-fi ----
    "★", "☆", "✪", "☪", "☼", "☁", "☃", "❄", "⚙", "⌛", "⚛", "☢", "☣", "⚰", "⚓", "⚒",
    # ---- Kiểu tượng cảm xúc ngầu / huyền ảo ----
    "ツ", "シ", "ッ", "彡", "乂", "メ", "ズ", "ッ", "卍", "々", "彡☆彡", "★彡", "☠彡", "⚔彡",
    "⛓彡", "❖彡", "✦彡", "⚡彡"
]

POPULAR_NUMBERS = [
    # ---- Năm sinh phổ biến ----
    "1997", "1998", "1999", "2000", "2001", "2002", "2003", "2004", "2005", "2006", "2007", "2008",
    "09", "07", "06", "05", "04", "03", "02", "01",
    # ---- Mã phong cách game thủ ----
    "69", "96", "97", "98", "99", "88", "777", "999", "666", "333", "555", "222", "123", "321", "404",
    # ---- Dãy đặc biệt & huyền thoại ----
    "0909", "0303", "0707", "1314", "2024", "2025", "0110", "1010", "1711", "2910", "2808", "1412",
    # ---- Số phong thủy / tượng trưng ----
    "08", "18", "28", "38", "68", "86", "168", "8888", "9999", "1313", "1212", "0101", "0709",
    # ---- Mã riêng cho cộng đồng NTH ----
    "1727", "0617", "1010", "0309", "2508", "1122"
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
        style = random.randint(0, 3)
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

# ================== BUFF MEM THEO LINK MỜI ==================
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

# ================== EXP / LEVEL / NHIỆT ==================
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
            "heat": 0.0,
            "chat_exp_buffer": 0,
            "voice_min_buffer": 0,
            "last_level_announce": 0,
        }
    else:
        exp_data["users"][uid].setdefault("heat", 0.0)
        exp_data["users"][uid].setdefault("last_msg", None)
        exp_data["users"][uid"].setdefault("chat_exp_buffer", 0)
        exp_data["users"][uid"].setdefault("voice_min_buffer", 0)
        exp_data["users"][uid"].setdefault("last_level_announce", 0)



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

# ================== THƯỞNG CẤP ==================
def try_grant_level_reward(member: discord.Member, new_total_exp: int):
    level, to_next, _ = calc_level_from_total_exp(new_total_exp)

    # thông báo kênh chung
    announce_channel = member.guild.system_channel
    if not announce_channel:
        for ch in member.guild.text_channels:
            if ch.permissions_for(member.guild.me).send_messages:
                announce_channel = ch
                break
    if announce_channel:
        try:
            asyncio.create_task(
                announce_channel.send(f"⭐ {member.mention} vừa đạt **level {level}**! Tiếp tục tu luyện nha.")
            )
        except:
            pass

    data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
    g = data["guilds"].get(str(member.guild.id), {})
    val = g.get(str(level))
    if not val:
        return

    if isinstance(val, int):
        role_ids = [val]
    else:
        role_ids = list(val)

    got_any = False
    for rid in role_ids:
        role = member.guild.get_role(rid)
        if role and role not in member.roles:
            asyncio.create_task(member.add_roles(role, reason=f"Đạt level {level}"))
            got_any = True

    if got_any:
        try:
            asyncio.create_task(
                member.send(
                    f"🎉 Bạn đã đạt **level {level}** ở **{member.guild.name}** và nhận role thưởng!"
                )
            )
        except:
            pass

# ================== SỰ KIỆN VOICE ==================
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
        voice_state_map[gid][member.id] = now_utc()
    elif was and not now:
        start = voice_state_map[gid].pop(member.id, None)
        if start:
            secs = (now_utc() - start).total_seconds()
            if secs > 5:
                bonus = int(secs // 60)
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
                heat_add = (secs / 600.0) * 0.2
                add_heat(u, heat_add)

                save_json(EXP_FILE, exp_data)
                total_now = u["exp_chat"] + u["exp_voice"]
                try_grant_level_reward(member, total_now)

                # điểm team từ voice
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

# ================== SỰ KIỆN CHAT ==================
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
            if (not last) or (now_utc() - datetime.fromisoformat(last)).total_seconds() >= 60:
                add_exp = random.randint(5, 15)
                if team_boost_today(message.guild.id, message.author):
                    add_exp *= 2
                u["exp_chat"] += add_exp
                u["last_msg"] = now_utc().isoformat()

                # chat -> nhiệt: 20 exp = 0.1
                u["chat_exp_buffer"] += add_exp
                while u["chat_exp_buffer"] >= 20:
                    add_heat(u, 0.1)
                    u["chat_exp_buffer"] -= 20
                    

                save_json(EXP_FILE, exp_data)
                total_now = u["exp_chat"] + u["exp_voice"]
                try_grant_level_reward(message.author, total_now)
    # THÔNG BÁO LÊN LEVEL KHÔNG TAG
                level, _, _ = calc_level_from_total_exp(total_now)
                last_ann = u.get("last_level_announce", 0)
                if level > last_ann:
                u["last_level_announce"] = level
                save_json(EXP_FILE, exp_data)
                try:
                await message.channel.send(
                f"🎉 **{message.author.display_name}** đã đạt **level {level}**!"
                )
                except:
                pass



                # điểm team từ chat
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

# ================== VIEW /kenhchat ==================
class KenhExpView(discord.ui.View):
    def __init__(self, ctx, cfg):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cfg = cfg

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    @discord.ui.button(label="➕ Set kênh này", style=discord.ButtonStyle.success)
    async def set_this(self, interaction: discord.Interaction, _):
        gid = str(self.ctx.guild.id)
        g = self.cfg["guilds"].setdefault(gid, {})
        lst = g.get("exp_channels", [])
        if interaction.channel.id not in lst:
            lst.append(interaction.channel.id)
        g["exp_channels"] = lst
        save_json(CONFIG_FILE, self.cfg)
        await interaction.response.edit_message(content=f"✅ Đã set {interaction.channel.mention} tính exp", view=self)

    @discord.ui.button(label="🗑 Xóa kênh này", style=discord.ButtonStyle.danger)
    async def del_this(self, interaction: discord.Interaction, _):
        gid = str(self.ctx.guild.id)
        g = self.cfg["guilds"].setdefault(gid, {})
        lst = g.get("exp_channels", [])
        if interaction.channel.id in lst:
            lst.remove(interaction.channel.id)
        g["exp_channels"] = lst
        save_json(CONFIG_FILE, self.cfg)
        await interaction.response.edit_message(content=f"🗑 Đã xóa {interaction.channel.mention} khỏi exp", view=self)

    @discord.ui.button(label="➕ Thêm kênh phụ", style=discord.ButtonStyle.secondary)
    async def hint(self, interaction: discord.Interaction, _):
        await interaction.response.send_message("👉 Thêm nhiều kênh: `/kenhchat #k1 #k2 #k3`", ephemeral=True)

    @discord.ui.button(label="📜 Danh sách", style=discord.ButtonStyle.primary)
    async def list_all(self, interaction: discord.Interaction, _):
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

# ================== VIEW PHÂN TRANG ==================
class PageView(discord.ui.View):
    def __init__(self, ctx, pages):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.pages = pages
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _):
        if self.index > 0:
            self.index -= 1
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _):
        if self.index < len(self.pages)-1:
            self.index += 1
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)
        else:
            await interaction.response.defer()

# ================== LỆNH CƠ BẢN ==================
@bot.command(name="lenh")
async def cmd_lenh(ctx):
    await ctx.reply(
        "📜 **LỆNH NGƯỜI DÙNG**\n\n"
        "`/hoso` – Xem hồ sơ\n"
        "`/bangcapdo` – Bảng exp lên cấp\n"
        "`/topnhiet` – Top nhiệt huyết\n"
        "`/diemdanh` – Điểm danh team (nếu đã bật)\n"
        "`/bxhkimlan` – Thống kê điểm danh các team\n"
        "`/bxhkimlan @team` – Chi tiết 1 team"
    )

@bot.command(name="lenhadmin")
async def cmd_lenhadmin(ctx):
    if not is_admin_ctx(ctx):
        await ctx.reply("⛔ Bạn không phải admin.")
        return
    await ctx.reply(
        "🛠 **LỆNH ADMIN**\n\n"
        "`/kenhchat` – Mở UI chọn kênh tính exp\n"
        "`/kenhchat #k1 #k2` – Thêm nhanh nhiều kênh\n"
        "`/setdiemdanh @role... [số]` – Cấu hình team điểm danh\n"
        "`/thongke` – Thống kê exp/nhiệt\n"
        "`/topnhiet [tuantruoc]` – Top nhiệt\n"
        "`/setthuongcap <level> @role..` – Thưởng level\n"
        "`/xemthuongcap` – Xem mốc thưởng\n"
        "`/thuhoithuong @r1 @r2` – Role bị thu thứ 2\n"
        "`/settuantra` – <giây> <ID KÊNH> Set kênh tuần tra theo ID kênh\n"
        "`/tuantra` <on> <off> – Bắt đầu tuần tra\n"
        "`/xemtuantra`– Xem lại kênh đang tuần tra\n"
        "`/camkenhthoai`– <ID KÊNH> Cấm kênh thoại không có exp\n"



    )

@bot.command(name="lenhchubot")
async def cmd_lenhchubot(ctx):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Không phải chủ bot.")
        return
    await ctx.reply(
        "👑 **LỆNH CHỦ BOT**\n\n"
        "`/setlink <invite> [@role..]` – Gắn link buff + role\n"
        "`/xemlink` – Xem link đang buff\n"
        "`/xoalink <invite>` – Tắt 1 link\n"
        "`/batbuff` / `tatbuff` – Bật/tắt hệ buff\n"
        "`/setkenhbackup` – Kênh nhận file backup\n"
        "`/backup` – Sao lưu thủ công"        
    )

# ================== /kenhchat ==================
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

# ================== /hoso (tiêu đề chỉ tên, tag ở cuối, team không tag) ==================
@bot.command(name="hoso")
async def cmd_hoso(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    u = exp_data["users"].get(str(member.id))
    if not u:
        await ctx.reply("📭 Chưa có dữ liệu.")
        return

    total = u.get("exp_chat", 0) + u.get("exp_voice", 0)
    level, to_next, spent = calc_level_from_total_exp(total)
    exp_in_level = total - spent
    need = exp_in_level + to_next
    voice_min = math.floor(u.get("voice_seconds_week", 0) / 60)
    heat = u.get("heat", 0.0)

    prev = exp_data.get("prev_week", {}).get(str(member.id), {})
    prev_chat = prev.get("exp_chat", 0)
    prev_voice = prev.get("exp_voice", 0)

    team_name = "Chưa thuộc team điểm danh"
    teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
    g_teams = teamconf["guilds"].get(str(ctx.guild.id), {}).get("teams", {})
    for rid, conf in g_teams.items():
        role = ctx.guild.get_role(int(rid))
        if role and role in member.roles:
            tname = conf.get("name") or role.name
            team_name = tname
            break

    try:
        has_boost = team_boost_today(ctx.guild.id, member)
    except Exception:
        has_boost = False

    bar_len = 14
    filled = int(bar_len * (exp_in_level / need)) if need > 0 else bar_len
    bar = "█" * filled + "░" * (bar_len - filled)

    embed = discord.Embed(
        title="📜 **Hồ Sơ Tu Luyện**",
        color=0xF1C40F
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    # phần mô tả, bắt đầu bằng tên người chơi ở dòng đầu
    desc = (
        f"**{member.display_name}**\n\n"
        "Theo dõi exp, thoại, nhiệt huyết và trạng thái điểm danh team.\n\n"
        "📈 **Cấp Độ**\n"
        f"• Level: **{level}**\n"
        f"• Tiến độ: **{exp_in_level}/{need} exp**\n"
        f"`{bar}`\n\n"
        "💬 **Tuần này**\n"
        f"• Chat: **{u.get('exp_chat', 0)} exp**\n"
        f"• Thoại: **{u.get('exp_voice', 0)} exp** — {voice_min} phút\n"
        f"• Nhiệt huyết: **{heat:.1f}/10**\n\n"
        "🕊️ **Tuần trước**\n"
        f"• Chat: **{prev_chat} exp**\n"
        f"• Thoại: **{prev_voice} exp**\n\n"
        "👥 **Team Kim Lan**\n"
        f"{team_name}\n\n"
        "🔥 **Buff điểm danh**\n"
        f"{'Đang nhận **x2 exp hôm nay**' if has_boost else 'Không hoạt động'}\n\n"
        f"👤 **Người xem:** {member.mention}"
    )

    embed.description = desc

    await ctx.reply(embed=embed)





# ================== /bangcapdo (phiên bản đẹp, tu tiên style) ==================
@bot.command(name="bangcapdo")
async def cmd_bangcapdo(ctx, max_level: int = 10):
    embed = discord.Embed(
        title="📘 BẢNG CẤP ĐỘ TU LUYỆN",
        description="Hiển thị lượng kinh nghiệm cần để thăng cảnh giới.\n",
        color=0x3498DB
    )

    total = 0
    lines = []
    symbols = ["🔸", "🔸", "🔸", "🔸", "🔸", "🔸", "🔸", "🔸", "🔸", "🔸", "🏵️"]

    for lvl in range(0, max_level + 1):
        need = 5 * (lvl ** 2) + 50 * lvl + 100
        total += need
        sym = symbols[lvl % len(symbols)]
        lines.append(f"{sym} **Level {lvl} → {lvl+1}:** {need:,} exp *(Tổng: {total:,})*")

    embed.add_field(name="📈 Chi tiết", value="\n".join(lines), inline=False)
    embed.add_field(
        name="💡 Ghi chú",
        value="Cấp càng cao, exp yêu cầu càng nhiều.\nChăm chat & voice để tăng tốc tu luyện! Tại LV 10 LV 20 sẽ mở khóa Role chữ 7 màu Thần Gió",
        inline=False
    )

    await ctx.reply(embed=embed)


# ================== /thongke ==================
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

# ================== /topnhiet ==================
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

# ================== MỐC THƯỞNG CẤP ==================
@bot.command(name="setthuongcap")
@commands.has_permissions(manage_guild=True)
async def cmd_setthuongcap(ctx, level: int, *roles: discord.Role):
    if not roles:
        await ctx.reply("❌ Tag ít nhất 1 role.")
        return
    data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
    g = data["guilds"].setdefault(str(ctx.guild.id), {})
    cur = g.get(str(level))
    if isinstance(cur, int):
        cur = [cur]
    new_list = cur or []
    for r in roles:
        if r.id not in new_list:
            new_list.append(r.id)
    g[str(level)] = new_list
    save_json(LEVEL_REWARD_FILE, data)
    await ctx.reply(f"✅ Khi đạt level {level} sẽ được: {', '.join(r.mention for r in roles)}")

@bot.command(name="xemthuongcap")
async def cmd_xemthuongcap(ctx):
    data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
    g = data["guilds"].get(str(ctx.guild.id), {})
    if not g:
        await ctx.reply("📭 Chưa có mốc thưởng.")
        return
    lines = ["🎁 Mốc thưởng:"]
    for lv, val in sorted(g.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 9999):
        if lv == "weekly_revoke":
            continue
        if isinstance(val, int):
            roles = [ctx.guild.get_role(val)]
        else:
            roles = [ctx.guild.get_role(rid) for rid in val]
        r_txt = ", ".join(r.mention for r in roles if r) or "(role đã xoá)"
        lines.append(f"- Level {lv} → {r_txt}")
    revoke = g.get("weekly_revoke", [])
    if revoke:
        r_objs = [ctx.guild.get_role(rid) for rid in revoke]
        lines.append("\n🧹 Role bị thu hồi thứ 2 14:00:")
        lines.append(", ".join(r.mention for r in r_objs if r))
    await ctx.reply("\n".join(lines))

@bot.command(name="thuhoithuong")
@commands.has_permissions(manage_guild=True)
async def cmd_thuhoithuong(ctx, *roles: discord.Role):
    if not roles:
        await ctx.reply("❌ Tag role để thu hồi.")
        return
    data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
    g = data["guilds"].setdefault(str(ctx.guild.id), {})
    cur = g.get("weekly_revoke", [])
    for r in roles:
        if r.id not in cur:
            cur.append(r.id)
    g["weekly_revoke"] = cur
    save_json(LEVEL_REWARD_FILE, data)
    await ctx.reply("✅ Đã lưu danh sách role sẽ bị thu hồi thứ 2 14:00.")

# ================== /setdiemdanh ==================
@bot.command(name="setdiemdanh")
@commands.has_permissions(manage_guild=True)
async def cmd_setdiemdanh(ctx, *args):
    gid = str(ctx.guild.id)
    data = load_json(TEAMCONF_FILE, {"guilds": {}})
    gconf = data["guilds"].setdefault(gid, {"teams": {}})

    # xem danh sách
    if not args:
        att = load_json(ATTEND_FILE, {"guilds": {}})
        today = today_str_gmt7()
        g_att = att["guilds"].get(gid, {})
        if not gconf["teams"]:
            await ctx.reply("📋 Chưa có team nào được cấu hình.")
            return
        lines = ["📖 Danh sách team:"]
        for rid, conf in gconf["teams"].items():
            role = ctx.guild.get_role(int(rid))
            if not role:
                continue
            day_data = g_att.get(rid, {}).get(today, {})
            checked = len(day_data.get("checked", []))
            total = len(role.members)
            active = "✅" if day_data.get("boost") else "❌"
            lines.append(f"{active} {role.mention} – cần {conf.get('min_count',9)} (hiện tại {checked}/{total})")
        await ctx.reply("\n".join(lines))
        return

    # có args
    if args and args[-1].isdigit():
        min_count = int(args[-1])
        role_args = args[:-1]
    else:
        min_count = 9
        role_args = args

    # xóa 1 team: /setdiemdanh @role 0
    if len(role_args) == 1 and min_count == 0:
        role = await commands.RoleConverter().convert(ctx, role_args[0])
        if str(role.id) in gconf["teams"]:
            del gconf["teams"][str(role.id)]
            save_json(TEAMCONF_FILE, data)
            await ctx.reply(f"🗑️ Đã xóa cấu hình cho {role.mention}")
        else:
            await ctx.reply("⚠️ Team này chưa cài.")
        return

    added = []
    for rtext in role_args:
        try:
            role = await commands.RoleConverter().convert(ctx, rtext)
            gconf["teams"][str(role.id)] = {
                "name": role.name,
                "min_count": min_count,
                "max_tag": 3,
                "channel_id": ctx.channel.id,
                "start_hour": 20,
                "start_minute": 0
            }
            added.append(role.mention)
        except:
            pass
    save_json(TEAMCONF_FILE, data)
    if added:
        await ctx.reply(f"✅ Đã cấu hình điểm danh cho {', '.join(added)} (cần {min_count} người).")
    else:
        await ctx.reply("⚠️ Không tìm thấy role hợp lệ.")

# ================== /diemdanh ==================
@bot.command(name="diemdanh")
async def cmd_diemdanh(ctx):
    if is_weekend_lock():
        await ctx.reply("⛔ Hôm nay nghỉ điểm danh (CN & T2 sáng).")
        return
    member = ctx.author
    gid = str(ctx.guild.id)
    teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
    att = load_json(ATTEND_FILE, {"guilds": {}})
    teams = teamconf["guilds"].get(gid, {}).get("teams", {})
    g_att = att["guilds"].setdefault(gid, {})

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
        await ctx.reply(f"⏰ Team điểm danh từ {conf.get('start_hour',20):02d}:{conf.get('start_minute',0):02d}.")
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
        await ctx.reply("✅ Bạn đã điểm danh.")
        return

    # đánh dấu
    day_data["checked"].append(uid)
    if uid not in day_data["active_members"]:
        day_data["active_members"].append(uid)

    # điểm team + nhiệt
    add_team_score(ctx.guild.id, role_id, today, 1)
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    ensure_user(exp_data, uid)
    add_heat(exp_data["users"][uid], 0.5)
    save_json(EXP_FILE, exp_data)

    g_att[str(role_id)][today] = day_data
    att["guilds"][gid] = g_att
    save_json(ATTEND_FILE, att)

    checked = len(day_data["checked"])
    await ctx.reply(f"✅ Điểm danh thành công cho **{conf.get('name','Team')}** ({checked}/{total_members})")

    # tag người chưa điểm danh
    max_tag = conf.get("max_tag", 3)
    if day_data["tag_count"] < max_tag and role_obj:
        not_checked = [m for m in role_obj.members if str(m.id) not in day_data["checked"]]
        if not_checked:
            ch = ctx.guild.get_channel(conf.get("channel_id")) or ctx.channel
            mention_list = " ".join(m.mention for m in not_checked[:20])
            await ch.send(
                f"📣 **{conf.get('name','Team')}** còn thiếu: {mention_list}\nGõ `/diemdanh` nhé!"
            )
            day_data["tag_count"] += 1
            g_att[str(role_id)][today] = day_data
            att["guilds"][gid] = g_att
            save_json(ATTEND_FILE, att)

    # kiểm tra kích hoạt x2
    need = conf.get("min_count", 9)
    enough_count = checked >= need
    enough_percent = total_members > 0 and checked / total_members >= 0.75
    if not day_data.get("boost", False) and (enough_count or enough_percent):
        day_data["boost"] = True
        g_att[str(role_id)][today] = day_data
        att["guilds"][gid] = g_att
        save_json(ATTEND_FILE, att)
        add_team_score(ctx.guild.id, role_id, today, 5)
        ch = ctx.guild.get_channel(conf.get("channel_id")) or ctx.channel
        await ch.send(f"🎉 Team **{conf.get('name','Team')}** đã đủ người và kích hoạt **X2** hôm nay!")

# ================== /bxhkimlan ==================
@bot.command(name="bxhkimlan")
async def cmd_bxhkimlan(ctx, role: discord.Role=None):
    teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
    att = load_json(ATTEND_FILE, {"guilds": {}})
    teamscore = load_json(TEAMSCORE_FILE, {"guilds": {}})

    gid = str(ctx.guild.id)
    teams_conf = teamconf["guilds"].get(gid, {}).get("teams", {})
    att_guild = att["guilds"].get(gid, {})
    score_guild = teamscore["guilds"].get(gid, {})

    # không tag -> bảng tổng
    if role is None:
        if not teams_conf:
            await ctx.reply("📭 Chưa có team.")
            return
        results = []
        for rid, conf in teams_conf.items():
            r_obj = ctx.guild.get_role(int(rid))
            name = conf.get("name") or (r_obj.name if r_obj else f"Role {rid}")
            role_days = att_guild.get(rid, {})
            days = sorted(role_days.keys(), reverse=True)[:7]
            total_quy = 0
            total_rate = 0
            day_count = 0
            good_days, bad_days = [], []
            for d in days:
                info = role_days[d]
                tot = info.get("total_at_day", 0)
                chk = len(info.get("checked", []))
                boosted = info.get("boost", False)
                total_quy += score_guild.get(rid, {}).get(d, 0)
                if tot > 0:
                    rate = chk / tot
                    total_rate += rate
                    day_count += 1
                    wd = datetime.fromisoformat(d).weekday()
                    thu = ["T2","T3","T4","T5","T6","T7","CN"][wd]
                    if chk == tot:
                        good_days.append(f"{thu} {chk}/{tot}" + (" (x2)" if boosted else ""))
                    else:
                        bad_days.append(f"{thu} {chk}/{tot}")
            avg = (total_rate / day_count * 100) if day_count else 0
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
                description=f"Trang {i//per+1}",
                color=0x2ecc71
            )
            for idx, t in enumerate(chunk, start=i+1):
                good = ", ".join(t["good"]) if t["good"] else "—"
                bad = ", ".join(t["bad"]) if t["bad"] else "—"
                e.add_field(
                    name=f"{idx}. {t['name']}",
                    value=f"Ngày điểm danh: {good}\n"
                          f"Ngày thiếu: {bad}\n"
                          f"Tổng điểm quỹ: **{t['quy']:.1f}** | Tỷ lệ TB: **{t['avg']:.0f}%**",
                    inline=False
                )
            pages.append(e)
        if len(pages) == 1:
            await ctx.reply(embed=pages[0])
        else:
            await ctx.reply(embed=pages[0], view=PageView(ctx, pages))
        return

    # có tag -> chi tiết 1 team
    rid = str(role.id)
    if rid not in teams_conf:
        await ctx.reply("❌ Team này chưa /setdiemdanh.")
        return
    role_days = att_guild.get(rid, {})
    if not role_days:
        await ctx.reply("📭 Team này chưa có dữ liệu.")
        return
    days = sorted(role_days.keys(), reverse=True)[:7]
    lines = [f"📅 BẢNG ĐIỂM DANH TEAM **{role.name}**", f"Từ {days[-1]} → {days[0]}"]
    total_quy = 0
    hit = 0
    count = 0
    for d in days:
        info = role_days[d]
        tot = info.get("total_at_day", 0)
        chk = len(info.get("checked", []))
        boosted = info.get("boost", False)
        total_quy += score_guild.get(rid, {}).get(d, 0)
        wd = datetime.fromisoformat(d).weekday()
        thu = ["Thứ 2","Thứ 3","Thứ 4","Thứ 5","Thứ 6","Thứ 7","CN"][wd]
        if tot == 0:
            lines.append(f"{thu}: ❌ 0/0")
        else:
            count += 1
            if chk == tot:
                hit += 1
                icon = "✅"
            elif chk == 0:
                icon = "❌"
            else:
                icon = "⚠️"
            extra = " (x2)" if boosted else ""
            lines.append(f"{thu}: {icon} {chk}/{tot}{extra}")
    rate = int(hit / count * 100) if count else 0
    lines.append(f"\nTổng điểm quỹ: **{total_quy:.1f}**  |  Tỷ lệ điểm danh TB: **{rate}%**")
    await ctx.reply("\n".join(lines))

# ================== DM NHẮC ĐIỂM DANH ==================
@tasks.loop(minutes=10)
async def auto_diemdanh_dm():
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
            dm_count = di.get("dm_count", 0)
            if dm_count >= 4:
                continue
            dm_sent = set(di.get("dm_sent", []))
            not_checked = [m for m in role.members if str(m.id) not in di.get("checked", [])]
            to_dm = [m for m in not_checked if str(m.id) not in dm_sent]
            sent = 0
            for m in to_dm:
                try:
                    await m.send(f"💛 Team **{role.name}** đang điểm danh, gõ `/diemdanh` nhé.")
                    di.setdefault("dm_sent", []).append(str(m.id))
                    sent += 1
                except:
                    pass
            if sent > 0:
                di["dm_count"] = dm_count + 1
            g_att[rid][today] = di
        att["guilds"][str(guild.id)] = g_att
    save_json(ATTEND_FILE, att)

# ================== RESET TUẦN + THU HỒI ==================
@tasks.loop(minutes=5)
async def auto_weekly_reset():
    now = gmt7_now()
    cfg = load_json(CONFIG_FILE, {"guilds": {}, "exp_locked": False, "last_reset": ""})
    last_reset = cfg.get("last_reset", "")
    today = now.date().isoformat()

    # Chủ nhật 00:00 reset
    if now.weekday() == 6 and now.hour == 0 and last_reset != today:
        exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
        exp_data["prev_week"] = exp_data.get("users", {})
        exp_data["users"] = {}
        save_json(EXP_FILE, exp_data)
        cfg["last_reset"] = today
        cfg["exp_locked"] = True
        save_json(CONFIG_FILE, cfg)
        print("🔁 Reset tuần (CN).")

    # Thứ 2 14:00 mở lại + thu hồi
    if now.weekday() == 0 and now.hour >= 14 and cfg.get("exp_locked", False):
        cfg["exp_locked"] = False
        save_json(CONFIG_FILE, cfg)
        print("🔓 Mở lại exp.")
        level_data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
        for guild in bot.guilds:
            gconf = level_data["guilds"].get(str(guild.id), {})
            revoke = gconf.get("weekly_revoke", [])
            for member in guild.members:
                if member.bot:
                    continue
                for rid in revoke:
                    r = guild.get_role(rid)
                    if r and r in member.roles:
                        try:
                            await member.remove_roles(r, reason="Thu hồi thưởng tuần")
                        except:
                            pass

# ================== BACKUP ==================
def make_backup_zip():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_name = f"backup-{ts}"
    zip_path = os.path.join(BACKUP_DIR, zip_name)
    shutil.make_archive(zip_path, "zip", DATA_DIR)
    return zip_path + ".zip"

def cleanup_old_backups(keep: int = 10):
    files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip")]
    if len(files) <= keep:
        return
    files.sort(reverse=True)
    for f in files[keep:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, f))
        except:
            pass

# --- BACKUP (chỉ chủ bot) ---
@bot.command(name="setkenhbackup")
async def cmd_setkenhbackup(ctx):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Lệnh này chỉ dành cho **chủ bot**.")
        return

    cfg = load_json(BACKUP_CONFIG_FILE, {"guilds": {}, "last_run": ""})
    g = cfg["guilds"].setdefault(str(ctx.guild.id), {})
    g["channel_id"] = ctx.channel.id
    save_json(BACKUP_CONFIG_FILE, cfg)
    await ctx.reply("✅ Kênh này sẽ nhận file backup tự động mỗi ngày.")


@bot.command(name="backup")
async def cmd_backup(ctx):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Lệnh này chỉ dành cho **chủ bot**.")
        return

    zip_path = make_backup_zip()
    cleanup_old_backups()
    await ctx.reply(
        content=f"📦 Sao lưu thủ công lúc {gmt7_now().strftime('%Y-%m-%d %H:%M:%S')}",
        file=discord.File(zip_path)
    )


@tasks.loop(minutes=5)
async def auto_backup_task():
    now = gmt7_now()
    today = now.strftime("%Y-%m-%d")
    cfg = load_json(BACKUP_CONFIG_FILE, {"guilds": {}, "last_run": ""})
    if cfg.get("last_run") == today:
        return
    if not (now.hour == 0 and now.minute >= 30):
        return
    zip_path = make_backup_zip()
    cleanup_old_backups()
    for gid, gdata in cfg["guilds"].items():
        ch_id = gdata.get("channel_id")
        if not ch_id:
            continue
        guild = bot.get_guild(int(gid))
        if not guild:
            continue
        ch = guild.get_channel(int(ch_id))
        if not ch:
            continue
        try:
            await ch.send(
                content=f"📦 Sao lưu tự động ngày **{today}**",
                file=discord.File(zip_path)
            )
        except:
            pass
    cfg["last_run"] = today
    save_json(BACKUP_CONFIG_FILE, cfg)

# ================== LỆNH CHỦ BOT: BUFF LINK ==================
@bot.command(name="setlink")
async def cmd_setlink(ctx, invite_url: str, *roles: discord.Role):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ chủ bot.")
        return
    code = invite_url.strip().split("/")[-1]
    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].setdefault(str(ctx.guild.id), {"buff_enabled": True, "links": {}})
    g["links"][code] = {"role_ids": [r.id for r in roles], "active": True}
    save_json(BUFF_FILE, data)
    await ctx.reply("✅ Đã gán link buff.")

@bot.command(name="xemlink")
async def cmd_xemlink(ctx: commands.Context):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Lệnh này chỉ dành cho **chủ bot**.")
        return

    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].get(str(ctx.guild.id))
    if not g or not g.get("links"):
        await ctx.reply("📭 Máy chủ này **chưa cấu hình link buff** nào.")
        return

    buff_status = "🟢 ĐANG BẬT" if g.get("buff_enabled", True) else "🔴 ĐANG TẮT"

    embed = discord.Embed(
        title="📦 Danh sách link buff đang quản lý",
        description=f"Trạng thái buff hiện tại: **{buff_status}**",
        color=0x00bfff
    )
    embed.set_footer(text=f"Máy chủ: {ctx.guild.name}")

    links = g.get("links", {})
    for code, conf in links.items():
        # nếu bạn chỉ dán code thì cứ hiển thị code
        role_ids = conf.get("role_ids", [])
        role_mentions = []
        for rid in role_ids:
            role_obj = ctx.guild.get_role(int(rid))
            if role_obj:
                role_mentions.append(role_obj.mention)
            else:
                role_mentions.append(f"`{rid}`")

        roles_text = ", ".join(role_mentions) if role_mentions else "—"

        embed.add_field(
            name=f"🔗 {code}",
            value=f"• Cấp role: {roles_text}",
            inline=False
        )

    await ctx.reply(embed=embed)


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
    await ctx.reply("✅ Đã bật buff.")

@bot.command(name="tatbuff")
async def cmd_tatbuff(ctx):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ chủ bot.")
        return
    data = load_json(BUFF_FILE, {"guilds": {}})
    g = data["guilds"].setdefault(str(ctx.guild.id), {"buff_enabled": False, "links": {}})
    g["buff_enabled"] = False
    save_json(BUFF_FILE, data)
    await ctx.reply("✅ Đã tắt buff.")

# ================== on_ready DUY NHẤT ==================
@bot.event
async def on_ready():
    print("✅ Bot online:", bot.user)
    # refresh invites
    for g in bot.guilds:
        try:
            await refresh_invites_for_guild(g)
        except:
            pass

    if not auto_weekly_reset.is_running():
        auto_weekly_reset.start()
    if not auto_diemdanh_dm.is_running():
        auto_diemdanh_dm.start()
    if not auto_backup_task.is_running():
        auto_backup_task.start()
    if not tick_voice_realtime.is_running():
        tick_voice_realtime.start()
    if not patrol_voice_channels.is_running():
        patrol_voice_channels.start()



# ============= TICK VOICE 1 PHÚT REALTIME =============
@tasks.loop(seconds=60)
async def tick_voice_realtime():
    # khóa lịch (CN / sáng T2 / ngoài giờ)
    if is_weekend_lock():
        return

    now = now_utc()
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})

    for guild in bot.guilds:
        gmap = voice_state_map.get(guild.id, {})
        for uid, start_time in list(gmap.items()):
            member = guild.get_member(uid)
            if not member:
                continue

            vs = member.voice
            # vẫn chặn mute/deaf / không còn ở voice
            if (
                not vs
                or not vs.channel
                or vs.self_mute
                or vs.mute
                or vs.self_deaf
                or vs.deaf
            ):
                gmap.pop(uid, None)
                continue

            channel = vs.channel  # dòng này phải thẳng cột với mấy dòng trên

            # 1) chặn kênh thoại bị cấm
            blocked = voice_block_data["guilds"].get(str(guild.id), [])
            if channel.id in blocked:
                continue

            # 2) chặn treo 1 mình (phải >=2 người thật)
            human_members = [m for m in channel.members if not m.bot]
            if len(human_members) < 2:
                continue

            # đủ điều kiện rồi mới cộng
            if (now - start_time).total_seconds() >= 55:
                uid_str = str(uid)
                ensure_user(exp_data, uid_str)
                u = exp_data["users"][uid_str]

                bonus = 1
                if team_boost_today(guild.id, member):
                    bonus *= 2

                # cộng exp thoại
                u["exp_voice"] += bonus
                # ghi lại phút thoại tuần
                u["voice_seconds_week"] += 60

                # dồn để lên nhiệt huyết từ voice: 10p -> +0.2
                u["voice_min_buffer"] = u.get("voice_min_buffer", 0) + 1
                while u["voice_min_buffer"] >= 10:
                    u["heat"] += 0.2
                    u["voice_min_buffer"] -= 10

                # cập nhật lại mốc thời gian
                gmap[uid] = now

                # check thưởng cấp
                total = u["exp_chat"] + u["exp_voice"]
                res = try_grant_level_reward(member, total)
                if asyncio.iscoroutine(res):
                    await res

    save_json(EXP_FILE, exp_data)



@tasks.loop(seconds=60)
async def auto_patrol_voice():
    """
    Mỗi 60s bot sẽ đi qua từng kênh thoại đã cấu hình để 'ngồi cho có mặt'.
    Một guild chỉ join được 1 kênh 1 lúc → nên mình cho nó xoay vòng.
    """
    for guild in bot.guilds:
        gid = str(guild.id)
        patrol_list = voice_patrol_config.get(gid, [])
        if not patrol_list:
            continue

        # nếu bot chưa ở voice -> vào kênh đầu
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            first_channel = guild.get_channel(patrol_list[0])
            if first_channel:
                try:
                    await first_channel.connect()
                except:
                    pass
            continue

        # bot đang ở voice rồi -> thử chuyển sang kênh tiếp theo
        # xác định kênh hiện tại nằm ở vị trí nào trong danh sách
        current_id = vc.channel.id
        if current_id in patrol_list:
            idx = patrol_list.index(current_id)
            next_idx = (idx + 1) % len(patrol_list)
            next_chan = guild.get_channel(patrol_list[next_idx])
            if next_chan and next_chan.id != current_id:
                try:
                    await vc.move_to(next_chan)
                except:
                    pass
        else:
            # đang ở kênh không có trong danh sách -> chuyển về kênh đầu
            first_channel = guild.get_channel(patrol_list[0])
            if first_channel:
                try:
                    await vc.move_to(first_channel)
                except:
                    pass


@bot.command(name="settuantra")
@commands.has_permissions(manage_guild=True)
async def cmd_settuantra(ctx, seconds_per_channel: int = 60, *ids):
    if not ids:
        await ctx.reply("⚙️ Dùng: `/settuantra <số_giây_mỗi_kênh> <id_kênh1> <id_kênh2> ...`")
        return

    gid = str(ctx.guild.id)
    ch_ids = []
    for _id in ids:
        try:
            cid = int(_id)
            ch = ctx.guild.get_channel(cid)
            if ch and isinstance(ch, discord.VoiceChannel):
                ch_ids.append(cid)
        except:
            continue

    if not ch_ids:
        await ctx.reply("⚠️ Không có ID kênh thoại hợp lệ.")
        return

    voice_patrol_data["guilds"][gid] = {
        "channels": ch_ids,
        "interval": seconds_per_channel,
        "pos": 0,
    }
    save_json(VOICE_PATROL_FILE, voice_patrol_data)

    names = ", ".join(f"<#{cid}>" for cid in ch_ids)
    await ctx.reply(f"✅ Đã lưu {len(ch_ids)} kênh tuần tra: {names}\n⏱ Mỗi kênh: `{seconds_per_channel}` giây.")




@bot.command(name="xemtuantra")
@commands.has_permissions(manage_guild=True)
async def cmd_xemtuantra(ctx):
    gid = str(ctx.guild.id)
    conf = voice_patrol_data.get("guilds", {}).get(gid)
    if not conf or not conf.get("channels"):
        await ctx.reply("ℹ️ Hiện chưa cấu hình tuần tra kênh thoại nào.")
        return

    interval = conf.get("interval", 60)
    ch_ids = conf.get("channels", [])

    lines = [f"🛰 **Danh sách kênh đang tuần tra** (mỗi kênh {interval}s):"]
    for i, cid in enumerate(ch_ids, start=1):
        ch = ctx.guild.get_channel(cid)
        if ch:
            lines.append(f"{i}. 🔊 {ch.name} (`{cid}`)")
        else:
            lines.append(f"{i}. ❓ (kênh đã xoá) `{cid}`")

    await ctx.reply("\n".join(lines))


# ================== TUẦN TRA KÊNH THOẠI ==================
VOICE_PATROL_FILE = "voice_patrol.json"
voice_patrol_data = load_json(VOICE_PATROL_FILE, {"guilds": {}})

@tasks.loop(seconds=30)
async def patrol_voice_channels():
    # chạy 30s/lần, mỗi guild đi 1 kênh
    for guild in bot.guilds:
        gid = str(guild.id)
        conf = voice_patrol_data["guilds"].get(gid)
        if not conf:
            continue

        channels = conf.get("channels", [])
        if not channels:
            continue

        interval = conf.get("interval", 60)
        pos = conf.get("pos", 0)

        # chọn kênh tiếp theo
        if pos >= len(channels):
            pos = 0
        ch_id = channels[pos]
        conf["pos"] = pos + 1  # lần sau nhảy kênh khác
        save_json(VOICE_PATROL_FILE, voice_patrol_data)

        ch = guild.get_channel(ch_id)
        if not ch or not isinstance(ch, discord.VoiceChannel):
            continue

        # nếu đã đang ở voice thì bỏ qua
        if guild.voice_client and guild.voice_client.is_connected():
            continue

        try:
            vc = await ch.connect(self_deaf=True)
            # rời sau interval giây
            async def _leave_after(vc, wait):
                await asyncio.sleep(wait)
                if vc.is_connected():
                    await vc.disconnect()

            bot.loop.create_task(_leave_after(vc, interval))
        except Exception as e:
            print(f"[VOICE PATROL] Không join được kênh {ch_id} ở guild {guild.name}: {e}")
            continue



@bot.command(name="tuantra")
@commands.has_permissions(manage_guild=True)
async def cmd_tuantra(ctx, mode: str):
    mode = mode.lower()
    if mode in ["on", "bat", "bật"]:
        if not patrol_voice_channels.is_running():
            patrol_voice_channels.start()
            await ctx.reply("🚀 Đã bật tuần tra kênh thoại.")
        else:
            await ctx.reply("✅ Tuần tra đang bật rồi.")
    elif mode in ["off", "tat", "tắt"]:
        if patrol_voice_channels.is_running():
            patrol_voice_channels.cancel()
            await ctx.reply("🛑 Đã tắt tuần tra.")
        else:
            await ctx.reply("ℹ️ Tuần tra chưa bật.")
    else:
        await ctx.reply("❔ Dùng: `/tuantra on` hoặc `/tuantra off`")

# ================== CẤM THOẠI LÊN EXP  ==================


class CamKenhThoaiView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx  # để check ai bấm

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # chỉ người gọi lệnh mới bấm được
        return interaction.user.id == self.ctx.author.id

    @discord.ui.button(label="➕ Thêm kênh", style=discord.ButtonStyle.green)
    async def add_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📥 Nhập **ID kênh thoại** muốn cấm:", ephemeral=True)

        def check_msg(m: discord.Message):
            return m.author.id == self.ctx.author.id and m.channel.id == self.ctx.channel.id

        try:
            msg = await self.ctx.bot.wait_for("message", timeout=30, check=check_msg)
        except asyncio.TimeoutError:
            await self.ctx.send("⏰ Hết thời gian nhập ID.", delete_after=5)
            return

        try:
            cid = int(msg.content.strip())
        except:
            await self.ctx.send("⚠️ ID không hợp lệ.", delete_after=5)
            return

        gid = str(self.ctx.guild.id)
        g = voice_block_data["guilds"].setdefault(gid, [])
        if cid not in g:
            g.append(cid)
            save_json(VOICE_BLOCK_FILE, voice_block_data)
            await self.ctx.send(f"✅ Đã cấm kênh thoại `<#{cid}>` (ID: `{cid}`) không tính EXP.")
        else:
            await self.ctx.send("ℹ️ Kênh này đã nằm trong danh sách cấm rồi.", delete_after=5)

    @discord.ui.button(label="🗑 Gỡ kênh", style=discord.ButtonStyle.danger)
    async def remove_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📥 Nhập **ID kênh thoại** muốn gỡ cấm:", ephemeral=True)

        def check_msg(m: discord.Message):
            return m.author.id == self.ctx.author.id and m.channel.id == self.ctx.channel.id

        try:
            msg = await self.ctx.bot.wait_for("message", timeout=30, check=check_msg)
        except asyncio.TimeoutError:
            await self.ctx.send("⏰ Hết thời gian nhập ID.", delete_after=5)
            return

        try:
            cid = int(msg.content.strip())
        except:
            await self.ctx.send("⚠️ ID không hợp lệ.", delete_after=5)
            return

        gid = str(self.ctx.guild.id)
        g = voice_block_data["guilds"].setdefault(gid, [])
        if cid in g:
            g.remove(cid)
            save_json(VOICE_BLOCK_FILE, voice_block_data)
            await self.ctx.send(f"✅ Đã gỡ cấm kênh thoại `<#{cid}>`.")
        else:
            await self.ctx.send("ℹ️ Kênh này không nằm trong danh sách cấm.", delete_after=5)

    @discord.ui.button(label="📋 Danh sách", style=discord.ButtonStyle.secondary)
    async def list_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = str(self.ctx.guild.id)
        g = voice_block_data["guilds"].get(gid, [])
        if not g:
            await interaction.response.send_message("✅ Hiện **không có** kênh thoại nào bị cấm.", ephemeral=True)
        else:
            text = "\n".join(f"- <#{cid}> (`{cid}`)" for cid in g)
            await interaction.response.send_message(f"🚫 Kênh thoại đang bị cấm:\n{text}", ephemeral=True)
@bot.command(name="camkenhthoai")
@commands.has_permissions(manage_guild=True)
async def cmd_camkenhthoai(ctx):
    """Mở giao diện chặn kênh thoại không tính EXP"""
    view = CamKenhThoaiView(ctx)
    await ctx.reply("🛡 Quản lý **kênh thoại bị cấm tính EXP**\nChọn thao tác bên dưới:", view=view)



# ================== CHẠY BOT ==================
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Thiếu DISCORD_TOKEN")
    else:
        bot.run(DISCORD_TOKEN)
