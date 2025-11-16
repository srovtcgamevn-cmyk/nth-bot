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

def is_heat_time() -> bool:
    """
    Chỉ cho cộng NHIỆT + QUỸ TEAM trong khung:
    - Thứ 2 đến Thứ 7
    - Từ 20:00 đến 23:59 (GMT+7)
    """
    n = gmt7_now()
    # 6 = Chủ nhật
    if n.weekday() == 6:
        return False
    # trong khoảng 20:00 -> 23:59
    if 20 <= n.hour <= 23:
        return True
    return False

def get_week_range_gmt7(offset_weeks: int = 0):
    """
    Trả về (monday, sunday) theo giờ GMT+7.
    offset_weeks = 0  -> tuần hiện tại
    offset_weeks = -1 -> tuần trước
    """
    today = gmt7_now().date()
    # weekday(): 0 = Thứ 2, ... 6 = CN
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def date_in_range(date_str: str, start_date, end_date) -> bool:
    """
    Kiểm tra 1 ngày dạng 'YYYY-MM-DD' hoặc ISO full có nằm trong [start_date, end_date] không.
    """
    try:
        d = datetime.fromisoformat(date_str).date()
    except Exception:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return False
    return start_date <= d <= end_date




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



# ========================= BỘ TÊN ẢO – BẢN MỚI =========================

BASE_NAMES_WITH_ACCENT = [
    "A Linh", "An Dao", "Ánh Vân", "Bạch Mị", "Băng Chi", "Băng Lạc", "Bích Hương", "Cẩm Vy",
    "Cầm Nguyệt", "Cầm Tịnh", "Chu Tâm", "Dạ Lam", "Dạ Vũ", "Di Ca", "Diên My", "Diệp Ca",
    "Dung Hoa", "Gia Mị", "Gia Nguyệt", "Giang Ca", "Hà Tịnh", "Hạ Tuyền", "Hàn Lạc", "Hàn Tư",
    "Hạnh Mị", "Hiểu Huyên", "Hòa Tâm", "Hoa Liên", "Hoài Ca", "Hương Vũ", "Huyền My",
    "Khuê Ca", "Khánh Tuyết", "Khinh Vân", "Kim Dao", "Kim Lạc", "Kim Vũ", "Lam Tư", "Lam Uyển",
    "Lăng Ca", "Lăng Ngọc", "Lăng Tịnh", "Liên Dao", "Liên Tâm", "Liễu Ca", "Linh Nguyệt",
    "Lộ Tâm", "Ly Dao", "Ly Tuyền", "Mai Ca", "Mai Linh", "Minh Ca", "Minh Uyển", "Mộng Chi",
    "Mộng Dao", "Mộng Hồ", "Mỵ Yên", "Mỵ Tâm", "Mỹ Dao", "Mỹ Hà", "Mỹ Lạc", "Mỹ Uyển",
    "Ngân Dao", "Ngân Lạc", "Ngọc Vy", "Ngọc Dao", "Nguyệt Ca", "Nhã Ca", "Nhã Dao",
    "Nhược Lam", "Nhược Hồ", "Nhược Vân", "Oanh Ngọc", "Phỉ Ca", "Phương Ca", "Phương Hàn",
    "Phù My", "Phù Lam", "Phù Tuyền", "Phụng Chi", "Phụng Lạc", "Quân Dao", "Quân Ngọc",
    "Quế Lam", "Quế Mị", "Quỳnh Dao", "Quỳnh Tuyền", "Sở Vân", "Sở Dao", "Song Hạ",
    "Song My", "Song Tâm", "Tạ Tâm", "Tâm Dao", "Tâm Hà", "Tầm Hàn", "Thanh Dao", "Thanh Lam",
    "Thi Ca", "Thi Nhược", "Thi Tâm", "Thi Yên", "Thiều My", "Thủy Dao", "Thủy Ngân",
    "Tiểu Dao", "Tiểu Tư", "Tiểu Vũ", "Tiểu Nhược", "Tiêu Hạ", "Tiêu Hàn", "Tịnh Dao",
    "Tịnh Hạ", "Tố Liên", "Tố Dao", "Trà Dao", "Trà Liên", "Trầm Hàn", "Trầm Dao", "Trầm Tư",
    "Trân Lam", "Trân Tuyền", "Triều Dao", "Trúc My", "Tuyết Ca", "Tuyết Lam", "Tuyết Uyển",
    "Tuyền Tâm", "Uyển Dao", "Uyển Lạc", "Uyển Tâm", "Vân Dao", "Vân Liên", "Vân My",
    "Vân Hà", "Vịnh Tuyền", "Vy Dao", "Vy Tịnh", "Yên Dao", "Yên Huyên", "Yểu Dao"
    "Ánh My", "Ánh Dao", "Ánh Hạ", "Ánh Tuyền", "An Huyên", "An Liên", "An Tịnh",
    "Bạch Dao", "Bạch Yên", "Bạch Tuyền", "Băng My", "Băng Tư", "Băng Nguyệt",
    "Bích Tuyền", "Bích Chi", "Bích Uyển", "Bích Tâm", "Cẩm Dao", "Cẩm Linh",
    "Cẩm Tư", "Cẩm My", "Cầm Hạ", "Cầm Tâm", "Cầm Yên", "Chu Lam", "Chu Tuyền",
    "Dạ Uyển", "Dạ Dao", "Dạ Chi", "Dạ Huyên", "Dạ My", "Dạ Tâm", "Dạ Hồ",
    "Diệu Lam", "Diệu My", "Diệu Tư", "Diệu Nhược", "Dương Ca", "Dương Hà",
    "Dương Linh", "Dung Tâm", "Dung Lam", "Dung Nguyệt", "Dung Tịnh",
    "Gia Lam", "Gia Huyên", "Gia Tâm", "Gia Nhược", "Giang Dao", "Giang Linh",
    "Giang Tuyền", "Giang My", "Giang Tư", "Hà Dao", "Hà Yên", "Hà My", "Hà Lạc",
    "Hạ Yên", "Hạ My", "Hạ Chi", "Hạ Lam", "Hàn My", "Hàn Dao", "Hàn Huyên",
    "Hàn Khê", "Hàn Uyển", "Hàn Linh", "Hiểu Dao", "Hiểu My", "Hiểu Tuyền",
    "Hiểu Hà", "Hiểu Uyển", "Hiểu Liên", "Hoa Dao", "Hoa My", "Hoa Tịnh",
    "Hoa Huyên", "Hoa Uyển", "Hoa Yên", "Hòa Liên", "Hòa Uyển", "Hòa Tịnh",
    "Hoài Dao", "Hoài Lam", "Hoài Yên", "Hoài Tư", "Hương Chi", "Hương Dao",
    "Hương Lam", "Hương Ngọc", "Hương Tư", "Huyền Dao", "Huyền Tư", "Huyền Hà",
    "Huyền Uyển", "Huyền Liên", "Kha Dao", "Kha My", "Kha Tuyền", "Kha Uyển",
    "Khuê Linh", "Khuê Tuyền", "Khuê My", "Khánh Ca", "Khánh Huyên",
    "Khánh Tuyền", "Khánh Dao", "Khinh Hà", "Khinh Chi", "Kim My", "Kim Tiên",
    "Kim Huyên", "Kim Nguyệt", "Kim Ly", "Lam Dao", "Lam Liên", "Lam Chi",
    "Lam Huyên", "Lam Tịnh", "Lam My", "Lan Uyển", "Lan Tư", "Lan Ca",
    "Lan My", "Lan Tuyền", "Lăng Dao", "Lăng Liên", "Lăng Yên", "Lăng Uyển",
    "Linh Hạ", "Linh Tư", "Linh Chi", "Linh Huyên", "Linh Liên", "Linh Tịnh",
    "Linh Hồ", "Lộ Uyển", "Lộ My", "Ly Tâm", "Ly Uyển", "Ly Chi", "Ly Huyên",
    "Mai Dao", "Mai Uyển", "Mai Tuyền", "Mai My", "Mai Chi", "Mẫn Dao",
    "Mẫn Hà", "Mẫn Uyển", "Mẫn Tư", "Mẫn Lam", "Mẫn Chi", "Mộng Tâm",
    "Mộng Tuyền", "Mộng Uyển", "Mộng Lam", "Mộng Yên", "Mỵ Lam", "Mỵ Tuyền",
    "Mỹ Tâm", "Mỹ Tuyền", "Mỹ Liên", "Mỹ Chi", "Mỹ Huyên", "Mỹ Uyển", "Ngân Ca",
    "Ngân Linh", "Ngân Uyển", "Ngân Tư", "Ngân Chi", "Ngân Nguyệt", "Ngọc Chi",
    "Ngọc Liên", "Ngọc Huyên", "Ngọc My", "Ngọc Tư", "Nguyệt Dao", "Nguyệt My",
    "Nguyệt Hạ", "Nguyệt Uyển", "Nguyệt Liên", "Nhạn Dao", "Nhạn My", "Nhạn Chi",
    "Nhã Lam", "Nhã Tuyền", "Nhã Uyển", "Nhã Chi", "Nhược Tâm", "Nhược Dao",
    "Nhược Huyên", "Nhược Tuyền", "Nhược Ca", "Oanh Dao", "Oanh Lam", "Oanh Tịnh",
    "Oanh Tuyền", "Phỉ Lam", "Phỉ Tuyền", "Phỉ Tâm", "Phỉ Uyển", "Phương My",
    "Phương Tư", "Phương Tuyền", "Phương Uyển", "Phương Chi", "Phù Chi",
    "Phù Uyển", "Phù Tuyền", "Phù Ca", "Phụng Yên", "Phụng Dao", "Phụng Uyển",
    "Quân Yên", "Quân Tư", "Quân Tuyền", "Quân Uyển", "Quế Dao", "Quế My",
    "Quế Tịnh", "Quế Uyển", "Quỳnh Ca", "Quỳnh Tịnh", "Quỳnh Uyển", "Quỳnh Lam",
    "Sở Chi", "Sở Tâm", "Sở Huyên", "Sở Uyển", "Song Dao", "Song Tịnh", "Song Uyển",
    "Tạ Chi", "Tạ Hà", "Tạ Uyển", "Tạ Linh", "Tạ Dao", "Tâm Uyển", "Tâm Linh",
    "Tâm Liên", "Tâm Tịnh", "Tầm Tuyền", "Tầm Uyển", "Thanh Huyên", "Thanh Uyển",
    "Thanh Chi", "Thanh Yên", "Thi Dao", "Thi Uyển", "Thi Chi", "Thi Lam",
    "Thiên Dao", "Thiên Tư", "Thiên Uyển", "Thiều Dao", "Thiều Uyển", "Thục Dao",
    "Thục Liên", "Thục My", "Thục Huyên", "Thủy Lam", "Thủy Yên", "Thủy Huyên",
    "Thủy Liên", "Tiểu Lam", "Tiểu Uyển", "Tiểu Tâm", "Tiểu Hồ", "Tiêu Dao",
    "Tiêu Lam", "Tiêu Uyển", "Tiêu Tịnh", "Tịnh Liên", "Tịnh Lam", "Tịnh Uyển",
    "Tố Uyển", "Tố My", "Tố Tịnh", "Tố Hà", "Trà Uyển", "Trà Tịnh", "Trà Chi",
    "Trà Liên", "Trầm Liên", "Trầm Hà", "Trầm Uyển", "Trầm Chi", "Trân Dao",
    "Trân Liên", "Trân Huyên", "Triều My", "Triều Tịnh", "Triều Uyển", "Triều Hà",
    "Trúc Dao", "Trúc Tuyền", "Trúc Uyển", "Trúc Lam", "Tuyết Dao", "Tuyết Tâm",
    "Tuyết Uyển", "Tuyết Tịnh", "Tuyền Dao", "Tuyền Hà", "Tuyền Chi", "Uyển Hà",
    "Uyển Ngọc", "Uyển Linh", "Uyển Tuyền", "Vân Tuyền", "Vân Chi", "Vân Uyển",
    "Vân Huyên", "Vân Tịnh", "Vịnh Dao", "Vịnh Liên", "Vịnh Uyển", "Vy Lam",
    "Vy Chi", "Vy Uyển", "Vy Tuyền", "Yên Tuyền", "Yên Uyển", "Yên Chi", "Yểu Lam",
    "Yểu Tuyền", "Yểu Uyển", "Yểu Chi",
]

BASE_NAMES_NO_ACCENT = [
    "a linh", "an dao", "anh van", "bach mi", "bang chi", "bang lac", "bich huong", "cam vy",
    "cam nguyet", "cam tinh", "chu tam", "da lam", "da vu", "di ca", "dien my", "diep ca",
    "dung hoa", "gia mi", "gia nguyet", "giang ca", "ha tinh", "ha tuyen", "han lac", "han tu",
    "hanh mi", "hieu huyen", "hoa tam", "hoa lien", "hoai ca", "huong vu", "huyen my",
    "khue ca", "khanh tuyet", "khinh van", "kim dao", "kim lac", "kim vu", "lam tu", "lam uyen",
    "lang ca", "lang ngoc", "lang tinh", "lien dao", "lien tam", "lieu ca", "linh nguyet",
    "lo tam", "ly dao", "ly tuyen", "mai ca", "mai linh", "minh ca", "minh uyen", "mong chi",
    "mong dao", "mong ho", "my yen", "my tam", "my dao", "my ha", "my lac", "my uyen",
    "ngan dao", "ngan lac", "ngoc vy", "ngoc dao", "nguyet ca", "nha ca", "nha dao",
    "nhuoc lam", "nhuoc ho", "nhuoc van", "oanh ngoc", "phi ca", "phuong ca", "phuong han",
    "phu my", "phu lam", "phu tuyen", "phung chi", "phung lac", "quan dao", "quan ngoc",
    "que lam", "que mi", "quynh dao", "quynh tuyen", "so van", "so dao", "song ha",
    "song my", "song tam", "ta tam", "tam dao", "tam ha", "tam han", "thanh dao", "thanh lam",
    "thi ca", "thi nhuoc", "thi tam", "thi yen", "thieu my", "thuy dao", "thuy ngan",
    "tieu dao", "tieu tu", "tieu vu", "tieu nhuoc", "tieu ha", "tieu han", "tinh dao",
    "tinh ha", "to lien", "to dao", "tra dao", "tra lien", "tram han", "tram dao", "tram tu",
    "tran lam", "tran tuyen", "trieu dao", "truc my", "tuyet ca", "tuyet lam", "tuyet uyen",
    "tuyen tam", "uyen dao", "uyen lac", "uyen tam", "van dao", "van lien", "van my",
    "van ha", "vinh tuyen", "vy dao", "vy tinh", "yen dao", "yen huyen", "yeu dao"
]

SUFFIX_TOKENS = [
    "kiemhaosu", "kiepthien", "phongtuyet", "huyentam", "nguyettam", "hothien", "tuyetson",
    "linhphach", "huyenlinh", "tuyetha", "tuyethoa", "nguyethan", "bangphong", "bangvu",
    "thachson", "vuutinh", "nguyenvu", "daogia", "tuchantinh", "thankiem", "hoangtuong",
    "thienmon", "vantam", "hatam", "truonglam", "bachtuyet", "thanhthien", "lamnguyet",
    "lamvu", "haolin", "thienhaisu", "nguyenthan", "haivu", "kihon", "phapthan", "hoanguyet",
    "trungquan", "tuyenca", "tinhkhiet", "khaitam", "linhthu", "huyenlam", "nguyetphong",
    "sontinh", "vantinh", "tuyenlam", "bangtich", "kimtuyet", "kimniem", "vuongtuyet",
    "quyetson", "tongthien", "aothien", "vuvien", "phongam", "phachlam", "lienhoan",
    "hoahuyen", "tuyetlinh", "bangchien", "nganhon", "nganhuyet", "thonglinh", "tichvan",
    "thachphach", "longtam", "ngochan", "nguyethoa", "nguyentich", "cuutinh", "cuuam",
    "thientu", "thienha", "bachvan", "kinhphan", "haosang", "uytinh", "huylam", "cutinh",
    "linhma", "camlinh", "kimha", "daolong", "tuyetphu", "nguyetpha", "hanguyen", "huytam",
    "sonchi", "phachvu", "congly", "tanhuyen"
]

DECOR_TOKENS = [
    "✥", "✺", "✹", "✵", "✴", "✷", "✲", "❂", "❉", "❇", "❈", "✣", "✢", "✤", "✬", "✫",
    "✧彡", "✥彡", "✶彡", "✸", "✹彡", "❂彡", "❃", "❃彡", "☄️彡",
    "☊", "☋", "☌", "☍", "⟁", "⧉", "⧚", "⧖", "✦✦", "✦✵", "✥✦", "✪✧",
    "⭑", "⭒", "⭓", "⭘", "⭙", "⨳", "⨴", "⨺", "⩘", "⩚"
]

POPULAR_NUMBERS = [
    "1123", "1712", "2012", "2102", "2709", "1507", "1606", "1208", "2412", "2607",
    "3030", "5050", "9090", "7070", "8080",
    "4488", "7887", "8778", "1221", "5775",
    "0812", "1210", "1510", "1910", "2711",
    "1411", "2211", "3110", "2303", "0407",
    "006", "008", "010", "118", "228", "338", "448", "558", "668", "778", "887"
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



# ================== KHU VỰC LỆNH CHỦ BOT ==================
# ================== KHU VỰC LỆNH CHỦ BOT ==================
# ================== KHU VỰC LỆNH CHỦ BOT ==================

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

    # 1) refresh lại invite cho từng guild
    for g in bot.guilds:
        try:
            await refresh_invites_for_guild(g)
        except:
            pass

    # 2) QUÉT người đang ở voice lúc bot vừa bật,
    #    để tick_voice_realtime có dữ liệu ngay
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            # lấy tất cả member đang ở kênh này
            humans = [m for m in vc.members if not m.bot]
            if len(humans) < 2:
                # yêu cầu >=2 người thật mới tính thoại
                continue
            for m in humans:
                vs = m.voice
                if not vs:
                    continue
                # bỏ mute/deaf
                if vs.self_mute or vs.mute or vs.self_deaf or vs.deaf:
                    continue
                # nhét vào map
                voice_state_map.setdefault(guild.id, {})[m.id] = now_utc()

    # 3) bật các task nền
    if not auto_weekly_reset.is_running():
        auto_weekly_reset.start()
    if not auto_diemdanh_dm.is_running():
        auto_diemdanh_dm.start()
    if not auto_backup_task.is_running():
        auto_backup_task.start()
    if not tick_voice_realtime.is_running():
        tick_voice_realtime.start()
    if not heat_decay_loop.is_running():
        heat_decay_loop.start()



    # task tuần tra chỉ start nếu bạn có định nghĩa patrol_voice_channels
    try:
        if not patrol_voice_channels.is_running():
            patrol_voice_channels.start()
    except NameError:
        # nếu bạn đang tạm tắt tính năng tuần tra thì bỏ qua
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

# ================== KHU VỰC LỆNH CHỦ BOT ==================
# ================== KHU VỰC LỆNH CHỦ BOT ==================
# ================== KHU VỰC LỆNH CHỦ BOT ==================


# ================== KHU VỰC LỆNH ADMIN ==================
# ================== KHU VỰC LỆNH ADMIN ==================
# ================== KHU VỰC LỆNH ADMIN ==================

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



# ================== KHU VỰC LỆNH ADMIN ==================
# ================== KHU VỰC LỆNH ADMIN ==================
# ================== KHU VỰC LỆNH ADMIN ==================



# ================== KHU VỰC BXH KIM LAN + TOP NHIỆT  ==================
# ================== KHU VỰC BXH KIM LAN + TOP NHIỆT  ==================
# ================== KHU VỰC BXH KIM LAN + TOP NHIỆT  ==================

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
        e = discord.Embed(title="📑 THỐNG KÊ HOẠT ĐỘNG", description=f"Trang {i//per + 1}", color=0x3498DB)
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
        await ctx.reply("📭 Dùng lệnh `/topnhiet tuantruoc` để xem dữ liệu tuần trước.")
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



# ================== /bxhkimlan ==================
# ================== /bxhkimlan ==================

class BXHKimLanView(discord.ui.View):
    def __init__(self, ctx, guild, teamconf, att, score_data):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild = guild
        self.teamconf = teamconf
        self.att = att
        self.score_data = score_data
        self.current_mode = "tuan"  # "tuan" hoặc "tuantruoc"

    def build_week_embed(self, mode: str, filter_role: int = None) -> discord.Embed:
        gid = str(self.guild.id)

        # chọn tuần
        mode = mode.lower()
        if mode == "tuantruoc":
            week_start, week_end = get_week_range_gmt7(offset_weeks=-1)
            title_suffix = "TUẦN TRƯỚC"
            week_emoji = "📘"
            color = 0x95A5A6  # xám
        else:
            week_start, week_end = get_week_range_gmt7(offset_weeks=0)
            title_suffix = "TUẦN NÀY"
            week_emoji = "📗"
            color = 0x2ECC71  # xanh lá

        guild_conf = self.teamconf["guilds"].get(gid, {})
        teams = guild_conf.get("teams", {})

        if not teams:
            return discord.Embed(
                title="📊 BẢNG ĐIỂM DANH TEAM KIM LAN",
                description="📭 Chưa có team nào được cấu hình điểm danh.",
                color=color
            )

        g_att = self.att["guilds"].get(gid, {})
        g_score = self.score_data["guilds"].get(gid, {})

        rows = []

        def fmt_day_label(d):
            thu = d.weekday()  # 0 = T2
            thu_map = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
            return f"{thu_map[thu]} {d.day:02d}/{d.month:02d}"

        # duyệt từng team
        for rid_str, conf in teams.items():
            role_id = int(rid_str)
            # nếu lọc 1 role thì bỏ hết role khác
            if filter_role is not None and role_id != filter_role:
                continue

            role = self.guild.get_role(role_id)
            if not role:
                continue

            team_att = g_att.get(rid_str, {})
            team_score_by_day = g_score.get(rid_str, {})

            days_ok = []
            days_miss = []
            total_score = 0.0

            cur = week_start
            while cur <= week_end:
                ds = cur.isoformat()
                day_rec = team_att.get(ds)
                day_score = team_score_by_day.get(ds, 0)

                try:
                    total_score += float(day_score)
                except Exception:
                    pass

                if day_rec:
                    checked = len(day_rec.get("checked", []))
                    total = day_rec.get("total_at_day", 0)
                    boost = day_rec.get("boost", False)
                    if checked > 0:
                        days_ok.append((cur, checked, total, boost))
                    else:
                        if total > 0:
                            days_miss.append((cur, checked, total, boost))
                cur += timedelta(days=1)

            # tính % điểm danh TB theo ngày có total_at_day > 0
            sum_rate = 0.0
            cnt_rate = 0
            for d, checked, total, _ in days_ok + days_miss:
                if total > 0:
                    sum_rate += checked / total
                    cnt_rate += 1
            avg_rate = (sum_rate / cnt_rate * 100) if cnt_rate else 0.0

            rows.append({
                "role": role,
                "conf": conf,
                "total_score": round(total_score, 1),
                "avg_rate": round(avg_rate),
                "days_ok": days_ok,
                "days_miss": days_miss,
            })

        if not rows:
            desc = "📭 Không tìm thấy dữ liệu điểm danh cho tuần đã chọn."
            if filter_role is not None:
                desc = "📭 Không tìm thấy dữ liệu điểm danh cho team này trong tuần đã chọn."
            return discord.Embed(
                title="📊 BẢNG ĐIỂM DANH TEAM KIM LAN",
                description=desc,
                color=color
            )

        # sort theo tổng điểm quỹ giảm dần
        rows.sort(key=lambda r: r["total_score"], reverse=True)

        # ===== PHẦN HIỂN THỊ =====
        lines = []
        if filter_role is None:
            title = "📊 BẢNG ĐIỂM DANH CÁC TEAM KIM LAN (7 ngày)"
        else:
            title = "📊 BẢNG ĐIỂM DANH TEAM KIM LAN (7 ngày)"

        lines.append(f"{week_emoji} **{title_suffix}: {week_start.strftime('%d/%m')} → {week_end.strftime('%d/%m')}**")
        if filter_role is None:
            lines.append("Dùng nút bên dưới để chuyển **tuần này / tuần trước**.")
        lines.append("")

        rank = 1
        for r in rows:
            role = r["role"]
            total_score = r["total_score"]
            avg_rate = r["avg_rate"]

            # tiêu đề từng team: rank + tên
            lines.append(f"**{rank}. {role.name}**")

            # 🔥 Ngày điểm nhận x2 (thay cho 'Ngày điểm danh')
            if r["days_ok"]:
                dd = ", ".join(
                    f"{fmt_day_label(d)} {c}/{t}{' (x2)' if boost else ''}"
                    for (d, c, t, boost) in r["days_ok"]
                )
                lines.append(f"🔥 Ngày điểm nhận x2: {dd}")
            else:
                lines.append("🔥 Ngày điểm nhận x2: —")

            # ngày thiếu
            if r["days_miss"]:
                miss = ", ".join(
                    f"{fmt_day_label(d)} {c}/{t}"
                    for (d, c, t, _) in r["days_miss"]
                )
                lines.append(f"Ngày thiếu: {miss}")
            else:
                lines.append("Ngày thiếu: —")

            # tổng điểm quỹ + tỷ lệ
            lines.append(f"Tổng điểm quỹ: **{total_score}** | Tỷ lệ TB: **{avg_rate}%**")
            lines.append("")  # dòng trống giữa các team
            rank += 1

        desc = "\n".join(lines)
        if len(desc) > 4000:
            desc = desc[:4000] + "\n...(rút gọn bớt vì quá dài)"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color
        )
        return embed

    async def _ensure_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "⛔ Chỉ người dùng lệnh mới bấm được nút này.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Tuần này", style=discord.ButtonStyle.primary)
    async def btn_tuan_nay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_author(interaction):
            return
        self.current_mode = "tuan"
        embed = self.build_week_embed("tuan")
        await interaction.response.edit_message(content=None, embed=embed, view=self)

    @discord.ui.button(label="Tuần trước", style=discord.ButtonStyle.secondary)
    async def btn_tuan_truoc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_author(interaction):
            return
        self.current_mode = "tuantruoc"
        embed = self.build_week_embed("tuantruoc")
        await interaction.response.edit_message(content=None, embed=embed, view=self)


@bot.command(name="bxhkimlan")
async def cmd_bxhkimlan(ctx, role: discord.Role = None):
    """
    /bxhkimlan
    - Không tag: hiện BXH tất cả team, tuần NÀY (có nút xem TUẦN TRƯỚC)
    - /bxhkimlan @role: chỉ xem BXH của 1 team riêng (không cần nút)
    """
    teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
    att = load_json(ATTEND_FILE, {"guilds": {}})
    score_data = load_json(TEAMSCORE_FILE, {"guilds": {}})

    view = BXHKimLanView(ctx, ctx.guild, teamconf, att, score_data)

    # nếu có @role → chỉ show đúng team đó, không kèm view
    if role is not None:
        embed = view.build_week_embed("tuan", filter_role=role.id)
        await ctx.reply(embed=embed)
        return

    # mặc định: show toàn bộ + có nút tuần này / tuần trước
    embed = view.build_week_embed("tuan")
    await ctx.reply(embed=embed, view=view)


# ================== /bxhkimlan ==================


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


# ================== /hoso (tiêu đề chỉ tên, tag ở cuối, team không tag) ==================
class HoSoView(discord.ui.View):
    def __init__(self, ctx, member):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.member = member
        self.current_mode = "tuan"   # tuan / tuantruoc

    async def _ensure_author(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "⛔ Bạn không thể sử dụng nút này.",
                ephemeral=True
            )
            return False
        return True

    def build_embed(self, member, mode="tuan"):
        exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})

        # Chọn data theo mode
        if mode == "tuantruoc":
            u = exp_data.get("prev_week", {}).get(str(member.id), {})
            week_title = "📘 **Tuần Trước**"
        else:
            u = exp_data.get("users", {}).get(str(member.id), {})
            week_title = "📗 **Tuần Này**"

        # Lấy dữ liệu (KHÔNG còn chặn ngày nghỉ)
        total = u.get("exp_chat", 0) + u.get("exp_voice", 0)
        level, to_next, spent = calc_level_from_total_exp(total)
        exp_in_level = total - spent
        need = exp_in_level + to_next
        voice_min = math.floor(u.get("voice_seconds_week", 0) / 60)
        heat = u.get("heat", 0.0)

        # team Kim Lan
        team_name = "Chưa thuộc team điểm danh"
        teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
        g_teams = teamconf["guilds"].get(str(self.ctx.guild.id), {}).get("teams", {})
        for rid, conf in g_teams.items():
            role = self.ctx.guild.get_role(int(rid))
            if role and role in member.roles:
                tname = conf.get("name") or role.name
                team_name = tname
                break

        # buff điểm danh
        try:
            has_boost = team_boost_today(self.ctx.guild.id, member)
        except Exception:
            has_boost = False

        # thanh exp
        bar_len = 14
        filled = int(bar_len * (exp_in_level / need)) if need > 0 else bar_len
        bar = "█" * filled + "░" * (bar_len - filled)

        # đổi màu embed theo tuần
        if mode == "tuan":
            embed_color = 0xF1C40F   # vàng – tuần này
        else:
            embed_color = 0xBDC3C7   # xám – tuần trước

        embed = discord.Embed(
            title="📜 **Hồ Sơ Tu Luyện**",
            color=embed_color
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        # phần mô tả
        desc = (
            f"**{member.display_name}**\n\n"
            "Theo dõi exp, thoại, nhiệt huyết và trạng thái điểm danh team.\n\n"
            "📈 **Cấp Độ**\n"
            f"• Level: **{level}**\n"
            f"• Tiến độ: **{exp_in_level}/{need} exp**\n"
            f"`{bar}`\n\n"
            f"{week_title}\n"
            f"• Chat: **{u.get('exp_chat', 0)} exp**\n"
            f"• Thoại: **{u.get('exp_voice', 0)} exp** — {voice_min} phút\n"
            f"• Nhiệt huyết: **{heat:.1f}/10**\n\n"
            "👥 **Team Kim Lan**\n"
            f"{team_name}\n\n"
            "🔥 **Buff điểm danh**\n"
            f"{'Đang nhận **x2 exp hôm nay**' if has_boost else 'Không hoạt động'}\n\n"
            f"👤 **Người xem:** {member.mention}"
        )

        embed.description = desc
        return embed

    @discord.ui.button(label="Tuần này", style=discord.ButtonStyle.primary)
    async def btn_tuan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_author(interaction):
            return
        self.current_mode = "tuan"
        embed = self.build_embed(self.member, "tuan")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Tuần trước", style=discord.ButtonStyle.secondary)
    async def btn_truoc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_author(interaction):
            return
        self.current_mode = "tuantruoc"
        embed = self.build_embed(self.member, "tuantruoc")
        await interaction.response.edit_message(embed=embed, view=self)


@bot.command(name="hoso")
async def cmd_hoso(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    view = HoSoView(ctx, member)
    embed = view.build_embed(member, "tuan")
    await ctx.reply(embed=embed, view=view)



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


# ================== KHU VỰC BXH KIM LAN + TOP NHIỆT  ==================
# ================== KHU VỰC BXH KIM LAN + TOP NHIỆT  ==================
# ================== KHU VỰC BXH KIM LAN + TOP NHIỆT  ==================



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


# ================== /godiemdanh ==================
@bot.command(name="godiemdanh")
@commands.has_permissions(manage_guild=True)  # Chỉ Admin / người có quyền Manage Server mới dùng
async def cmd_godiemdanh(ctx: commands.Context, role: discord.Role):
    """
    Gỡ 1 team (role) ra khỏi danh sách điểm danh.
    - Chỉ người có quyền Manage Guild mới được dùng.
    - Xoá team khỏi cấu hình để không còn tính điểm danh cho tuần tới.
    - Dữ liệu điểm danh cũ vẫn được giữ lại để xem BXH tuần trước.
    """
    gid = str(ctx.guild.id)

    # Tải cấu hình team điểm danh
    data = load_json(TEAMCONF_FILE, {"guilds": {}})
    gconf = data["guilds"].setdefault(gid, {})
    teams = gconf.setdefault("teams", {})

    rid = str(role.id)

    # Nếu role chưa được cấu hình trong hệ thống điểm danh
    if rid not in teams:
        await ctx.reply(f"❌ Role **{role.name}** chưa được cấu hình điểm danh.")
        return

    # Xoá role khỏi danh sách team đang điểm danh
    del teams[rid]
    data["guilds"][gid] = gconf
    save_json(TEAMCONF_FILE, data)

    # Thông báo kết quả
    await ctx.reply(
        f"🗑️ Đã gỡ team **{role.name}** khỏi danh sách điểm danh.\n"
        f"📌 Dữ liệu điểm danh cũ vẫn được giữ để xem BXH tuần trước."
    )



# ================== KHU VỰC TOP NHIỆT + QUỸ TEAM  ==================
# ================== KHU VỰC TOP NHIỆT + QUỸ TEAM  ==================
# ================== KHU VỰC TOP NHIỆT + QUỸ TEAM  ==================
# ================== KHU VỰC TOP NHIỆT + QUỸ TEAM  ==================

# --------- KHUNG GIỜ SINH NHIỆT + ĐIỂM TEAM (20:00–23:59, T2–T7) ----------
def is_heat_time() -> bool:
    """
    Chỉ cho cộng NHIỆT + QUỸ TEAM trong khung:
    - Thứ 2 đến Thứ 7
    - Từ 20:00 đến 23:59 (GMT+7)
    """
    n = gmt7_now()
    # 6 = Chủ nhật
    if n.weekday() == 6:
        return False
    if 20 <= n.hour <= 23:
        return True
    return False


# ================== /diemdanh ==================
@bot.command(name="diemdanh")
async def cmd_diemdanh(ctx):
    # CN & sáng T2 nghỉ
    if is_weekend_lock():
        await ctx.reply("⛔️ Hôm nay nghỉ điểm danh (CN & sáng T2).")
        return

    # CHỈ cho điểm danh từ 20:00 → 23:59
    now = gmt7_now()
    if not (20 <= now.hour <= 23):
        await ctx.reply("⏰ Điểm danh chỉ hợp lệ từ **20:00 đến 23:59**.")
        return

    member = ctx.author
    gid = str(ctx.guild.id)

    # --- Load dữ liệu ---
    teamconf = load_json(TEAMCONF_FILE, {"guilds": {}})
    att = load_json(ATTEND_FILE, {"guilds": {}})

    teams = teamconf["guilds"].get(gid, {}).get("teams", {})
    g_att = att["guilds"].setdefault(gid, {})

    # --- Tìm team mà member đang ở ---
    role_id = None
    conf = None
    for rid, c in teams.items():
        role = ctx.guild.get_role(int(rid))
        if role and role in member.roles:
            role_id = int(rid)
            conf = c
            break

    if not conf:
        await ctx.reply("⛔️ Bạn không thuộc team nào đang bật điểm danh.")
        return

    # ---- Setup ngày ----
    today = today_str_gmt7()
    day_data = g_att.setdefault(str(role_id), {}).setdefault(today, {
        "checked": [],
        "dm_sent": [],
        "tag_count": 0,
        "boost": False,
        "total_at_day": 0,
        "active_members": [],
    })

    # ---- Tổng số thành viên team ----
    role_obj = ctx.guild.get_role(role_id)
    total_members = len(role_obj.members) if role_obj else 0
    day_data["total_at_day"] = total_members

    uid = str(member.id)
    if uid in day_data["checked"]:
        await ctx.reply("✅ Bạn đã điểm danh hôm nay.")
        return

    # ---- ĐÁNH DẤU ĐIỂM DANH ----
    day_data["checked"].append(uid)
    if uid not in day_data["active_members"]:
        day_data["active_members"].append(uid)

    # ---- Điểm TEAM: mỗi người +1 ----
    add_team_score(ctx.guild.id, role_id, today, 1)

    # ---- Nhiệt huyết: mạnh nhất +1.0 ----
    exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
    ensure_user(exp_data, uid)
    add_heat(exp_data["users"][uid], 1.0)
    save_json(EXP_FILE, exp_data)

    # ---- LƯU LẠI ----
    g_att[str(role_id)][today] = day_data
    att["guilds"][gid] = g_att
    save_json(ATTEND_FILE, att)

    checked = len(day_data["checked"])
    await ctx.reply(
        f"✅ Điểm danh thành công cho **{conf.get('name','Team')}** "
        f"({checked}/{total_members})"
    )

    # ========================== TAG NGƯỜI CHƯA ĐIỂM DANH ==========================
    announce_channel = ctx.channel
    max_tag = conf.get("max_tag", 3)
    if role_obj and day_data["tag_count"] < max_tag:
        not_checked = [m for m in role_obj.members if str(m.id) not in day_data["checked"]]
        if not_checked:
            mention_list = " ".join(m.mention for m in not_checked[:20])
            await announce_channel.send(
                f"📣 **{conf.get('name','Team')}** còn thiếu: {mention_list}\n"
                f"Gõ `/diemdanh` nhé!"
            )
            day_data["tag_count"] += 1
            g_att[str(role_id)][today] = day_data
            att["guilds"][gid] = g_att
            save_json(ATTEND_FILE, att)

    # ========================== KÍCH HOẠT X2 NẾU ĐỦ NGƯỜI ==========================
    need = conf.get("min_count", 9)
    enough_count = checked >= need
    enough_percent = total_members > 0 and checked / total_members >= 0.75

    if not day_data.get("boost", False) and (enough_count or enough_percent):
        day_data["boost"] = True
        g_att[str(role_id)][today] = day_data
        att["guilds"][gid] = g_att
        save_json(ATTEND_FILE, att)

        # thưởng thêm điểm quỹ khi đủ
        add_team_score(ctx.guild.id, role_id, today, 5)

        await announce_channel.send(
            f"🎉 Team **{conf.get('name','Team')}** đã đủ người và **kích hoạt X2** hôm nay!"
        )


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
            "last_heat_ts": None,
        }
    else:
        u = exp_data["users"][uid]
        u.setdefault("exp_chat", 0)
        u.setdefault("exp_voice", 0)
        u.setdefault("last_msg", None)
        u.setdefault("voice_seconds_week", 0)
        u.setdefault("heat", 0.0)
        u.setdefault("chat_exp_buffer", 0)
        u.setdefault("voice_min_buffer", 0)
        u.setdefault("last_level_announce", 0)
        u.setdefault("last_heat_ts", None)


def add_heat(user_obj: dict, amount: float):
    """Cộng / trừ điểm nhiệt, giới hạn 0–10, có lưu mốc hoạt động cuối."""
    if amount == 0:
        return
    cur = float(user_obj.get("heat", 0.0))
    cur += amount
    if cur < 0:
        cur = 0.0
    if cur > 10.0:
        cur = 10.0
    user_obj["heat"] = round(cur, 3)
    user_obj["last_heat_ts"] = now_utc().isoformat()


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
    # tính level mới
    level, to_next, _ = calc_level_from_total_exp(new_total_exp)

    # xử lý thưởng role
    data = load_json(LEVEL_REWARD_FILE, {"guilds": {}})
    g = data["guilds"].get(str(member.guild.id), {})
    val = g.get(str(level))
    if not val:
        return

    # cho phép 1 cấp nhận nhiều role
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

    # vẫn giữ DM riêng nếu nhận được role
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
        return (
            v.channel
            and not v.self_mute
            and not v.mute
            and not v.self_deaf
            and not v.deaf
        )

    gid = member.guild.id
    voice_state_map.setdefault(gid, {})

    if is_weekend_lock():
        return

    was = open_mic(before)
    now = open_mic(after)

    # bắt đầu mở mic
    if now and not was:
        voice_state_map[gid][member.id] = now_utc()

    # tắt mic / rời kênh
    elif was and not now:
        start = voice_state_map[gid].pop(member.id, None)
        if start:
            secs = (now_utc() - start).total_seconds()
            if secs > 5:
                minutes = int(secs // 60)
                exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
                uid = str(member.id)
                ensure_user(exp_data, uid)
                u = exp_data["users"][uid]

                if minutes > 0:
                    bonus = minutes
                    if team_boost_today(gid, member):
                        bonus *= 2

                    # EXP thoại luôn cộng (nếu không bị weekend lock)
                    u["exp_voice"] += bonus
                    u["voice_seconds_week"] += int(secs)

                    # NHIỆT: chỉ trong khung 20–23:59
                    if is_heat_time():
                        heat_add = minutes * 0.02
                        if team_boost_today(gid, member):
                            heat_add *= 2
                        add_heat(u, heat_add)

                    save_json(EXP_FILE, exp_data)

                    total_now = u["exp_chat"] + u["exp_voice"]
                    try_grant_level_reward(member, total_now)

                    # QUỸ TEAM: chỉ trong khung 20–23:59 và đã điểm danh
                    if is_heat_time():
                        att = load_json(ATTEND_FILE, {"guilds": {}})
                        g_att = att["guilds"].get(str(gid), {})
                        today = today_str_gmt7()
                        for rid, daymap in g_att.items():
                            di = daymap.get(today)
                            if not di:
                                continue
                            if str(member.id) in di.get("active_members", []):
                                team_pts = minutes * 0.05
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
        cfg = load_json(
            CONFIG_FILE,
            {"guilds": {}, "exp_locked": False, "last_reset": ""}
        )
        gconf = cfg["guilds"].get(str(message.guild.id), {})
        exp_chs = gconf.get("exp_channels", [])
        allow = (not exp_chs) or (message.channel.id in exp_chs)

        if allow:
            exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
            uid = str(message.author.id)
            ensure_user(exp_data, uid)
            u = exp_data["users"][uid]

            last = u.get("last_msg")
            # mỗi 60s chat mới cộng
            if (not last) or \
               (now_utc() - datetime.fromisoformat(last)).total_seconds() >= 60:
                add_exp = random.randint(5, 15)

                # nếu team hôm nay đã kích x2 thì nhân
                if team_boost_today(message.guild.id, message.author):
                    add_exp *= 2

                # cộng exp chat
                u["exp_chat"] += add_exp
                u["last_msg"] = now_utc().isoformat()

                # CHAT -> NHIỆT: mỗi 20 exp chat = +0.03 nhiệt, chỉ trong 20–23:59
                u["chat_exp_buffer"] += add_exp
                while u["chat_exp_buffer"] >= 20:
                    u["chat_exp_buffer"] -= 20
                    if is_heat_time():
                        add_heat(u, 0.02)

                # lưu lại trước khi tính level
                save_json(EXP_FILE, exp_data)

                # tổng exp = chat + voice
                total_now = u["exp_chat"] + u["exp_voice"]

                # cấp role thưởng nếu có set
                try_grant_level_reward(message.author, total_now)

                # ------ THÔNG BÁO LÊN LEVEL KHÔNG TAG (CHỈ KHI CHAT) ------
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
                # ----------------------------------------------------------

    # để các lệnh vẫn chạy
    await bot.process_commands(message)

# ================== KHU VỰC TOP NHIỆT + QUỸ TEAM  ==================
# ================== KHU VỰC TOP NHIỆT + QUỸ TEAM  ==================
# ================== KHU VỰC TOP NHIỆT + QUỸ TEAM  ==================
# ================== KHU VỰC TOP NHIỆT + QUỸ TEAM  ==================




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


# ============= TICK VOICE 1 PHÚT REALTIME =============
@tasks.loop(seconds=60)
async def tick_voice_realtime():
    # Khóa lịch (CN / sáng T2 / ngoài giờ theo is_weekend_lock)
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

            # 2) chặn treo 1 mình (phải >= 2 người thật)
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

                # cộng EXP thoại
                u["exp_voice"] += bonus
                # ghi lại phút thoại tuần
                u["voice_seconds_week"] += 60

                # NHIỆT THOẠI: chỉ cộng trong khung 20:00–23:59 (GMT+7)
                if is_heat_time():
                    # 1 phút thoại ~ 0.02 nhiệt, có nhân X2 nếu đang boost
                    heat_gain = 0.05 * bonus
                    add_heat(u, heat_gain)

                # cập nhật lại mốc thời gian
                gmap[uid] = now

                # check thưởng cấp (chỉ role, không tag, không spam)
                total = u["exp_chat"] + u["exp_voice"]
                try:
                    await try_grant_level_reward(member, total)
                except:
                    pass

    # lưu dữ liệu EXP sau mỗi tick
    save_json(EXP_FILE, exp_data)

# ============= GIẢM NHIỆT KHI KHÔNG HOẠT ĐỘNG =============
@tasks.loop(hours=6)
async def heat_decay_loop():
    """
    Mỗi 6 tiếng quét một lần:
    - Nếu user không có hoạt động sinh nhiệt > 12 tiếng -> trừ 0.3 điểm nhiệt huyết.
    """
    try:
        exp_data = load_json(EXP_FILE, {"users": {}, "prev_week": {}})
        changed = False
        now = now_utc()

        for uid, u in exp_data["users"].items():
            last_ts = u.get("last_heat_ts")
            if not last_ts:
                continue
            try:
                last = datetime.fromisoformat(last_ts)
            except:
                continue

            diff_hours = (now - last).total_seconds() / 3600
            if diff_hours >= 12:
                cur = float(u.get("heat", 0.0))
                if cur > 0:
                    cur -= 0.3
                    if cur < 0:
                        cur = 0.0
                    u["heat"] = round(cur, 3)
                    changed = True

        if changed:
            save_json(EXP_FILE, exp_data)
    except Exception as e:
        print("[HEAT_DECAY]", e)







# ================== CHẠY BOT ==================
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Thiếu DISCORD_TOKEN")
    else:
        bot.run(DISCORD_TOKEN)
