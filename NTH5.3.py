# =================================================================================================
# BOT TU TIÊN — NTH4.9 (BT-1727-KIM)
# Phiên bản gốc: của bạn
# Mục tiêu chỉnh sửa: CHỈ SẮP XẾP LẠI BỐ CỤC, KHÔNG XOÁ CODE GỐC
# =================================================================================================
# 📑 MỤC LỤC (PHỤ LỤC)
#   [PL-001] Cấu hình & hạ tầng chung (import, intents, đường dẫn, backup cơ bản)
#   [PL-002] Hệ emoji, hình ảnh, rarity, mô tả loot
#   [PL-003] Khởi tạo bot, on_ready, auto-backup
#   [PL-004] Hệ quản trị kênh (osetbot, view, check kênh)
#   [PL-005] Lệnh chủ bot / quản trị dữ liệu (saoluu, phuchoi, reset, xuatdata,…)
#   [PL-006] Nhiệm vụ cộng đồng + onhanthuong + reaction role
#   [PL-007] Bảng xếp hạng (obxh)
#   [PL-008] Gameplay (omo, kho, bán, trang bị, sinh item…)
#   [PL-999] Cuối file: chạy bot (token)
#
# Chú ý:
# - Khi bạn cần tìm nhanh: chỉ cần tìm ID, ví dụ "PL-006"
# - Tôi giữ lại các comment gốc dài của bạn để khỏi mất thông tin
# =================================================================================================


# =================================================================================================
# [PL-001] CẤU HÌNH & HẠ TẦNG CHUNG
# - import
# - intents
# - cấu hình thư mục dữ liệu (Railway / local)
# - bộ công cụ backup v16
# - hàm load/save/ensure user
# =================================================================================================
import os, io, json, time, random, asyncio, logging, hashlib, tempfile
from glob import glob
from datetime import datetime
import discord
from discord.ext import commands
import aiohttp

logging.getLogger("discord").setLevel(logging.WARNING)

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

# ----------- QUAN TRỌNG CHO RAILWAY VOLUME -------------
# BASE_DATA_DIR: thư mục dữ liệu vĩnh viễn
# - Nếu chạy local: ./data (tự tạo)
# - Nếu chạy Railway: bạn set env DATA_DIR=/data và mount volume vào /data
BASE_DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
)
os.makedirs(BASE_DATA_DIR, exist_ok=True)

# data.json và thư mục backups sẽ nằm trong BASE_DATA_DIR
DATA_FILE = os.path.join(BASE_DATA_DIR, "data.json")

COOLDOWN_OL = 10
STARTING_NP = 1000

# ——— Whitelist từ ‘o…’ không báo lỗi CommandNotFound ———
IGNORE_O_TOKENS = {"ok","oh","ob","oke","okay","ooo","oi"}

# ===== HỆ THỐNG BACKUP v16 =====
BACKUP_DIRS = {
    "startup":        os.path.join(BASE_DATA_DIR, "backups", "startup"),
    "pre_save":       os.path.join(BASE_DATA_DIR, "backups", "pre-save"),
    "manual":         os.path.join(BASE_DATA_DIR, "backups", "manual"),
    "before_restore": os.path.join(BASE_DATA_DIR, "backups", "before-restore"),
    "resetuser":      os.path.join(BASE_DATA_DIR, "backups", "resetuser"),
    "export":         os.path.join(BASE_DATA_DIR, "backups", "export")
}

def _ensure_backup_dirs():
    for p in BACKUP_DIRS.values():
        os.makedirs(p, exist_ok=True)

def _stamp_now():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def snapshot_data_v16(data, tag, subkey):
    _ensure_backup_dirs()
    stamp = _stamp_now()
    fname = f"data.json.v16.{tag}.{stamp}.json"
    dstdir = BACKUP_DIRS.get(subkey, BACKUP_DIRS["manual"])
    os.makedirs(dstdir, exist_ok=True)
    out = os.path.join(dstdir, fname)
    # ghi file backup
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # kèm checksum
    with open(out + ".sha256", "w", encoding="utf-8") as g:
        g.write(_sha256_file(out))
    return out

def list_recent_backups_v16(limit=10):
    _ensure_backup_dirs()
    files = []
    for key, d in BACKUP_DIRS.items():
        for p in glob(os.path.join(d, "data.json.v*.json")):
            files.append((os.path.getmtime(p), key, p))
    files.sort(reverse=True)
    return files[:max(1, min(20, limit))]

def total_backup_stats_v16():
    _ensure_backup_dirs()
    total_files = 0
    total_bytes = 0
    latest = None
    for key, d in BACKUP_DIRS.items():
        for p in glob(os.path.join(d, "data.json.v*.json")):
            total_files += 1
            total_bytes += os.path.getsize(p)
            mt = os.path.getmtime(p)
            if (latest is None) or (mt > latest[0]):
                latest = (mt, p)
    return {
        "files": total_files,
        "bytes": total_bytes,
        "latest": latest[1] if latest else None
    }




# ----------- QUAN TRỌNG CHO RAILWAY VOLUME -------------
# BASE_DATA_DIR: thư mục dữ liệu vĩnh viễn
# - Nếu chạy local: ./data (tự tạo)
# - Nếu chạy Railway: bạn set env DATA_DIR=/data và mount volume vào /data

# Giới hạn số lượng backup thủ công (manual) cần giữ lại
MAX_MANUAL_BACKUPS = 2

def _cleanup_old_backups_limit():
    """
    Giữ lại tối đa MAX_MANUAL_BACKUPS bản backup loại 'manual',
    xóa các bản manual cũ hơn để tránh đầy volume.

    Chỉ dọn thư mục BACKUP_DIRS['manual'].
    Không đụng pre-save / before-restore / startup / resetuser / export.
    """
    manual_dir = BACKUP_DIRS.get("manual")
    if not manual_dir:
        return

    try:
        # Lấy tất cả file .json trong thư mục manual
        pattern = os.path.join(manual_dir, "data.json.v*.json")
        files = glob(pattern)

        # Nếu số file <= giới hạn thì thôi
        if len(files) <= MAX_MANUAL_BACKUPS:
            return

        # Sort giảm dần theo tên file để file mới nhất đứng đầu
        # (tên file có timestamp YYYYMMDD-HHMMSS nên sort tên ~ sort thời gian)
        files_sorted_new_first = sorted(files, reverse=True)

        # Giữ lại N bản mới nhất
        keep = set(files_sorted_new_first[:MAX_MANUAL_BACKUPS])

        # Những file còn lại (cũ hơn) sẽ bị xóa
        to_delete = [f for f in files_sorted_new_first if f not in keep]

        deleted = 0
        for f in to_delete:
            try:
                os.remove(f)
                # Xóa luôn file checksum nếu có
                sha_path = f + ".sha256"
                if os.path.exists(sha_path):
                    os.remove(sha_path)
                deleted += 1
            except Exception:
                pass

        print(f"[AUTO-BACKUP-CLEANUP] Đã xóa {deleted} bản manual cũ, giữ lại {MAX_MANUAL_BACKUPS} bản mới nhất.")

    except Exception as e:
        print(f"[AUTO-BACKUP-CLEANUP] Lỗi dọn backup manual: {e}")


# ===== DỮ LIỆU & TIỆN ÍCH CHUNG =====
SESSION: aiohttp.ClientSession | None = None
IMG_CACHE: dict[str, bytes] = {}

async def get_session() -> aiohttp.ClientSession:
    global SESSION
    if SESSION is None or SESSION.closed:
        connector = aiohttp.TCPConnector(limit=8)
        SESSION = aiohttp.ClientSession(connector=connector)
    return SESSION

async def file_from_url_cached(url: str, filename: str) -> discord.File:
    if url not in IMG_CACHE:
        sess = await get_session()
        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            IMG_CACHE[url] = await resp.read()
    return discord.File(io.BytesIO(IMG_CACHE[url]), filename=filename)

def ensure_data():
    """
    Đảm bảo có file data.json ban đầu.
    """
    if not os.path.exists(DATA_FILE):
        base = {
            "bot_channel": None,
            "active": False,
            "users": {}
        }
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False, indent=2)

def load_data():
    """
    Đọc data.json an toàn, tự thêm các field mặc định nếu thiếu.
    """
    ensure_data()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        data = {"users": {}, "bot_channel": None, "active": False}
    data.setdefault("users", {})
    data.setdefault("bot_channel", None)
    data.setdefault("active", False)
    data.setdefault("guild_settings", {})
    data.setdefault("server_cfg", {})
    data.setdefault("config", {"images_enabled": True})
    return data

def save_data(data):
    """
    Ghi data.json an toàn:
    - Backup pre-save
    - Ghi ra file tạm trong cùng thư mục
    - os.replace để đảm bảo atomic
    """
    try:
        snapshot_data_v16(data, tag="pre-save", subkey="pre_save")
    except Exception:
        pass

    dir_ = os.path.dirname(os.path.abspath(DATA_FILE)) or "."
    fd, tmp_path = tempfile.mkstemp(prefix="data_", suffix=".json", dir=dir_)
    os.close(fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, DATA_FILE)

#=================GHI LẠI DATA =================

def ensure_user(user_id: str):
    """
    Đảm bảo user tồn tại trong data["users"].
    KHÔNG phụ thuộc ctx ở đây (để không phải sửa toàn file),
    việc ghi name / guild_id / last_active sẽ được cập nhật riêng
    bên trong từng lệnh gameplay khi có ctx.

    Trả về: data (toàn bộ), và luôn đảm bảo khung stats mới.
    """
    data = load_data()
    users = data.setdefault("users", {})

    if user_id not in users:
        users[user_id] = {
            "ngan_phi": STARTING_NP,
            "rungs": {"D":0,"C":0,"B":0,"A":0,"S":0},
            "items": [],
            "equipped": {
                "slot_vukhi": None,
                "slot_aogiap": None
            },
            "cooldowns": {"ol":0},
            "stats": {
                "opened": 0,
                "ol_count": 0,
                "odt_count": 0,
                "ngan_phi_earned_total": 0,
                "odt_np_spent_total": 0,
                "odt_np_earned_total": 0,
                "sold_count": 0,
                "sold_value_total": 0
            },
            "claimed_missions": [],
            "achievements": [],
            "minigames": {
                "odt": {"win_streak": 0, "loss_streak": 0}
            },
            # thông tin phục vụ thống kê toàn hệ thống
            "name": "",
            "guild_id": 0,
            "last_active": 0
        }
        save_data(data)
    else:
        # đảm bảo các key mới tồn tại kể cả user cũ
        u = users[user_id]
        u.setdefault("rungs", {"D":0,"C":0,"B":0,"A":0,"S":0})
        u.setdefault("items", [])
        u.setdefault("equipped", {})
        u["equipped"].setdefault("slot_vukhi", None)
        u["equipped"].setdefault("slot_aogiap", None)
        u.setdefault("cooldowns", {}).setdefault("ol", 0)
        st = u.setdefault("stats", {})
        st.setdefault("opened", 0)
        st.setdefault("ol_count", 0)
        st.setdefault("odt_count", 0)
        st.setdefault("ngan_phi_earned_total", 0)
        st.setdefault("odt_np_spent_total", 0)
        st.setdefault("odt_np_earned_total", 0)
        st.setdefault("sold_count", 0)
        st.setdefault("sold_value_total", 0)
        u.setdefault("claimed_missions", [])
        u.setdefault("achievements", [])
        mg = u.setdefault("minigames", {})
        mg.setdefault("odt", {"win_streak": 0, "loss_streak": 0})
        u.setdefault("name", "")
        u.setdefault("guild_id", 0)
        u.setdefault("last_active", 0)
        save_data(data)

    return data


def touch_user_activity(ctx, user_dict: dict):
    """
    Cập nhật thông tin hoạt động mới nhất cho user:
    - name: tên hiển thị hiện tại
    - guild_id: server hiện tại (nếu có)
    - last_active: timestamp
    """
    try:
        user_dict["name"] = ctx.author.display_name
    except Exception:
        pass
    try:
        if ctx.guild:
            user_dict["guild_id"] = ctx.guild.id
    except Exception:
        pass
    try:
        user_dict["last_active"] = int(time.time())
    except Exception:
        pass





#=================GHI LẠI DATA =================


def format_num(n:int)->str:
    return f"{n:,}"

def make_embed(title, description="", fields=None, color=0x9B5CF6, thumb=None, image=None, footer=None):
    emb = discord.Embed(title=title, description=description, color=color)
    if fields:
        for n,v,inline in fields:
            emb.add_field(name=n, value=v, inline=inline)
    if thumb: emb.set_thumbnail(url=thumb)
    if image: emb.set_image(url=image)
    if footer: emb.set_footer(text=footer)
    return emb

# ===== CẤU HÌNH KÊNH (osetbot – nhiều kênh) =====
def _sv_cfg(data, guild_id: int) -> dict:
    root = data.setdefault("server_cfg", {})
    return root.setdefault(str(guild_id), {})

def get_guild_channels(data, guild_id: int) -> set[int]:
    cfg = _sv_cfg(data, guild_id)
    lst = cfg.get("bot_channels")
    if isinstance(lst, list) and lst:
        try:
            return {int(x) for x in lst}
        except Exception:
            pass
    # tương thích cũ
    rec = data.setdefault("guild_settings", {}).setdefault(str(guild_id), {})
    legacy = rec.get("channel_id")
    if legacy:
        try:
            return {int(legacy)}
        except Exception:
            return set()
    return set()

def set_guild_channels_only(data, guild_id: int, channel_id: int):
    cfg = _sv_cfg(data, guild_id)
    cfg["bot_channels"] = [int(channel_id)]

def add_guild_channel(data, guild_id: int, channel_id: int, max_channels: int = 5) -> bool:
    cfg = _sv_cfg(data, guild_id)
    cur = list(get_guild_channels(data, guild_id))
    if int(channel_id) in cur:
        return True
    if len(cur) >= max_channels:
        return False
    cur.append(int(channel_id))
    cfg["bot_channels"] = cur
    return True

def remove_guild_channel(data, guild_id: int, channel_id: int) -> bool:
    cfg = _sv_cfg(data, guild_id)
    cur = list(get_guild_channels(data, guild_id))
    if int(channel_id) not in cur:
        return False
    cur = [c for c in cur if int(c) != int(channel_id)]
    cfg["bot_channels"] = cur
    return True

# ===== CẤU HÌNH KÊNH (osetbot – nhiều kênh) =====






# =================================================================================================
# [PL-002] EMOJI, ẢNH, RARITY, MÔ TẢ LOOT
# - toàn bộ mapping emoji, hình, màu
# - pool map
# - mô tả rơi
# => mục này bạn đã viết rất đầy đủ, tôi chỉ bọc lại
# =================================================================================================
# (Khu vực Emoji dùng chung toàn dự án)
RARITY_EMOJI = {
    "D": "<a:D12:1432473477616505023>",
    "C": "<a:C11:1432467636943454315>",
    "B": "<a:B11:1432467633932075139>",
    "A": "<a:A11:1432467623051919390>",
    "S": "<a:S11:1432467644761509948>",
}
RARITY_CHEST_EMOJI = {
    "D": "<a:rd_d:1431717925034918052>",
    "C": "<a:rc_d:1431713192123568328>",
    "B": "<a:rb_d:1431713180975108291>",
    "A": "<a:ra_d:1431713170384490726>",
    "S": "<a:rs_d:1432101376699269364>",
}
RARITY_CHEST_OPENED_EMOJI = {
    "D": "<a:rd_m:1431717929782870116>",
    "C": "<a:rc_m:1431713195860693164>",
    "B": "<a:rb_m:1431713187924934686>",
    "A": "<a:ra_m:1431713174704492604>",
    "S": "<a:rs_m:1434605431145369610>",
}
EMOJI_MORUONG          = "<a:rd_m:1431717929782870116>"
EMOJI_TRANG_BI_COUNT   = "<:motrangbi:1431822388793704508>"
NP_EMOJI               = "<a:np:1431713164277448888>"
EMOJI_NOHU4            = "<a:nohu5:1432589822740004934>"
EMOJI_CANHBAO          = "<:thongbao:1432852057353621586>"
EMOJI_THONGBAO         = "<:canhbao:1432848238104543322>"
EMOJI_DOTHACH          = "<a:dothach:1431793311978491914>"
EMOJI_DOTHACHT         = "<:dothacht:1431806329529303041>"
EMOJI_DOTHACH1         = "<a:dothach1:1432592899694002286>"
EMOJI_DOTHACHTHUA      = "<:dothachthua:1432755827621757038>"
EMOJI_THIENTHUONG      = "<a:thienthuong:1434625295897333811>"


# ===== Emoji — KẾT THÚC =====

# ===== Link Hình Ảnh — BẮT ĐẦU =====
IMG_BANDO_DEFAULT = "https://i.postimg.cc/15CvNdQL/bando.png"
IMG_RUONG_MO      = "https://i.ibb.co/21NS0t10/ruongdamo.png"
IMG_NGAN_PHIEU    = "https://i.ibb.co/DDrgRRF1/nganphieu.png"
IMG_KHO_DO        = "https://i.postimg.cc/W3189R0f/thungdo-min.png"
IMG_NHAN_VAT      = "https://sv2.anhsieuviet.com/2025/10/29/nhanvat-min.png"
ITEM_IMAGE = {
    "Kiếm":     "https://i.ibb.co/6pDBWyR/kiem.png",
    "Thương":   "https://i.ibb.co/S2C7fwJ/thuong.png",
    "Đàn":      "https://i.ibb.co/Fk0rSpQg/dan.png",
    "Trượng":   "https://i.ibb.co/ymbxhtg5/truong.png",
    "Dải Lụa":  "https://i.ibb.co/Myx1fD34/dailua.png",
    "Găng Tay": "https://i.ibb.co/gbn2Q6Gx/gangtay.png",
    "Áo Giáp":  "https://i.ibb.co/jkWkT5hj/giap.png"
}
RARITY_COLOR = {
    "D":0x8B6B46,
    "C":0x2F80ED,
    "B":0x8A2BE2,
    "A":0xFF6A00,
    "S":0xFFD700
}
MAP_IMAGES = {
    "S": "https://sv2.anhsieuviet.com/2025/10/28/5-min.png",
    "A": "https://sv2.anhsieuviet.com/2025/10/28/4-min.png",
    "B": "https://sv2.anhsieuviet.com/2025/10/28/3-min.png",
    "C": "https://sv2.anhsieuviet.com/2025/10/28/2-min.png",
    "D": "https://sv2.anhsieuviet.com/2025/10/28/1-min.png",
}
# ===== Link Hình Ảnh — KẾT THÚC =====

# ===== Rarity, map, mô tả loot — BẮT ĐẦU =====
RARITY_PROBS = [("D",0.50),("C",0.30),("B",0.15),("A",0.04),("S",0.01)]
NGANPHIEU_RANGE = {
    "D":(1,5),
    "C":(5,10),
    "B":(10,500),
    "A":(500,2000),
    "S":(2000,50000)
}
PROB_ITEM_IN_RUONG = 0.40
MAP_POOL = [
    "Biện Kinh","Đào Khê Thôn","Tam Thanh Sơn",
    "Hàng Châu","Từ Châu","Nhạn Môn Quan",
    "Discord NTH Fan"
]
ITEM_TYPES = [
    "Kiếm","Thương","Đàn","Trượng",
    "Dải Lụa","Găng Tay","Áo Giáp"
]
ITEM_VALUE_RANGE = {
    "D":(20,100),
    "C":(100,500),
    "B":(500,5000),
    "A":(5000,20000),
    "S":(20000,200000)
}
ITEM_NAMES = {
    "Kiếm":[
        ("Kiếm Sắt","D"),
        ("Kiếm Lam Tinh","C"),
        ("Kiếm Hàn Vân","B"),
        ("Kiếm Trúc Nguyệt","A"),
        ("Kiếm Thượng Thần","S")
    ],
    "Thương":[
        ("Thương Sơ","D"),
        ("Thương Bão Tố","C"),
        ("Thương Tiêu Hồn","B"),
        ("Thương Huyền Vũ","A"),
        ("Thương Chấn Thiên","S")
    ],
    "Đàn":[
        ("Đàn Tre","D"),
        ("Đàn Thanh","C"),
        ("Đàn Hồn Thanh","B"),
        ("Đàn Pháp Nguyệt","A"),
        ("Đàn Thiên Nhạc","S")
    ],
    "Trượng":[
        ("Trượng Gỗ","D"),
        ("Trượng Ma","C"),
        ("Trượng Phong Ảnh","B"),
        ("Trượng Linh Ngưng","A"),
        ("Trượng Càn Khôn","S")
    ],
    "Dải Lụa":[
        ("Lụa Tầm Thôn","D"),
        ("Lụa Thanh","C"),
        ("Lụa Huyễn Liễu","B"),
        ("Lụa Phượng Hoàng","A"),
        ("Lụa Mị Ảnh","S")
    ],
    "Găng Tay":[
        ("Găng Vải","D"),
        ("Găng Bão","C"),
        ("Găng Ma Pháp","B"),
        ("Găng Kim Cương","A"),
        ("Găng Vô Ảnh","S")
    ],
    "Áo Giáp":[
        ("Áo Da","D"),
        ("Áo Linh Phi","C"),
        ("Áo Ngự Vân","B"),
        ("Áo Hắc Vô Cực","A"),
        ("Áo Vô Song","S")
    ]
}

MAP_DISCORD = "Discord NTH Fan"

DESCRIPTIONS = {
    "D": [
        "Bạn dạo quanh chợ phàm nhân, bất ngờ phát hiện chiếc rương gỗ cũ dưới gốc cây.",
        "Hành tẩu giang hồ vấp hòn đá lạ — bên dưới là rương phủ rêu.",
        "Trời nắng đẹp, bạn lên núi hái thuốc — ven đường lộ ra rương gỗ mộc.",
        "Hoàn thành việc vặt ở trấn nhỏ, trưởng lão thưởng cho bạn rương bé xíu.",
        "Giếng cổ lộ đá lạ, bạn moi ra chiếc rương sứt mẻ.",
        "Tại lùm trúc vang âm thanh khẽ, bạn nhặt được rương mini.",
        "Bão tan, gốc cây bật rễ — lộ ra rương đồng rỉ.",
        "Đồng hành cảm tạ, tặng bạn rương nhỏ bọc vải.",
        "Cửa hàng tạp hóa bán rẻ một rương cũ không chìa.",
        "Bến thuyền có bao tải dạt vào, trong là rương gỗ con.",
        "Khe núi hẹp phản quang, hóa ra là khóa rương cũ.",
        "Tiểu tăng quên đồ, bạn trả lại — được tặng rương mộc.",
        "Sương sớm đọng nặng trên nắp rương, bạn khẽ mở thử.",
        "Lều cỏ bỏ hoang, rương bé bị bụi phủ kín.",
        "Tiếng ve ngừng, mùi gỗ cũ thoảng lên — một rương nhỏ nằm đó.",
        "Dưới bậc đá miếu hoang, bạn gạt rêu thấy rương gài then.",
        "Bờ ruộng có ánh lập lòe — dây leo che nửa chiếc rương.",
        "Bạn đốt lửa sưởi đêm, tro tàn lộ ra mép rương vỡ.",
        "Trên tấm bia sụp có khắc ký hiệu dẫn tới rương cũ.",
        "Một con sóc tha nhầm chìa khóa, bạn lần theo và gặp rương mộc."
    ],
    "C": [
        "Bạn rút quẻ đại cát, may mắn nhặt được rương gỗ phát sáng nhẹ.",
        "Nghỉ chân bên suối nghe tiếng ngân — rương đồng nho nhỏ trôi lên.",
        "Bạn vấp phải rương bé lăn tới như muốn theo bạn về.",
        "Gió nghịch thổi rương mini đến sát mũi giày.",
        "Trong lùm hoa, bướm đậu lên chiếc rương nhỏ khảm đinh.",
        "Tuyết tan để lộ rương đơn sơ nép trong băng mỏng.",
        "Bạn luyện công vấp đá — dưới đó là rương cũ phủ bụi.",
        "Dọn kho chùa hoang bắt gặp rương bé bị chuột tha vào góc.",
        "Làn khói đàn hương dẫn bạn tới rương gỗ khắc phù.",
        "Mưa rào tạnh, cầu vồng chiếu lên nắp rương nhỏ.",
        "Ngư ông cúng bạn rương lạ vớt ngoài hồ.",
        "Tiếng chuông xa ngân, nắp rương khẽ rung theo nhịp.",
        "Đá tảng nứt, khe hở giấu rương mini bọc lụa.",
        "Bạn giúp dân làng sửa đê, được tặng rương nhỏ tri ân.",
        "Trên cành cây rỗng có rương gỗ nhét vừa tay.",
        "Chuông gió treo hiên trỏ hướng — bạn thấy rương nhỏ.",
        "Bước chân chạm bậc cổ thềm, viên gạch rơi lộ rương con.",
        "Đốm lửa đom đóm tụ lại quanh chiếc rương tinh xảo.",
        "Bạn nhặt lá bùa cổ, dưới là rương gỗ cài then.",
        "Ve sầu lột xác bên rương nhỏ khắc đường vân đẹp."
    ],
    "B": [
        "Bạn thám hiểm ngoại thành, đánh lui du côn — thu được rương quý.",
        "Đêm trăng linh quang chiếu xuống — hiện rương cổ tiền triều.",
        "Bạn lập công bắt trộm, được thưởng rương khóa đồng nặng.",
        "Phá trận pháp đơn sơ trong hang tối — rương bí ẩn lộ ra.",
        "Đẩy lùi cướp đường, rương rơi từ tay tên thủ lĩnh.",
        "Sửa miếu thờ, sau bệ đá ẩn rương cổ đinh chạm.",
        "Trận chiến vách đá kết thúc, rương rơi đúng bàn tay bạn.",
        "Qua minh cốc, chuông đá rung — rương quý bật nắp.",
        "Hồ sen nở rộ; gốc sen dính rương chạm bạc.",
        "Thư khố cũ có hộc bí mật, bên trong là rương khảm đồng.",
        "Quặng mạch đổi sắc, bạn đào lên rương trân châu.",
        "Đỉnh núi nổi mây tím, rương mạ đồng hiện dấu ấn gia tộc.",
        "Mộ cổ lộ ra đạo khẩu, rương chạm thú canh giữ.",
        "Hạc giấy chỉ đường đưa bạn tới rương gấm.",
        "Mưa sao băng rơi, rương sáng dịu đáp bên chân.",
        "Tiếng tiêu trên núi gọi bạn tới rương khắc long vân.",
        "Cửa ngầm Vân Sơn mở, rương quý từ tường trượt ra.",
        "Cây cổ thụ tiết nhựa thơm, trong hốc là rương bí dược.",
        "Lò rèn nguội tro còn ấm, rương thép sẫm nằm dưới đe.",
        "Sắc phù cổ rung lên — rương quý đáp ứng lời triệu."
    ],
    "A": [
        "Thiên vận chú ý — một rương ngọc hiện ra giữa linh quang rực rỡ.",
        "Tập khinh công rơi vào khe — đáy có rương báu lóe sáng.",
        "Ánh linh lực tụ lại hóa rương châu sáng ngời.",
        "Cổ thụ nở hoa đêm, gốc hé rương thơm mùi linh dược.",
        "Khí mạch chấn động, rương phát sáng bay vòng quanh rồi hạ xuống.",
        "Tiên hạc sà xuống, đặt rương châu tinh xảo vào tay bạn.",
        "Khoảnh khắc đột phá cảnh giới, đất rung lộ rương báu chờ sẵn.",
        "Tâm bão tuyết tách đôi, rương vàng lơ lửng như đợi chủ.",
        "Dòng suối hóa thành gương, phản chiếu rương ngọc lấp lánh.",
        "Vân hà mở lối, rương huyền quang từ xa bay tới.",
        "Đài tế cổ nổi lên, rương khắc phù văn tiên gia.",
        "Hào quang tụ đỉnh, rương chói rót xuống tay bạn.",
        "Tinh tú đổi vị, rương thiên tượng rơi đúng tọa độ.",
        "Chuông cổ tự ngân ba hồi, rương báu trồi khỏi nền đất.",
        "Linh điểu dẫn đường, rương bảo vật hiện nơi lòng chảo.",
        "Thủy kính vỡ, rương ánh bạc trồi lên như hô ứng.",
        "Sương mù tán, rương bạch ngọc hiện giữa thảo nguyên.",
        "Đá trời nứt, rương hoàng kim từ lõi đá lộ diện.",
        "Tháp cổ mở mắt trận, rương ngọc từ bậc thang trôi xuống.",
        "Phong vân biến sắc, rương báu đáp xuống theo vết sét."
    ],
    "S": [
        "Thiên địa dao động — rương thần bí đáp xuống như tiên nhân gửi tặng.",
        "Nhập định cửu thiên — tỉnh dậy đã thấy rương chứa bí bảo thất truyền.",
        "Mây xé trời, rương thần giáng như sắc phong cửu thiên.",
        "Cổ mộc hóa rồng rồi tan — rương kim sắc còn lại như di vật tiên giới.",
        "Tượng thần mở mắt, đạo âm vang — rương chí tôn hạ xuống.",
        "Trăng dựng Tây Hồ, nước tách — rương tiên từ đáy hồ bay lên.",
        "Cổng thời không mở, rương vàng từ xa xưa trao quyền thừa kế.",
        "Tuyết phong tụ long ảnh hóa rương, đất trời lặng im.",
        "Thiên tinh rơi, rương nhật nguyệt dung hợp trong tay bạn.",
        "Vân kiếp tiêu tan, rương thiên kim treo giữa không trung.",
        "Đạo vận hội tụ lên đỉnh đầu — rương thần giáng lễ tấn phong.",
        "Long mạch chuyển, rương chí tôn nứt ánh thần văn.",
        "Chu thiên đại trận kích hoạt, rương hoàng cực xuất thế.",
        "Nguyệt quang chảy thành suối, rương tinh diệu nổi bồng bềnh.",
        "Lôi đình giáng xuống, rương lục lôi an tọa bất động.",
        "Tiên cầm hát khúc đăng thiên, rương bảo vân thăng hạ.",
        "Vô tự thiên thư tự lật, rương kim quang xuất hiện ở chương cuối.",
        "Hồn đèn miếu cổ bùng cháy, rương xích kim bay khỏi bệ.",
        "Thanh thiên mở vết rạn, rương thiên uy xuyên qua khe nứt.",
        "Thiên đạo ban ấn, rương thánh khắc lệnh đồ trên nắp."
    ],
}

DISCORD_DESCRIPTIONS = {
    "D": [
        "Bạn tham gia event nhẹ trên Discord — quà an ủi là chiếc rương gỗ mộc.",
        "Tin nhắn hệ thống ping: ‘Bạn có phần quà nhỏ!’ — mở ra rương cũ.",
        "Channel #eventbang nổ thông báo — bạn kịp claim rương nhỏ.",
        "Bạn trả lời đúng 1 câu quiz — được phát rương bé xíu.",
        "Admin phát lì xì test — bạn nhận một rương đơn sơ.",
        "Bot gửi DM ‘nhiệm vụ hằng ngày’ — bạn nhận rương mộc.",
        "Bạn ghé kênh #chatbanghoi — mod tặng rương gỗ.",
        "Phản hồi bug hợp lệ — phần quà là rương phủ bụi.",
        "Bạn online đủ giờ — hệ thống tặng rương bé.",
        "Mini reaction game trao tay bạn chiếc rương nhỏ.",
        "Bạn check-in kênh #chatchung — rinh rương gỗ mini.",
        "Nhiệm vụ ‘chào hỏi’ hoàn thành — nhận rương mộc.",
        "Kênh voice kết thúc — bạn được rương kỷ niệm.",
        "Bạn nhận 1 lượt đua vịt và trúng quà — là rương nhỏ xinh.",
        "Đua TOP 10 kết thúc — bạn lọt top 10 và có rương.",
        "Sticker war vui vẻ — mod tặng rương an ủi.",
        "Bạn report spam kịp lúc — nhận rương cảm ơn.",
        "Tham gia poll — phần thưởng rương gỗ bé.",
        "Bạn test role mới — bonus rương cũ.",
        "Bạn đã ‘đọc nội quy’ xong — hệ thống phát rương mộc."
    ],
    "C": [
        "Tham gia mini game giờ vàng — bạn nhận rương phát sáng nhẹ.",
        "Bot quay số — tên bạn hiện lên, rương đồng nho nhỏ về tay.",
        "Bạn đạt mốc online tuần — hệ thống gửi rương mini.",
        "Sự kiện sticker đạt mốc — bạn có rương cảm ơn.",
        "Góp ý giao diện hợp lý — mod tặng rương nhỏ.",
        "Phản hồi survey — nhận rương đồng.",
        "Bạn hoàn thành nhiệm vụ guild — rương C gửi thẳng kho.",
        "Kênh event thông báo: bạn qualified — rương nhỏ unlock.",
        "Bạn giữ sạch kênh chat — hệ thống thưởng rương.",
        "Hoàn tất onboarding role — bonus rương C vừa tay.",
        "Tương tác đạt streak — rương mini được phát.",
        "Bạn pass checkpoint quiz — rương đồng về túi.",
        "Đạt cấp độ chat 5 — rương C auto claim.",
        "Tham gia thread xây ý tưởng — quà là rương nhỏ.",
        "Bạn giúp trả lời tân thủ — bot ghi nhận rương thưởng.",
        "Chốt ngày công cán bộ — phát rương mini tri ân.",
        "Bạn clear report — rương đồng chuyển khoản.",
        "Check in 7 ngày — rương C xuất hiện.",
        "Up meme đúng chủ đề — rương nhỏ bật nắp.",
        "Bạn review tài liệu — rương mini gửi nhanh."
    ],
    "B": [
        "Thắng bán kết event — bạn nhận rương quý.",
        "Đứng top phản hồi tuần — rương B về tay.",
        "Clear bug quan trọng — admin tặng rương khóa đồng.",
        "Tổ chức minigame thành công — rương quý unlock.",
        "Hoàn thành guide chuẩn — rương chạm bạc xuất kho.",
        "Đạt role ‘Cộng tác’ — rương B chuyển phát nhanh.",
        "Lead voice room — khoá đồng bàn giao.",
        "Gửi pack emoji chất lượng — rương quý tặng thưởng.",
        "Review rule chi tiết — rương B ghi công.",
        "Chụp banner — rương quý có tên bạn.",
        "Hỗ trợ event cross-server — rương B về kho.",
        "Deploy bot test ổn — rương khóa đồng đến tay.",
        "Cứu kèo phút chót — rương quý tôn vinh.",
        "Thiết kế frame độc — rương B xuất hiện.",
        "Đạt KPI nội dung — rương quý trao tay.",
        "Moderation nghiêm túc — rương B tri ân.",
        "Sưu tầm lore server — rương quý học hỏi.",
        "Ghim tài liệu chuẩn — rương B open slot.",
        "Tối ưu kênh voice — rương quý chúc mừng.",
        "Biên tập recap chất — rương B lên đường."
    ],
    "A": [
        "Thắng chung kết event — rương ngọc rực rỡ xuất hiện.",
        "Lập thành tích đột phá tháng — rương báu A mở slot.",
        "Push dự án server thành công — rương châu về tay.",
        "Thiết kế hệ thống role mới — rương ngọc phát sáng.",
        "Dẫn dắt chiến dịch cộng đồng — rương báu gửi tặng.",
        "Đạt kỷ lục tương tác — rương vàng A hạ cánh.",
        "Phát hiện lỗ hổng lớn — admin trao rương ngọc.",
        "Xây onboarding xịn — rương báu trình diện.",
        "Rework theme — rương A bừng sáng.",
        "Contributor of the Month — rương báu đến.",
        "Điều phối giải đấu — rương A ghi nhận.",
        "Thiết kế UX cho bot — rương ngọc on-chain vào kho.",
        "Dẫn tour tân thủ — rương báu theo bạn về.",
        "Viết tài liệu chuẩn hóa — rương A thăng điểm.",
        "Refactor bot thành công — rương châu sáng rỡ.",
        "Kết nối cộng đồng — rương báu cập bến.",
        "Triển khai CDN ảnh — rương A thưởng nóng.",
        "Series event dài hạn — rương báu mở nắp.",
        "Lead hackathon nội bộ — rương A vinh danh.",
        "Ổn định hạ tầng đêm bão — rương báu A gửi tới."
    ],
    "S": [
        "Toàn server vỗ tay — bạn nhận rương thần sắc như ‘legendary drop’.",
        "Tên bạn lên banner — rương S hoàng kim xuất hiện.",
        "Đại sự kiện thành công — rương chí tôn giáng lâm.",
        "Bạn giữ lửa cộng đồng — rương thánh ban ấn.",
        "Đưa NTH Fan lên trending — rương S rực sáng.",
        "Vượt KPI toàn diện — rương chí tôn khắc lệnh.",
        "Kết nối liên minh server — rương thần đạo trao tay.",
        "Cứu server khỏi crash — rương S thiên quang giáng.",
        "Xây vận hành bền vững — rương chí tôn xuất thế.",
        "Mở kỷ nguyên sự kiện mới — rương thánh rực rỡ.",
        "Dẫn dắt đại lễ kỷ niệm — rương S hội tụ phong vân.",
        "Hợp nhất cộng đồng phân mảnh — rương thần uy mở khóa.",
        "Vẽ bản đồ tương lai server — rương chí tôn ấn ký.",
        "Đặt nền móng hệ thống mới — rương S hiển thánh.",
        "Chuyển giao thế hệ mượt mà — rương thánh vàng giáng.",
        "Kiến tạo văn hóa server — rương thần ban tặng.",
        "Thống nhất tiêu chuẩn nội bộ — rương S đáp lễ.",
        "Mở cổng sáng tạo người dùng — rương chí tôn long lanh.",
        "Định hình bản sắc vĩnh cửu — rương thánh khắc danh.",
        "Bạn trở thành biểu tượng — rương S theo bạn như ấn tín."
    ],
}

def get_loot_description(map_name: str, rarity: str) -> str:
    pool = DISCORD_DESCRIPTIONS if map_name == MAP_DISCORD else DESCRIPTIONS
    arr = pool.get(rarity, DESCRIPTIONS.get("D", []))
    if not arr:
        arr = DESCRIPTIONS["D"]
    return random.choice(arr)

def choose_rarity():
    r = random.random()
    acc=0.0
    for rar,p in RARITY_PROBS:
        acc += p
        if r <= acc:
            return rar
    return "D"

def get_nganphieu(r):
    lo,hi = NGANPHIEU_RANGE[r]
    return random.randint(lo,hi)

def gen_short_id(existing_ids:set):
    tries = 0
    while True:
        tries += 1
        iid = f"{random.randint(0,999):03d}"
        if iid not in existing_ids or tries>2000:
            return iid

def generate_item(rarity, user_items:list, item_type=None):
    if not item_type:
        item_type = random.choice(ITEM_TYPES)
    candidates = [n for (n,r) in ITEM_NAMES[item_type] if r==rarity]
    name = (random.choice(candidates) if candidates else ITEM_NAMES[item_type][0][0])
    lo,hi = ITEM_VALUE_RANGE[rarity]
    value = random.randint(lo,hi)
    existing = {it["id"] for it in user_items}
    iid = gen_short_id(existing)
    return {
        "id": iid,
        "name": name,
        "type": item_type,
        "rarity": rarity,
        "value": value,
        "equipped": False
    }
# ===== Rarity, map, mô tả loot — KẾT THÚC =====

# ===== ẢNH: helper attach trễ =====
IMAGE_TIMEOUT_SEC = 2.5
async def _attach_image_later(ctx, message, embed, url, filename):
    try:
        file = await asyncio.wait_for(file_from_url_cached(url, filename), timeout=IMAGE_TIMEOUT_SEC)
        if file:
            embed.set_image(url=f"attachment://{filename}")
            try:
                await message.edit(embed=embed, attachments=[file])
            except TypeError:
                await ctx.send(embed=embed, file=file)
    except Exception:
        pass

def images_enabled_global() -> bool:
    data = load_data()
    cfg = data.get("config", {})
    return bool(cfg.get("images_enabled", True))

# =========================
# 🔧 HỆ THAM CHIẾU CHUNG — KẾT THÚC
# =========================


# ===================================
# 🧩 BOT & CẤU HÌNH CHUNG — BẮT ĐẦU
# ===================================
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("o","O"),
    intents=INTENTS,
    help_command=None,
    case_insensitive=True
)

@bot.event
async def on_ready():
    """
    Gọi khi bot login xong và event loop Discord đã chạy.
    - Log bot ready
    - Chụp snapshot 'startup' (như cũ)
    - Khởi động vòng auto_backup_task nếu chưa chạy
    """
    global _auto_backup_started

    print(f"✅ Bot ready: {bot.user} (id: {bot.user.id})")

    # Snapshot khởi động (giữ nguyên logic cũ của bạn)
    try:
        data = load_data()
        snapshot_data_v16(data, tag="startup", subkey="startup")
    except Exception:
        pass

    # Khởi động vòng auto backup 1 lần duy nhất
    if not _auto_backup_started:
        try:
            auto_backup_task.start()
            _auto_backup_started = True
            print("[AUTO-BACKUP] Đã khởi động auto_backup_task.")
            print(
                f"[AUTO-BACKUP] Cấu hình ban đầu: "
                f"backup mỗi {AUTO_BACKUP_INTERVAL_MINUTES} phút, "
                f"báo mỗi {AUTO_REPORT_INTERVAL_MINUTES} phút."
            )
        except RuntimeError:
            # Nếu Discord reconnect và task đã start rồi -> bỏ qua
            pass
# ===================================
# 🧩 BOT & CẤU HÌNH CHUNG — KẾT THÚC
# ===================================



# =================================================
# 🧱 QUẢN LÝ — ADMIN (module-style)
# =================================================
from discord import ui, ButtonStyle, Interaction

ADMIN_WHITELIST = {
    "setbot","osetbot",
    "lenhquantri","saoluu","listbackup","xemsaoluu",
    "phuchoi","resetdata","resetuser",
    "addtien","addruong",
    "gianlan","thabong","phattu",
    "batanh","pingg",
    "lenh","olenh"
    "saoluuantoan","osaoluuantoan"
    "xuatdata","oxuatdata"
    "osaoluuantoan","saoluuantoan"
    "othongbao",


}
GAMEPLAY_REQUIRE = {
    "ol","l",
    "okho","kho",
    "oxem","xem",
    "omac","mac",
    "othao","thao",
    "omo","mo",
    "oban","ban",
    "onhanvat","nhanvat",
    "odt","dt",
    "onhanthuong","nhanthuong",
    "otang",
    "onhiemvu",
    "obxh",
    "omonphai",
    "obantrangbi",
    "opb",



}

@bot.command(name="lenh", aliases=["olenh"])
async def cmd_olenh(ctx: commands.Context):
    desc = (
        "**⚔️ LỆNH SPAM**\n"
        "**osetbot** — Kích hoạt BOT trong kênh *(Admin)*\n"
        "**ol** — Đi thám hiểm, tìm rương báu (CD 10s)\n"
        "**odt** — Đổ thạch (hỗ trợ `odt all`)\n"
        "**opb** — Đi phó bản sơ cấp\n"
        "**opk** — Sắp ra mắt\n\n"


        "**👤 LỆNH NHÂN VẬT**\n"
        "**okho** — Xem kho đồ\n"
        "**oban all** — Bán tất tạp vật\n"
        "**obantrangbi** — Bán trang bị lấy tiền xu\n"
        "**omac** `<ID>` / `othao <ID>`\n"
        "**oxem** `<ID>` / `oxem all`\n"
        "**onhanvat** — Thông tin nhân vật\n"
        "**omo** — Mở rương (VD: omo D / omo all)\n"
        "**omonphai** — Gia nhập môn phái\n\n"

        "**💼 LỆNH TƯƠNG TÁC**\n"
        "**obxh** — Xem Bảng Xếp Hạng\n"
        "**otang** — `otang @nguoichoi <số>`\n"
        "**onhanthuong** — Nhận 500K NP + 1 Rương S\n"
        "**onhiemvu** — Nhiệm vụ hàng ngày\n\n"

        "**⬆️ LỆNH MỚI UPDATE**\n\n"
        "**omonphai** — Gia nhập môn phái\n\n"


        "**⚙️ THÔNG TIN NÂNG CẤP**\n\n"
        "• Lưu trữ dữ liệu vĩnh viễn\n"
        "• Thêm Tiền Xu, môn phái để mở tính năng pvp - pve\n"
        "• Thêm Tạp Vật bán NP, Trang Bị sẽ có chỉ số và hiếm ra hơn\n"
        "• BOT đang trong giai đoạn phát triển, mong các bạn thông cảm\n"



    )
    embed = discord.Embed(
        title="📜 DANH SÁCH LỆNH CƠ BẢN",
        description=desc,
        color=0xFFD700
    )
    embed.set_footer(text="BOT GAME NGH OFFLINE | NTH5.0")
    await ctx.reply(embed=embed, mention_author=False)




# =========================================
# CẤU HÌNH KÊNH BOT / THEO DÕI SERVER
# Lệnh: osetbot / setbot
# Yêu cầu: admin server
# =========================================

from discord.ext import commands
from discord import ui, ButtonStyle, Interaction
import time

def _update_guild_info_block(data, guild_obj: discord.Guild):
    """
    Cập nhật thông tin server (guild) vào data["guilds"] để
    lệnh thống kê (othongtinmc) có thể đọc tên server,
    số thành viên, và danh sách kênh bot hợp lệ.
    """
    gid = str(guild_obj.id)

    # đảm bảo nhánh tồn tại
    data.setdefault("guilds", {})
    if gid not in data["guilds"]:
        data["guilds"][gid] = {}

    # tên server
    data["guilds"][gid]["name"] = guild_obj.name

    # số thành viên (nếu bot có quyền xem)
    mcount = getattr(guild_obj, "member_count", None)
    if mcount is not None:
        data["guilds"][gid]["member_count"] = int(mcount)

    # lần cuối chỉnh cấu hình bot cho server này (epoch giây)
    data["guilds"][gid]["last_setbot"] = int(time.time())

    # lưu luôn danh sách kênh bot được phép hiện tại để chủ bot xem thống kê
    allowed_channels_now = list(get_guild_channels(data, guild_obj.id))
    data["guilds"][gid]["allowed_channels"] = [int(x) for x in allowed_channels_now]


class SetBotView(ui.View):
    def __init__(self, timeout: float | None = 180):
        super().__init__(timeout=timeout)

    async def _is_admin_or_deny(self, interaction: Interaction) -> bool:
        """
        Chỉ cho phép người có quyền admin thao tác các nút.
        Nếu không đủ quyền -> trả lời ephemeral và thoát.
        """
        perms = getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False)
        if not perms:
            try:
                await interaction.response.send_message(
                    "❌ Bạn cần quyền **Quản trị viên** để thao tác.",
                    ephemeral=True
                )
            except Exception:
                pass
            return False
        return True

    @ui.button(label="① Set DUY NHẤT kênh này", style=ButtonStyle.success, emoji="✅")
    async def btn_set_only(self, interaction: Interaction, button: ui.Button):
        """
        Chỉ cho phép BOT chạy duy nhất ở kênh này.
        Xoá whitelist cũ, giữ đúng kênh hiện tại.
        """
        if not await self._is_admin_or_deny(interaction):
            return

        data = load_data()

        # Ghi cấu hình allowed_channels: CHỈ kênh hiện tại
        set_guild_channels_only(data, interaction.guild.id, interaction.channel.id)

        # Cập nhật info server để thống kê global
        _update_guild_info_block(data, interaction.guild)

        save_data(data)

        try:
            await interaction.response.send_message(
                f"✅ ĐÃ CHỈ ĐỊNH DUY NHẤT kênh {interaction.channel.mention} cho BOT.\n"
                f"🔒 Các lệnh gameplay chỉ chạy ở kênh này.",
                ephemeral=True
            )
        except Exception:
            pass

    @ui.button(label="② Gỡ kênh này", style=ButtonStyle.danger, emoji="🗑️")
    async def btn_unset_here(self, interaction: Interaction, button: ui.Button):
        """
        Gỡ kênh hiện tại ra khỏi whitelist.
        Nếu whitelist rỗng => BOT coi như chạy ở mọi kênh.
        """
        if not await self._is_admin_or_deny(interaction):
            return

        data = load_data()

        removed_ok = remove_guild_channel(data, interaction.guild.id, interaction.channel.id)

        # cập nhật info server
        _update_guild_info_block(data, interaction.guild)

        save_data(data)

        if removed_ok:
            msg_txt = (
                f"🗑️ ĐÃ GỠ {interaction.channel.mention} khỏi danh sách kênh BOT.\n"
                f"ℹ️ Nếu không còn kênh whitelist, BOT sẽ chạy ở MỌI kênh."
            )
        else:
            msg_txt = (
                f"ℹ️ Kênh {interaction.channel.mention} hiện không nằm trong whitelist."
            )

        try:
            await interaction.response.send_message(msg_txt, ephemeral=True)
        except Exception:
            pass

    @ui.button(label="③ Thêm kênh phụ (kênh này)", style=ButtonStyle.primary, emoji="➕")
    async def btn_add_here(self, interaction: Interaction, button: ui.Button):
        """
        Thêm kênh hiện tại vào whitelist (cho phép BOT chạy ở nhiều kênh).
        Giới hạn tối đa số kênh phụ ví dụ 5.
        """
        if not await self._is_admin_or_deny(interaction):
            return

        data = load_data()

        added_ok = add_guild_channel(
            data,
            interaction.guild.id,
            interaction.channel.id,
            max_channels=5  # giữ giới hạn như thiết kế của bạn
        )

        # cập nhật info server
        _update_guild_info_block(data, interaction.guild)

        save_data(data)

        if added_ok:
            msg_txt = (
                f"➕ ĐÃ THÊM {interaction.channel.mention} "
                f"vào danh sách kênh BOT hợp lệ cho server này."
            )
        else:
            msg_txt = (
                "⚠️ Số lượng kênh đã đạt giới hạn. "
                "Hãy gỡ bớt trước khi thêm kênh mới."
            )

        try:
            await interaction.response.send_message(msg_txt, ephemeral=True)
        except Exception:
            pass

    @ui.button(label="④ Xem kênh đã set", style=ButtonStyle.secondary, emoji="📋")
    async def btn_list(self, interaction: Interaction, button: ui.Button):
        """
        Hiển thị danh sách whitelist kênh BOT hiện tại trong server này.
        Đồng thời cập nhật info server vào data["guilds"].
        """
        if not await self._is_admin_or_deny(interaction):
            return

        data = load_data()

        allowed_now = list(get_guild_channels(data, interaction.guild.id))

        # cập nhật info server (bao gồm allowed_channels)
        _update_guild_info_block(data, interaction.guild)

        save_data(data)

        if not allowed_now:
            txt = (
                "📋 Chưa có kênh nào bị khoá riêng.\n"
                "👉 BOT hiện có thể chạy ở MỌI kênh trong server."
            )
        else:
            mentions = []
            for cid in allowed_now:
                ch = interaction.guild.get_channel(int(cid))
                mentions.append(ch.mention if ch else f"`#{cid}`")
            txt = "📋 **Danh sách kênh BOT được phép:**\n" + " • ".join(mentions)

        try:
            await interaction.response.send_message(txt, ephemeral=True)
        except Exception:
            pass

# ====================================================================================================================================
# 🧍 SETBOT
# ====================================================================================================================================


@bot.command(name="osetbot", aliases=["setbot"])
@commands.has_guild_permissions(administrator=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_osetbot(ctx: commands.Context):
    """
    Gửi menu cấu hình BOT cho server hiện tại (4 nút).
    Admin server dùng để:
    - Khoá BOT vào đúng 1 kênh
    - Thêm kênh phụ
    - Gỡ kênh khỏi whitelist
    - Xem danh sách kênh đã set

    Ngoài ra, mỗi lần thao tác nút sẽ ghi thông tin server
    vào data["guilds"] để chủ bot coi thống kê tổng qua lệnh othongtinmc.
    """

    if not ctx.guild:
        await ctx.reply(
            "Lệnh này chỉ dùng trong server, không dùng trong DM.",
            mention_author=False
        )
        return

    note = (
        "⚠️ BOT dùng tiền tố `o` hoặc `O`.\n"
        "Chọn cách thiết lập kênh BOT cho server này:\n\n"
        "① Set DUY NHẤT kênh hiện tại\n"
        "② Gỡ kênh hiện tại khỏi danh sách\n"
        "③ Thêm kênh hiện tại làm kênh phụ\n"
        "④ Xem danh sách kênh được phép\n\n"
        "📌 BOT sẽ ghi nhận tên server + danh sách kênh để thống kê."
    )

    try:
        await ctx.send(note, view=SetBotView())
    except discord.HTTPException:
        await ctx.send(
            "Không thể gửi menu tương tác. Kiểm tra quyền gửi message / button.",
            mention_author=False
        )


# ====================================================================================================================================
# 🧍 SETBOT
# ====================================================================================================================================



# ====================================================================================================================================
# 🧍 BOT EVENT
# ====================================================================================================================================

def _looks_like_noise_o(msg: str) -> bool:
    if not msg:
        return False
    s = msg.strip().lower()
    if not s:
        return False
    first = s.split()[0]
    if first in IGNORE_O_TOKENS:
        return True
    if set(first) == {"o"}:
        return True
    for t in IGNORE_O_TOKENS:
        if first.startswith("o"+t):
            return True
    return False




@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CheckFailure):
        return
    if isinstance(error, commands.CommandNotFound):
        try:
            if _looks_like_noise_o(getattr(ctx.message, "content", "")):
                return
        except Exception:
            pass
        if ctx.guild:
            try:
                data = load_data()
                allowed = get_guild_channels(data, ctx.guild.id)
            except Exception:
                allowed = set()
            if (not allowed) or (ctx.channel.id not in allowed):
                return
        await ctx.reply(
            "❓ Lệnh không tồn tại. Dùng `olenh` để xem danh sách.",
            mention_author=False
        )
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(
            f"⏳ Vui lòng chờ thêm {int(error.retry_after)} giây.",
            mention_author=False
        )
        return
    if isinstance(error, commands.MissingRequiredArgument):
        name = getattr(ctx.command, "name", "")
        if name in {"mac","thao","xem"}:
            await ctx.reply(
                f"📝 Lệnh `{name}` cần ID. Ví dụ: `{name} 123`.",
                mention_author=False
            )
            return
        if name in {"dt"}:
            await ctx.reply(
                "📝 Dùng: `odt <số_ngân_phiếu>` — ví dụ: `odt 1000`.",
                mention_author=False
            )
            return
        await ctx.reply(
            "📝 Thiếu tham số. Dùng `olenh` để xem cú pháp.",
            mention_author=False
        )
        return
    if isinstance(error, commands.BadArgument):
        name = getattr(ctx.command, "name", "")
        if name in {"dt"}:
            await ctx.reply(
                "⚠️ Số tiền cược không hợp lệ. Ví dụ: `odt 500`.",
                mention_author=False
            )
            return
        if name in {"addtien","addruong"}:
            await ctx.reply(
                "⚠️ Số lượng không hợp lệ. Ví dụ: `oaddtien @user 1,000`.",
                mention_author=False
            )
            return
        await ctx.reply(
            "⚠️ Tham số không hợp lệ. Kiểm tra lại cú pháp.",
            mention_author=False
        )
        return

@bot.check
async def global_channel_check(ctx: commands.Context):
    if not ctx.guild:  # DM
        return True
    if ctx.command is None:
        return True
    cmd_names = {
        ctx.command.name.lower(),
        *[a.lower() for a in getattr(ctx.command, "aliases", [])]
    }
    if cmd_names & ADMIN_WHITELIST:
        return True
    if cmd_names & GAMEPLAY_REQUIRE:
        data = load_data()
        allowed = get_guild_channels(data, ctx.guild.id)
        if (not allowed) or (ctx.channel.id not in allowed):
            msg = (
                "⚠️ BOT sử dụng tiền tố `o` hoặc `O`.\n"
                "Yêu cầu Admin dùng **`osetbot`** để chỉ định kênh chạy BOT cho server này."
            )
            try:
                await ctx.reply(msg, mention_author=False)
            except Exception:
                await ctx.send(msg)
            return False
    return True
# ====================================================================================================================================
# 🧍 BOT EVENT
# ====================================================================================================================================


# ====================================================================================================================================
# 🧍 QUẢN LÝ — CHỦ BOT (module-style)
# ====================================================================================================================================

BOT_OWNERS = {821066331826421840}

def is_owner_user(user, bot):
    try:
        app = bot.application
        if app and app.owner and user.id == app.owner.id:
            return True
    except Exception:
        pass
    return user.id in BOT_OWNERS

def owner_only():
    async def predicate(ctx):
        return is_owner_user(ctx.author, ctx.bot)
    return commands.check(predicate)

def _get_user_ref(data: dict, member: discord.Member):
    uid = str(member.id)
    gid = str(getattr(getattr(member, "guild", None), "id", None)) if getattr(member, "guild", None) else None
    users = data.setdefault("users", {})
    if uid in users:
        return users[uid], "users"
    if gid and "guilds" in data and gid in data["guilds"]:
        g = data["guilds"][gid]
        if "users" in g and uid in g["users"]:
            return g["users"][uid], f"guilds[{gid}].users"
    if "players" in data and uid in data["players"]:
        return data["players"][uid], "players"
    u = users.setdefault(uid, {})
    return u, "users (new)"

def get_balance(u: dict) -> int:
    return int(u.get("ngan_phi", u.get("ngan_phieu", 0)))

def set_balance(u: dict, value: int) -> None:
    u["ngan_phi"] = int(value)
    if "ngan_phieu" in u:
        u.pop("ngan_phieu", None)

def ensure_rungs(u: dict) -> dict:
    legacy = u.pop("ruong", None)
    r = u.setdefault("rungs", {})
    if isinstance(legacy, dict):
        for k, v in legacy.items():
            if isinstance(v, int) and k in ("D","C","B","A","S"):
                r[k] = r.get(k, 0) + v
    for k in ("D","C","B","A","S"):
        r.setdefault(k, 0)
    return r
# =============================================================

@bot.command(name="lenhquantri")
@owner_only()
async def cmd_olenhquantri(ctx):
    lines = [
        "**LỆNH CHỦ BOT (Owner)**",
        "`saoluu` — Tạo backup thủ công",
        "`listbackup [limit]` — Liệt kê backup gần đây",
        "`xemsaoluu` — Xem thống kê backup",
        "`phuchoi [filename]` — Khôi phục dữ liệu",
        "`resetdata` — Reset toàn bộ dữ liệu (giữ config)",
        "`resetuser @user` — Reset dữ liệu 1 người",
        "`addtien @user <số>` — Cộng Ngân Phiếu",
        "`addruong @user <phẩm> <số>` — Cấp rương",
        "`xtien @user` — Chẩn đoán số dư & nhánh lưu",
        "`batanh [on|off]` — Bật/tắt hiển thị ảnh",
        "`okhoiphucfile` — Khôi phục dữ liệu từ file `data.json` (khi dữ liệu lớn)",
        "`otestdata` — Kiểm tra dữ liệu đang lưu trong volume Railway",
        "`othoigiansaoluu` — Thay đổi thời gian sao lưu tự động và thông báo",
        "`othongtinmc` — Thông tin máy chủ hiện tại",
        "`osaoluuantoan` — Sao lưu an toán",
        "`oxuatdata` — Xuất data về Discord",
        "`oxoabackup` — Dọn dẹp trống đầy volum",



    ]
    await ctx.reply("\n".join(lines), mention_author=False)





# ====================thông tin máy chủ===============================



@bot.command(name="othongtinmc", aliases=["thongtinmc"])
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_othongtinmc(ctx):
    """
    Báo cáo tổng quan tình trạng hệ thống BOT TU TIÊN.
    Chỉ dành cho Chủ Bot.
    """

    # ===== 1. Load data =====
    try:
        data = load_data()
    except Exception as e:
        await ctx.reply(f"❌ Không thể đọc dữ liệu: {e}", mention_author=False)
        return

    users_dict = data.get("users", {})
    guilds_dict = data.get("guilds", {})

    import time
    now_ts = time.time()

    # ===== 2. Thống kê người chơi =====
    total_users = len(users_dict)
    active_24h = 0
    for u in users_dict.values():
        last_active_ts = u.get("last_active", 0)
        try:
            last_active_ts = float(last_active_ts)
        except Exception:
            last_active_ts = 0
        if last_active_ts and (now_ts - last_active_ts) <= 86400:
            active_24h += 1

    # ===== 3. Kinh tế (Ngân Phiếu) =====
    total_money = 0
    for u in users_dict.values():
        try:
            total_money += int(u.get("ngan_phi", 0))
        except Exception:
            pass
    avg_money = (total_money / total_users) if total_users else 0

    # ===== 4. Top 5 người giàu nhất =====
    richest = sorted(
        users_dict.items(),
        key=lambda kv: int(kv[1].get("ngan_phi", 0)),
        reverse=True
    )[:5]

    richest_lines = []
    for uid, u in richest:
        display_name = u.get("name", "")
        if not display_name:
            # fallback hỏi Discord nếu chưa log tên
            try:
                user_obj = bot.get_user(int(uid))
                if user_obj:
                    display_name = user_obj.display_name or user_obj.name
                else:
                    user_obj = await bot.fetch_user(int(uid))
                    display_name = user_obj.display_name or user_obj.name
            except Exception:
                display_name = f"ID:{uid}"
        money_val = int(u.get("ngan_phi", 0))
        richest_lines.append(
            f"• {display_name} — 💰 {money_val:,} Ngân Phiếu"
        )
    richest_text = "\n".join(richest_lines) if richest_lines else "_Không có dữ liệu._"

    # ===== 5. Hoạt động server: Top 10 guild =====
    # gom user theo guild_id
    guild_count = {}
    for u in users_dict.values():
        gid = str(u.get("guild_id", ""))
        if gid:
            guild_count[gid] = guild_count.get(gid, 0) + 1

    top_guilds = sorted(
        guild_count.items(),
        key=lambda kv: kv[1],
        reverse=True
    )[:10]

    guild_lines = []
    for gid, count in top_guilds:
        ginfo = guilds_dict.get(str(gid), {})
        gname = ginfo.get("name", f"Server {gid}")
        member_ct = int(ginfo.get("member_count", 0))
        guild_lines.append(
            f"• {gname} — 🏠 {member_ct:,} | 🧙 {count:,}"
        )

    if not guild_lines and guilds_dict:
        # fallback trường hợp chưa có user.guild_id
        for gid, ginfo in list(guilds_dict.items())[:10]:
            gname = ginfo.get("name", f"Server {gid}")
            mem_ct = int(ginfo.get("member_count", 0))
            guild_lines.append(
                f"• {gname} — 🏠 {mem_ct:,} | 🧙 0"
            )
    guilds_text = "\n".join(guild_lines) if guild_lines else "_Không có dữ liệu server._"

    # ===== 6. Tổng hoạt động gameplay =====
    total_ol_all = 0
    total_odt_all = 0
    for uid, u in users_dict.items():
        st = u.get("stats", {})
        total_ol_all  += int(st.get("ol_count", 0))
        total_odt_all += int(st.get("odt_count", 0))

    # Top 5 spam ol nhất
    top_ol = sorted(
        users_dict.items(),
        key=lambda kv: int(kv[1].get("stats", {}).get("ol_count", 0)),
        reverse=True
    )[:5]
    top_ol_lines = []
    for uid, u in top_ol:
        st = u.get("stats", {})
        display_name = u.get("name", f"ID:{uid}")
        top_ol_lines.append(
            f"• {display_name} — 🔍 {int(st.get('ol_count',0))} lần `ol`"
        )
    top_ol_text = "\n".join(top_ol_lines) if top_ol_lines else "_Không có dữ liệu._"

    # Top 5 đổ thạch nhiều nhất
    top_odt = sorted(
        users_dict.items(),
        key=lambda kv: int(kv[1].get("stats", {}).get("odt_count", 0)),
        reverse=True
    )[:5]
    top_odt_lines = []
    for uid, u in top_odt:
        st = u.get("stats", {})
        display_name = u.get("name", f"ID:{uid}")
        top_odt_lines.append(
            f"• {display_name} — 🪨 {int(st.get('odt_count',0))} lần `odt`"
        )
    top_odt_text = "\n".join(top_odt_lines) if top_odt_lines else "_Không có dữ liệu._"

    # ===== 7. Backup / dung lượng =====
    try:
        data_path = os.path.join(BASE_DATA_DIR, "data.json")
        size_kb = os.path.getsize(data_path) / 1024
        size_info = f"{size_kb:.2f} KB"
    except Exception:
        size_info = "Không xác định"

    manual_dir = os.path.join(BASE_DATA_DIR, "backups", "manual")
    backup_files = []
    try:
        if os.path.isdir(manual_dir):
            for fn in os.listdir(manual_dir):
                if fn.endswith(".json"):
                    backup_files.append(fn)
        backup_count = len(backup_files)
    except Exception:
        backup_count = 0

    # ===== 8. Thời gian hiện tại =====
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ===== 9. Embed trả về =====
    embed = discord.Embed(
        title="📊 THỐNG KÊ DỮ LIỆU SERVER",
        description=f"Cập nhật lúc: `{now_str}`",
        color=0x2ECC71
    )

    # Người chơi
    embed.add_field(
        name="👥 Người chơi",
        value=(
            f"• Tổng: **{total_users:,}** người\n"
            f"• Hoạt động 24h: **{active_24h:,}** người"
        ),
        inline=False
    )

    # Kinh tế
    embed.add_field(
        name="💰 Kinh tế Ngân Phiếu",
        value=(
            f"• Tổng: {total_money:,}\n"
            f"• TB / người: {avg_money:,.0f}"
        ),
        inline=False
    )

    # Hoạt động gameplay
    embed.add_field(
        name="🎮 Hoạt động gameplay",
        value=(
            f"• Tổng `ol` toàn máy chủ: {total_ol_all:,}\n"
            f"• Tổng `odt` toàn máy chủ: {total_odt_all:,}"
        ),
        inline=False
    )

    # Top giàu
    embed.add_field(
        name="🏆 Top 5 người giàu nhất",
        value=richest_text,
        inline=False
    )

    # Top `ol`
    embed.add_field(
        name="🔍 Top 5 thám hiểm (`ol`)",
        value=top_ol_text,
        inline=False
    )

    # Top `odt`
    embed.add_field(
        name="🪨 Top 5 đổ thạch (`odt`)",
        value=top_odt_text,
        inline=False
    )

    # Top server
    embed.add_field(
        name="🏘 Top 10 máy chủ Discord hoạt động",
        value=guilds_text,
        inline=False
    )

    # Backup
    embed.add_field(
        name="📦 Sao lưu & dung lượng",
        value=(
            f"• Số file backup (manual): **{backup_count}**\n"
            f"• data.json: {size_info}\n"
            f"• Giới hạn giữ: 10 bản gần nhất"
        ),
        inline=False
    )

    await ctx.reply(embed=embed, mention_author=False)







# =============================================================

@bot.command(name="testdata")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_otestdata(ctx):
    """
    Kiểm tra nhanh dữ liệu hiện đang load trong volume:
    - Số người chơi
    - Liệt kê một vài ID đầu tiên
    Giúp xác nhận bot đang đọc đúng /data/data.json sau restore.
    """
    data = load_data()
    users = data.get("users", {})
    count_users = len(users)

    # lấy 3 id đầu tiên nếu có
    preview_ids = list(users.keys())[:3]
    if preview_ids:
        sample_text = ", ".join(preview_ids)
    else:
        sample_text = "(không có user nào)"

    msg = (
        f"📦 Hiện bot đang đọc dữ liệu từ volume.\n"
        f"- Số người chơi ghi nhận: **{count_users}**\n"
        f"- Một vài ID đầu tiên: {sample_text}\n"
        f"- File data.json thực tế nằm tại BASE_DATA_DIR: {BASE_DATA_DIR}"
    )

    await ctx.reply(msg, mention_author=False)


@bot.command(name="khoiphucfile")
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_khoiphucfile(ctx):
    """
    KHÔI PHỤC DỮ LIỆU TỪ FILE (DATA.JSON)
    -------------------------------------
    Dùng khi dữ liệu quá lớn, không thể dán JSON trực tiếp qua Discord.

    Cách dùng:
    1️⃣ Gõ: okhoiphucfile
    2️⃣ Gửi kèm (attach) file data.json trong cùng tin nhắn hoặc reply lại tin bot này bằng file đó.
    3️⃣ Bot sẽ tải file đó, backup volume hiện tại, rồi ghi đè /data/data.json.
    """

    # Nếu không có file đính kèm
    if not ctx.message.attachments:
        await ctx.reply(
            "📂 Vui lòng gửi file `data.json` trong cùng tin nhắn hoặc reply lại với file đó để khôi phục dữ liệu.",
            mention_author=False
        )
        return

    attach = ctx.message.attachments[0]
    filename = attach.filename.lower()

    # Kiểm tra tên file
    if not filename.endswith(".json"):
        await ctx.reply("❗ File phải có định dạng .json", mention_author=False)
        return

    # Đường dẫn volume thực tế
    json_path = os.path.join(BASE_DATA_DIR, "data.json")

    # Bước 1: tải file về bộ nhớ tạm
    try:
        file_bytes = await attach.read()
        json_text = file_bytes.decode("utf-8")
        new_data = json.loads(json_text)
        if not isinstance(new_data, dict):
            raise ValueError("Cấu trúc JSON không hợp lệ.")
    except Exception as e:
        await ctx.reply(f"❌ Không đọc được file JSON. Lỗi: {e}", mention_author=False)
        return

    # Bước 2: Backup dữ liệu hiện tại
    try:
        current_data = load_data()
        snapshot_data_v16(current_data, tag="before-import-file", subkey="manual")
    except Exception as e:
        await ctx.reply(f"⚠️ Không thể backup dữ liệu hiện tại: {e}", mention_author=False)

    # Bước 3: Ghi đè data.json trong volume
    try:
        save_data(new_data)
    except Exception as e:
        await ctx.reply(f"❌ Ghi dữ liệu thất bại: {e}", mention_author=False)
        return

    # Bước 4: Xác nhận
    after_data = load_data()
    count_users = len(after_data.get("users", {}))

    await ctx.reply(
        f"✅ ĐÃ KHÔI PHỤC DỮ LIỆU TỪ FILE `{filename}` THÀNH CÔNG!\n"
        f"- Tổng số người chơi: **{count_users}**\n"
        f"- Dữ liệu đã được ghi vào volume tại `{json_path}`.\n"
        f"👉 Hãy chạy `otestdata` để kiểm tra lại.",
        mention_author=False
    )

# ==================SAO LƯU==================================





@bot.command(name="saoluu")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_osaoluu(ctx):
    """
    Tạo backup thủ công (manual) và tự động dọn backup manual cũ,
    chỉ giữ lại MAX_MANUAL_BACKUPS bản mới nhất.
    """
    data = load_data()
    try:
        path = snapshot_data_v16(data, tag="manual", subkey="manual")

        # Sau khi tạo backup mới, dọn bớt backup manual cũ nếu quá giới hạn
        try:
            _cleanup_old_backups_limit()
        except Exception as cle:
            print(f"[AUTO-BACKUP-CLEANUP] Lỗi khi dọn sau osaoluu: {cle}")

        await ctx.reply(
            f"✅ Đã tạo bản sao lưu: `{os.path.basename(path)}`\n"
            f"🔁 Hệ thống giữ tối đa {MAX_MANUAL_BACKUPS} bản manual mới nhất.",
            mention_author=False
        )

    except Exception as e:
        await ctx.reply(
            f"⚠️ Sao lưu thất bại: {e}",
            mention_author=False
        )


# ===================SAO LƯU========================





# ===============================================
# 🔄 TỰ ĐỘNG SAO LƯU DỮ LIỆU + THÔNG BÁO KÊNH (CÓ CẤU HÌNH)
# ===============================================
from discord.ext import tasks
import time, os, glob
from datetime import datetime

# 🧭 Kênh Discord để gửi thông báo
AUTO_BACKUP_CHANNEL_ID = 821066331826421840  


# ⏱ Thời gian mặc định
AUTO_BACKUP_INTERVAL_MINUTES = 1500   # 24 giờ sao lưu 1 lần
AUTO_REPORT_INTERVAL_MINUTES = 60    # báo tối đa mỗi 60 phút (bạn giữ như cũ)

# Bộ nhớ runtime
_last_report_ts = 0
_auto_backup_started = False

@tasks.loop(minutes=1)
async def auto_backup_task():
    """
    Vòng lặp chạy mỗi 1 phút.
    - Đếm phút → đủ 720 phút (12h) thì backup.
    - Backup xong dọn bớt → chỉ giữ 2 file mới nhất.
    """
    global _last_report_ts
    global AUTO_BACKUP_INTERVAL_MINUTES
    global AUTO_REPORT_INTERVAL_MINUTES

    # setup biến đếm phút từ lần backup gần nhất
    if not hasattr(auto_backup_task, "_minutes_since_backup"):
        auto_backup_task._minutes_since_backup = 0

    auto_backup_task._minutes_since_backup += 1

    # chưa đủ thời gian -> thôi
    if auto_backup_task._minutes_since_backup < AUTO_BACKUP_INTERVAL_MINUTES:
        return

    # đủ thời gian → reset đếm
    auto_backup_task._minutes_since_backup = 0

    try:
        # 1) tạo backup
        data_now = load_data()
        filename = snapshot_data_v16(data_now, tag="auto", subkey="manual")

        # 2) dọn bớt backup cũ, chỉ giữ 2 cái mới nhất
        # đoán thư mục snapshot nằm ở đây, nếu bạn lưu chỗ khác thì đổi lại
        SNAP_DIRS = [
            "/mnt/volume/snapshots",
            "/mnt/volume/backups",
        ]
        for snap_dir in SNAP_DIRS:
            if os.path.isdir(snap_dir):
                files = sorted(
                    glob.glob(os.path.join(snap_dir, "*.json")),
                    key=os.path.getmtime
                )
                # giữ lại 2 cái mới nhất
                for f in files[:-2]:
                    try:
                        os.remove(f)
                    except Exception as e:
                        print(f"[AUTO-BACKUP] ⚠️ Không xóa được {f}: {e}")

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"✅ **Tự động sao lưu dữ liệu thành công!**\n"
            f"📦 File: `{os.path.basename(filename)}`\n"
            f"🕐 Thời gian backup: {current_time}\n"
            f"⏱️ Chu kỳ backup hiện tại: {AUTO_BACKUP_INTERVAL_MINUTES} phút/lần\n"
            f"📣 Chu kỳ báo cáo hiện tại: {AUTO_REPORT_INTERVAL_MINUTES} phút/lần"
        )
        print(f"[AUTO-BACKUP] {msg}")

        # 3) báo kênh nếu tới giờ
        now_ts = time.time()
        elapsed_since_report_min = (now_ts - _last_report_ts) / 60.0

        if elapsed_since_report_min >= AUTO_REPORT_INTERVAL_MINUTES:
            try:
                channel = bot.get_channel(AUTO_BACKUP_CHANNEL_ID)
                if channel:
                    await channel.send(msg)
                else:
                    print("[AUTO-BACKUP] ⚠️ Không tìm thấy kênh Discord để gửi thông báo.")
            except Exception as e:
                print(f"[AUTO-BACKUP] ⚠️ Lỗi gửi thông báo Discord: {e}")

            _last_report_ts = now_ts

    except Exception as e:
        print(f"[AUTO-BACKUP] ❌ Lỗi khi tạo backup tự động: {e}")


@auto_backup_task.before_loop
async def before_auto_backup():
    # đợi bot kết nối xong discord
    await bot.wait_until_ready()
    # khởi tạo lại bộ đếm phút
    auto_backup_task._minutes_since_backup = 0
    # lần đầu start thì cho phép báo ngay
    global _last_report_ts
    _last_report_ts = 0
    print("[AUTO-BACKUP] Vòng lặp chuẩn bị chạy (mỗi 1 phút tick).")



# ===============================================
# 🔄 TỰ ĐỘNG SAO LƯU DỮ LIỆU + THÔNG BÁO KÊNH (CÓ CẤU HÌNH)
# ===============================================













# =================LỆNH THAY ĐỔI THỜI GIAN SAO LƯU TỰ ĐỘNG======================


@bot.command(name="thoigiansaoluu", aliases=["backupconfig"])
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_thoigiansaoluu(ctx, backup_minutes: int = None, report_minutes: int = None):
    """
    Cấu hình hệ thống auto backup:
    - backup_minutes: mỗi bao nhiêu phút thì tạo 1 bản backup mới.
    - report_minutes: mỗi bao nhiêu phút thì cho phép gửi 1 thông báo vào kênh.

    Ví dụ:
    `thoigiansaoluu 10 60`
    -> Sao lưu mỗi 10 phút
    -> Chỉ báo lên kênh mỗi 60 phút (ít spam thông báo)

    Nếu bạn gọi không đủ tham số, bot sẽ chỉ hiển thị cấu hình hiện tại.
    """

    global AUTO_BACKUP_INTERVAL_MINUTES
    global AUTO_REPORT_INTERVAL_MINUTES

    # Nếu không truyền tham số -> chỉ show cấu hình hiện tại
    if backup_minutes is None or report_minutes is None:
        await ctx.reply(
            "📊 Cấu hình Auto Backup hiện tại:\n"
            f"- Chu kỳ backup: {AUTO_BACKUP_INTERVAL_MINUTES} phút/lần\n"
            f"- Chu kỳ báo cáo: {AUTO_REPORT_INTERVAL_MINUTES} phút/lần\n"
            "👉 Dùng: `thoigiansaoluu <phút_backup> <phút_báo>`\n"
            "Ví dụ: `thoigiansaoluu 10 60`",
            mention_author=False
        )
        return

    # Validate
    if backup_minutes < 1:
        await ctx.reply("❗ Chu kỳ backup phải >= 1 phút.", mention_author=False)
        return
    if report_minutes < 1:
        await ctx.reply("❗ Chu kỳ báo cáo phải >= 1 phút.", mention_author=False)
        return

    # Cập nhật giá trị
    AUTO_BACKUP_INTERVAL_MINUTES = backup_minutes
    AUTO_REPORT_INTERVAL_MINUTES = report_minutes

    # reset bộ đếm phút để áp dụng ngay
    if hasattr(auto_backup_task, "_minutes_since_backup"):
        auto_backup_task._minutes_since_backup = 0

    await ctx.reply(
        "✅ ĐÃ CẬP NHẬT CẤU HÌNH AUTO BACKUP!\n"
        f"- Sao lưu mỗi **{AUTO_BACKUP_INTERVAL_MINUTES} phút/lần**\n"
        f"- Gửi thông báo tối đa mỗi **{AUTO_REPORT_INTERVAL_MINUTES} phút/lần**\n"
        "📦 Lưu ý: Bot sẽ áp dụng cấu hình mới ngay lập tức.",
        mention_author=False
    )

# =================LỆNH THAY ĐỔI THỜI GIAN SAO LƯU TỰ ĐỘNG======================







@bot.command(name="listbackup")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_olistbackup(ctx, limit: int = 10):
    recents = list_recent_backups_v16(limit=limit)
    if not recents:
        return await ctx.reply(
            "Không tìm thấy bản sao lưu nào.",
            mention_author=False
        )
    lines = ["**Các bản sao lưu gần đây:**"]
    for ts, key, path in recents:
        base = os.path.basename(path)
        lines.append(f"- `{base}` — **{key}**")
    await ctx.reply("\n".join(lines), mention_author=False)

@bot.command(name="xemsaoluu")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_oxemsaoluu(ctx):
    st = total_backup_stats_v16()
    mb = st["bytes"] / (1024*1024) if st["bytes"] else 0.0
    latest = os.path.basename(st["latest"]) if st["latest"] else "—"
    msg = (
        f"**Thống kê backup**\n"
        f"- Số file: **{st['files']}**\n"
        f"- Dung lượng: **{mb:.2f} MB**\n"
        f"- Gần nhất: `{latest}`"
    )
    await ctx.reply(msg, mention_author=False)

@bot.command(name="batanh")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_batanh(ctx, mode: str = None):
    data = load_data()
    cfg = data.setdefault("config", {})
    if mode is None:
        status = "BẬT" if cfg.get("images_enabled", True) else "TẮT"
        await ctx.reply(
            f"Hiển thị ảnh hiện tại: {status}",
            mention_author=False
        )
        return
    m = (mode or "").strip().lower()
    if m in ("on","bật","bat","enable","enabled","true","1"):
        cfg["images_enabled"] = True
        save_data(data)
        await ctx.reply(
            "✅ Đã BẬT hiển thị ảnh.",
            mention_author=False
        )
        return
    if m in ("off","tắt","tat","disable","disabled","false","0"):
        cfg["images_enabled"] = False
        save_data(data)
        await ctx.reply(
            "✅ Đã TẮT hiển thị ảnh.",
            mention_author=False
        )
        return
    await ctx.reply(
        "Dùng: `obatanh on` hoặc `obatanh off`.",
        mention_author=False
    )

@bot.command(name="addtien")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_addtien(ctx, member: discord.Member, so: str):
    try:
        amount = int(str(so).replace(",", "").strip())
        if amount <= 0:
            raise ValueError()
    except Exception:
        await ctx.reply(
            "⚠️ Số lượng không hợp lệ. Ví dụ: `oaddtien @user 1,000,000`.",
            mention_author=False
        )
        return
    data = load_data()
    u, path = _get_user_ref(data, member)
    bal = get_balance(u)
    set_balance(u, bal + amount)
    save_data(data)
    await ctx.reply(
        f"✅ Cộng `{format_num(amount)}` NP cho `{member.display_name}` — Tổng: `{format_num(get_balance(u))}`",
        mention_author=False
    )

@bot.command(name="addruong")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_addruong(ctx, member: discord.Member, pham: str, so: str):
    pham = pham.strip().upper()
    if pham not in {"D","C","B","A","S"}:
        await ctx.reply(
            "Phẩm rương không hợp lệ. Dùng: D/C/B/A/S",
            mention_author=False
        )
        return
    try:
        amount = int(str(so).replace(",", "").strip())
        if amount <= 0:
            raise ValueError()
    except Exception:
        await ctx.reply(
            "⚠️ Số lượng không hợp lệ. Ví dụ: `oaddruong @user S 3`.",
            mention_author=False
        )
        return
    if amount > 100:
        await ctx.reply(
            "⚠️ Tối đa **10 rương** mỗi lần.",
            mention_author=False
        )
        return
    data = load_data()
    u, path = _get_user_ref(data, member)
    r = ensure_rungs(u)
    r[pham] = int(r.get(pham, 0)) + amount
    save_data(data)
    await ctx.reply(
        f"✅ Đã cấp `{format_num(amount)}` rương **{pham}** cho `{member.display_name}` — Tổng: `{format_num(r[pham])}`",
        mention_author=False
    )

@bot.command(name="xtien")
@owner_only()
@commands.cooldown(1, 3, commands.BucketType.user)
async def cmd_oxtien(ctx, member: discord.Member):
    data = load_data()
    u, path = _get_user_ref(data, member)
    keys = {k: u[k] for k in ("ngan_phi","ngan_phieu") if k in u}
    rinfo = u.get("rungs", {})
    bal = int(u.get("ngan_phi", u.get("ngan_phieu", 0)))
    await ctx.reply(
        f"🧩 Path: **{path}**\n"
        f"💰 Số dư: **{format_num(bal)}** (keys: {keys})\n"
        f"🎁 Rương: {rinfo}",
        mention_author=False
    )


#===========PHỤC HỒI==========================
@bot.command(name="phuchoi")
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_phuchoi(ctx, filename: str = None):
    # Bắt buộc phải chỉ định file .json
    if not filename:
        await ctx.reply(
            "⚠️ Dùng đúng cú pháp:\n"
            "`ophuchoi <tên_file.json>`\n"
            "Ví dụ: `ophuchoi data.json.v16.auto.20251030-153211.json`",
            mention_author=False
        )
        return

    data = load_data()

    # backup trước khi restore
    try:
        snapshot_data_v16(data, tag="before-restore", subkey="before_restore")
    except Exception:
        pass

    BACKUP_DIR_ROOT = os.path.join(BASE_DATA_DIR, "backups")
    cand = os.path.join(BACKUP_DIR_ROOT, filename)

    if not os.path.isfile(cand):
        await ctx.reply(
            "❌ Không tìm thấy file backup với tên đó. "
            "Hãy dùng `olistbackup` để xem danh sách file hợp lệ.",
            mention_author=False
        )
        return

    try:
        with open(cand, "r", encoding="utf-8") as f:
            restored = json.load(f)
        save_data(restored)
        await ctx.reply(
            f"✅ ĐÃ KHÔI PHỤC DỮ LIỆU TỪ `{filename}` THÀNH CÔNG.",
            mention_author=False
        )
    except Exception as e:
        await ctx.reply(
            f"❌ Khôi phục thất bại: {e}",
            mention_author=False
        )
#===========PHỤC HỒI==========================



#===========resetdata========================


@bot.command(name="resetdata")
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_resetdata(ctx):
    data = load_data()
    try:
        snapshot_data_v16(data, tag="before-resetdata", subkey="before_resetdata")
    except Exception:
        pass
    new_data = {}
    if "guild_settings" in data:
        new_data["guild_settings"] = data["guild_settings"]
    if "config" in data and isinstance(data["config"], dict):
        new_data["config"] = data["config"]
    if "server_cfg" in data and isinstance(data["server_cfg"], dict):
        new_data["server_cfg"] = data["server_cfg"]
    save_data(new_data)
    await ctx.reply(
        "✅ Đã reset dữ liệu (giữ cấu hình kênh & thiết lập ảnh).",
        mention_author=False
    )

@bot.command(name="resetuser")
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_resetuser(ctx, member: discord.Member):
    data = load_data()
    try:
        snapshot_data_v16(data, tag="before-resetuser", subkey="before_resetuser")
    except Exception:
        pass
    users = data.setdefault("users", {})
    uid = str(member.id)
    had = users.pop(uid, None)
    save_data(data)
    if had is not None:
        await ctx.reply(
            f"✅ Đã reset dữ liệu: `{member.display_name}`.",
            mention_author=False
        )
    else:
        await ctx.reply(
            f"Người chơi `{member.display_name}` chưa có dữ liệu.",
            mention_author=False
        )








# =================== BACKUP & XUẤT DỮ LIỆU HOÀN CHỈNH ===================

# ⚙️ Giữ lại tối đa 10 file backup mới nhất cho mỗi loại (manual, pre-save, startup, ...)
MAX_BACKUPS_PER_DIR = 2

def _cleanup_old_backups_limit():
    """
    DỌN TOÀN BỘ backup trong mọi thư mục BACKUP_DIRS.
    - Với mỗi thư mục backup (startup, pre-save, manual, ...):
      -> chỉ giữ lại MAX_BACKUPS_PER_DIR file mới nhất
      -> xóa các file cũ hơn (kể cả .sha256)
    - Mục tiêu: không để volume phình tới vài GB.
    """
    for subkey, folder in BACKUP_DIRS.items():
        if not folder or not os.path.isdir(folder):
            continue

        try:
            pattern = os.path.join(folder, "data.json.v*.json")
            files = glob(pattern)

            if len(files) <= MAX_BACKUPS_PER_DIR:
                continue

            files_sorted_new_first = sorted(files, reverse=True)
            keep = set(files_sorted_new_first[:MAX_BACKUPS_PER_DIR])
            to_delete = [f for f in files_sorted_new_first if f not in keep]

            deleted = 0
            for f in to_delete:
                try:
                    os.remove(f)
                except Exception:
                    pass
                sha_path = f + ".sha256"
                if os.path.exists(sha_path):
                    try:
                        os.remove(sha_path)
                    except Exception:
                        pass
                deleted += 1

            print(f"[AUTO-BACKUP-CLEANUP] [{subkey}] Xóa {deleted} file cũ, giữ {MAX_BACKUPS_PER_DIR} file mới nhất.")

        except Exception as e:
            print(f"[AUTO-BACKUP-CLEANUP] Lỗi dọn thư mục {subkey}: {e}")



# ================== SAO LƯU AN TOÀN ==================

@bot.command(name="saoluuantoan", aliases=["osaoluuantoan"])
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_osaoluu_antoan(ctx):
    """
    Tạo ngay 1 bản backup mới nhất (manual) trước khi dọn dẹp.
    Dùng khi sắp xóa backup cũ để chắc chắn luôn còn 1 bản khôi phục gần nhất.
    """
    data_now = load_data()
    try:
        backup_path = snapshot_data_v16(data_now, tag="manual-before-clean", subkey="manual")

        try:
            _cleanup_old_backups_limit()
        except Exception as cle:
            print(f"[BACKUP CLEANUP] Lỗi dọn backup sau khi tạo bản an toàn: {cle}")

        await ctx.reply(
            f"✅ Đã tạo bản backup an toàn: `{os.path.basename(backup_path)}`\n"
            f"📦 Đã dọn bớt backup cũ, giữ tối đa 10 bản mỗi loại.",
            mention_author=False
        )
    except Exception as e:
        await ctx.reply(
            f"❌ Sao lưu an toàn thất bại: {e}",
            mention_author=False
        )



# ================== XOÁ BACKUP (THỦ CÔNG + TỰ ĐỘNG) ==================
from discord.ext import tasks
import os, shutil

def run_xoabackup():
    """
    GIẢI PHÓNG DUNG LƯỢNG.
    Xóa toàn bộ thư mục backups (startup / pre-save / manual / ...).
    KHÔNG xoá data.json chính.
    """
    backup_root = os.path.join(BASE_DATA_DIR, "backups")
    try:
        if os.path.isdir(backup_root):
            shutil.rmtree(backup_root)   # 👈 y như bản cũ của bạn
            print(f"[XOABACKUP] Đã xoá toàn bộ thư mục: {backup_root}")
        os.makedirs(backup_root, exist_ok=True)
        print("[XOABACKUP] Đã tạo lại thư mục backups rỗng.")
    except Exception as e:
        print(f"[XOABACKUP] Lỗi khi xoá backup: {e}")

@bot.command(name="xoabackup", aliases=["oxoabackup"])
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_xoabackup(ctx):
    run_xoabackup()
    await ctx.reply(
        "🧹 Đã xoá toàn bộ backup cũ (startup / pre-save / manual / ...).\n"
        "📦 File dữ liệu chính `data.json` vẫn còn nguyên.",
        mention_author=False
    )

@tasks.loop(minutes=10)
async def auto_xoabackup_task():
    await bot.wait_until_ready()
    print("[AUTO-XOABACKUP] Dọn backup tự động...")
    run_xoabackup()
    print("[AUTO-XOABACKUP] Xong.")


# ================== XOÁ TOÀN BỘ BACKUP (THỦ CÔNG + TỰ ĐỘNG) ==================


# ================== XUẤT FILE BACKUP ZIP ==================

@bot.command(name="xuatdata", aliases=["oxuatdata", "backupxuat"])
@owner_only()
@commands.cooldown(1, 30, commands.BucketType.user)
async def cmd_xuatdata(ctx):
    """
    Đóng gói toàn bộ dữ liệu hiện tại (data.json + backups/)
    thành 1 file ZIP và gửi lên Discord để tải về.
    Sau khi gửi xong sẽ xóa file ZIP tạm để không tốn dung lượng.
    """
    import zipfile
    import time

    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    export_name = f"export_{timestamp}.zip"
    export_path = os.path.join(BASE_DATA_DIR, export_name)

    data_file_path = os.path.join(BASE_DATA_DIR, "data.json")
    backups_dir = os.path.join(BASE_DATA_DIR, "backups")

    try:
        with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Ghi file data.json
            if os.path.isfile(data_file_path):
                zf.write(data_file_path, arcname="data.json")

            # Ghi toàn bộ thư mục backups
            if os.path.isdir(backups_dir):
                for root, dirs, files in os.walk(backups_dir):
                    for fname in files:
                        full_path = os.path.join(root, fname)
                        arcname = os.path.relpath(full_path, BASE_DATA_DIR)
                        zf.write(full_path, arcname=arcname)

        await ctx.reply(
            content=(
                "📦 Đã tạo file sao lưu tổng hợp (data.json + backups/)\n"
                "⬇ Tải file ZIP này về máy của bạn và lưu cẩn thận.\n"
                "⚠ Ai có file này có thể xem toàn bộ dữ liệu bot, không nên chia sẻ công khai."
            ),
            file=discord.File(export_path, filename=export_name),
            mention_author=False
        )

    except Exception as e:
        await ctx.reply(f"❌ Không thể xuất data: {e}", mention_author=False)
        try:
            if os.path.exists(export_path):
                os.remove(export_path)
        except:
            pass
        return

    # Xóa file ZIP tạm sau khi gửi thành công
    try:
        if os.path.exists(export_path):
            os.remove(export_path)
    except Exception as cleanup_err:
        print(f"[WARN] Không xoá được file xuất tạm: {cleanup_err}")

# =================== /BACKUP & XUẤT DỮ LIỆU ===================


# ====================================================================================================================================
# 🧍 QUẢN LÝ — CHỦ BOT (module-style)
# ====================================================================================================================================
# ====================================================================================================================================
# 🧍 KẾT TRÚC KHU VỰC CẤU HÌNH BOT CÁC THỨ Ở BÊN DƯỚI LÀ CÁC LỆNH TÍNH NĂNG
# ====================================================================================================================================
# ====================================================================================================================================
# 🧍 KẾT TRÚC KHU VỰC CẤU HÌNH BOT CÁC THỨ Ở BÊN DƯỚI LÀ CÁC LỆNH TÍNH NĂNG
# ====================================================================================================================================
# ====================================================================================================================================
# 🧍 KẾT TRÚC KHU VỰC CẤU HÌNH BOT CÁC THỨ Ở BÊN DƯỚI LÀ CÁC LỆNH TÍNH NĂNG
# ====================================================================================================================================


# -----------------------
# 🎁 NHIỆM VỤ CỘNG ĐỒNG
# -----------------------
MAIN_GUILD_ID          = 1413785749215510680  # server chính của bạn
MISSION_CHANNEL_ID     = 1431507301990269061  # kênh có bài nhiệm vụ
MISSION_MESSAGE_ID     = 1433051721495478353  # ID bài nhiệm vụ
REWARD_CHEST_RARITY    = "S"                  # loại rương tặng

async def check_community_requirements(bot, user_id: int):
    """
    Kiểm tra xem user đã làm nhiệm vụ cộng đồng chưa.

    Trả về (status, reason):
    - (True,  None): đủ điều kiện -> cho rương
    - (False, "lý do"): chưa đủ điều kiện -> chưa cho
    - (None, "lý do"): bot không thể tự kiểm tra -> cần admin duyệt tay
    """

    # 1. bot phải thấy guild chính
    guild = bot.get_guild(MAIN_GUILD_ID)
    if guild is None:
        return (None, "Bot không ở trong máy chủ chính hoặc không có quyền xem máy chủ chính.")

    # 2. user phải là member trong guild chính
    member = guild.get_member(user_id)
    if member is None:
        return (False, "Bạn chưa tham gia máy chủ chính.")

    # 3. bot phải thấy message nhiệm vụ
    channel = bot.get_channel(MISSION_CHANNEL_ID)
    if channel is None:
        return (None, "Bot không thể truy cập kênh nhiệm vụ (thiếu quyền xem kênh).")

    try:
        message = await channel.fetch_message(MISSION_MESSAGE_ID)
    except Exception:
        return (None, "Bot không thể đọc bài nhiệm vụ (thiếu quyền đọc lịch sử tin nhắn).")

    # 4. kiểm tra user đã react icon chưa
    reacted = False
    try:
        for reaction in message.reactions:
            try:
                async for u in reaction.users():
                    if u.id == user_id:
                        reacted = True
                        break
                if reacted:
                    break
            except Exception:
                # nếu fail 1 reaction thì bỏ qua reaction đó, thử reaction khác
                pass
    except Exception:
        return (None, "Bot không thể xem ai đã thả icon vào bài nhiệm vụ (thiếu quyền xem reaction).")

    if not reacted:
        return (False, "Bạn chưa bấm icon trong bài nhiệm vụ.")

    # -> join server chính + react bài -> OK
    return (True, None)




# ====================================================================================================================================
# 🧍 
# ====================================================================================================================================

@bot.command(name="onhanthuong", aliases=["nhanthuong"])
async def onhanthuong_cmd(ctx):
    uid = str(ctx.author.id)

    # lấy data toàn cục + object người chơi
    data = ensure_user(uid)
    player = data["users"][uid]

    # =========================
    # 1. Kiểm tra kênh hợp lệ (tránh spam ngoài kênh game)
    # =========================
    # Hệ thống của bạn đã có global_channel_check nên thật ra bước này không bắt buộc.
    # Mình vẫn giữ try/except NameError để không crash nếu hàm không tồn tại.
    try:
        if not is_channel_allowed(ctx):
            await ctx.reply(
                "❗ Lệnh này chỉ dùng ở kênh game đã được cấu hình bằng lệnh osetbot.",
                mention_author=False
            )
            return
    except NameError:
        pass

    # đảm bảo có các trường dùng cho nhiệm vụ
    if "reward_community_pending" not in player:
        player["reward_community_pending"] = False
    if "reward_community_claimed" not in player:
        player["reward_community_claimed"] = False
    if "rungs" not in player:
        player["rungs"] = {}
    if REWARD_CHEST_RARITY not in player["rungs"]:
        player["rungs"][REWARD_CHEST_RARITY] = 0

    # =========================
    # 2. Gửi thông báo công khai
    # =========================
    public_msg = (
        "📩 Hệ thống đã gửi hướng dẫn nhận quà vào tin nhắn riêng.\n"
        "Vui lòng kiểm tra tin nhắn riêng của bot."
    )

    public_sent = False
    try:
        await ctx.reply(public_msg, mention_author=False)
        public_sent = True
    except Exception:
        pass

    # =========================
    # 3. Cập nhật hoạt động
    # =========================
    try:
        touch_user_activity(ctx, player)
    except Exception:
        pass

    # =========================
    # 4. Nếu user đã claim rồi
    # =========================
    if player.get("reward_community_claimed", False):
        embed_claimed = discord.Embed(
            title="❌ BẠN ĐÃ NHẬN PHẦN THƯỞNG",
            description=(
                "Bạn đã nhận **Rương S** trước đó.\n"
                "Phần thưởng cộng đồng chỉ nhận được **một lần duy nhất** cho mỗi tài khoản.\n\n"
                "Chúc tu luyện thuận lợi."
            ),
            color=discord.Color.dark_grey()
        )
        try:
            await ctx.author.send(embed=embed_claimed)
        except discord.Forbidden:
            if not public_sent:
                await ctx.reply(
                    "❗ Bot không thể gửi tin nhắn riêng cho bạn. "
                    "Vui lòng bật nhận tin nhắn riêng từ thành viên trong server rồi thử lại `onhanthuong`.",
                    mention_author=False
                )
        return

    # =========================
    # 5. Nếu chưa pending -> lần đầu gọi lệnh
    # =========================
    if not player.get("reward_community_pending", False):
        player["reward_community_pending"] = True

        guide_embed = discord.Embed(
            title="🎁 PHẦN THƯỞNG CỘNG ĐỒNG — RƯƠNG S",
            description=(
                "Bạn có thể nhận **1 Rương S (Truyền Thuyết) + 500,000 Ngân Phiếu** miễn phí bằng cách hoàn thành các bước sau:\n\n"
                "1. Tham gia máy chủ chính của game:\n"
                "   https://discord.gg/ZrcgXGAAWJ\n\n"
                "2. Vào bài nhiệm vụ và bấm 1 icon bất kỳ:\n"
                "   https://discordapp.com/channels/1413785749215510680/1431507301990269061/1433051721495478353\n\n"
                "Sau khi hoàn thành, quay lại server và gõ lại lệnh `onhanthuong` để nhận **Rương S x1 Ngân Phiếu x 500,000**.\n\n"


                "_Bạn đã được ghi vào danh sách chờ nhận thưởng._"
            ),
            color=discord.Color.blue()
        )

        # lưu lại trạng thái pending
        save_data(data)

        try:
            await ctx.author.send(embed=guide_embed)
        except discord.Forbidden:
            await ctx.reply(
                "❗ Bot không thể gửi tin nhắn riêng cho bạn. "
                "Vui lòng bật nhận tin nhắn riêng từ thành viên trong server rồi gõ lại `onhanthuong`.",
                mention_author=False
            )
        return

    # =========================
    # 6. Đến đây: đã pending nhưng chưa claim -> kiểm tra điều kiện
    # =========================
    status, reason = await check_community_requirements(bot, int(uid))

    # 6A. ĐỦ điều kiện -> phát thưởng
    if status is True:
        # đảm bảo tồn tại kho rương
        if "rungs" not in player:
            player["rungs"] = {}
        if REWARD_CHEST_RARITY not in player["rungs"]:
            player["rungs"][REWARD_CHEST_RARITY] = 0

        # ====== THƯỞNG RƯƠNG S ======
        player["rungs"][REWARD_CHEST_RARITY] += 1

        # ====== THƯỞNG THÊM NGÂN PHIẾU ======
        BONUS_NP = 500_000  # <- bạn muốn bao nhiêu chỉnh ở đây
        # đảm bảo field ngan_phi tồn tại và là int
        try:
            player["ngan_phi"] = int(player.get("ngan_phi", 0)) + BONUS_NP
        except Exception:
            # nếu vì lý do gì đó field hư kiểu, ép lại
            player["ngan_phi"] = BONUS_NP

        # cập nhật thống kê kiếm tiền tổng
        player.setdefault("stats", {})
        player["stats"]["ngan_phi_earned_total"] = int(
            player["stats"].get("ngan_phi_earned_total", 0)
        ) + BONUS_NP

        # đánh dấu đã nhận
        player["reward_community_claimed"] = True
        player["reward_community_pending"] = False

        save_data(data)

        # ====== DM thông báo thành công ======
        embed_success = discord.Embed(
            title="✅ HOÀN THÀNH NHIỆM VỤ CỘNG ĐỒNG",
            description=(
                "Bạn đã hoàn thành nhiệm vụ cộng đồng.\n\n"
                f"Phần thưởng của bạn:\n"
                f"- Rương {REWARD_CHEST_RARITY} x1 🎁\n"
                f"- {format_num(BONUS_NP)} Ngân Phiếu 💰\n\n"
                "Cảm ơn bạn đã tham gia máy chủ chính và tương tác trong bài nhiệm vụ.\n\n"
                "_Phần thưởng này đã được khóa. Bạn sẽ không thể nhận lại lần nữa._"
            ),
            color=discord.Color.green()
        )

        try:
            await ctx.author.send(embed=embed_success)
        except discord.Forbidden:
            await ctx.reply(
                f"✅ Bạn đã nhận Rương {REWARD_CHEST_RARITY} x1 và {format_num(BONUS_NP)} Ngân Phiếu. "
                "(Bot không thể gửi DM do bạn chặn tin nhắn.)",
                mention_author=False
            )
        return

    # 6B. CHƯA ĐỦ điều kiện (thiếu join server hoặc chưa react)
    if status is False:
        embed_not_ready = discord.Embed(
            title="⏳ CHƯA HOÀN THÀNH",
            description=(
                "Hệ thống vẫn chưa thể xác minh bạn đã hoàn thành nhiệm vụ.\n\n"
                f"{reason}\n\n"
                "Bạn cần:\n"
                "1. Tham gia máy chủ chính:\n"
                "   https://discord.gg/ZrcgXGAAWJ\n\n"
                "2. Vào bài nhiệm vụ và bấm 1 icon bất kỳ:\n"
                "   https://discordapp.com/channels/1413785749215510680/1431507301990269061/1433051721495478353\n\n"
                "Sau đó, hãy gõ lại `onhanthuong` để nhận **Rương S x1**."
            ),
            color=discord.Color.orange()
        )
        try:
            await ctx.author.send(embed=embed_not_ready)
        except discord.Forbidden:
            await ctx.reply(
                "⏳ Bạn chưa đủ điều kiện nhận quà. "
                "Hãy tham gia server chính và bấm icon trong bài nhiệm vụ, rồi gõ lại `onhanthuong`. "
                "(Bot không thể gửi DM vì bạn chặn tin nhắn.)",
                mention_author=False
            )
        return

    # 6C. BOT KHÔNG THỂ TỰ XÁC MINH (thiếu quyền / không thấy kênh / không đọc reaction)
    embed_manual = discord.Embed(
        title="⏳ CHƯA THỂ XÁC MINH TỰ ĐỘNG",
        description=(
            "Hệ thống hiện không thể tự động xác minh nhiệm vụ của bạn "
            "(có thể bot không có quyền xem thành viên hoặc xem danh sách reaction trong kênh nhiệm vụ).\n\n"
            "Nếu bạn đã:\n"
            " - Tham gia máy chủ chính\n"
            " - Bấm icon trong bài nhiệm vụ\n\n"
            "Hãy ping Admin để được duyệt thủ công và nhận **Rương S x1**.\n\n"
            f"Chi tiết kỹ thuật: {reason if reason else 'Không rõ nguyên nhân'}"
        ),
        color=discord.Color.gold()
    )

    try:
        await ctx.author.send(embed=embed_manual)
    except discord.Forbidden:
        await ctx.reply(
            "⏳ Bot không thể tự xác minh và cũng không thể gửi DM cho bạn. "
            "Hãy ping Admin để được hỗ trợ nhận Rương S.",
            mention_author=False
        )
    return

# ====================================================================================================================================
# 🧍 
# ====================================================================================================================================


# -----------------------
# 🔔 ĐĂNG KÝ THÔNG BÁO BẰNG REACTION
# Người chơi react vào bài nhiệm vụ -> bot gán role "Thông Báo Sự Kiện"
# Người chơi bỏ react -> bot gỡ role
# -----------------------

SUBSCRIBE_ROLE_NAME = "Thông Báo Sự Kiện"  # bạn đặt đúng tên role trong server

async def _give_sub_role(payload):
    """Thêm role SUBSCRIBE_ROLE_NAME cho người đã react."""
    # đảm bảo đúng bài nhiệm vụ
    if (
        payload.guild_id != MAIN_GUILD_ID or
        payload.channel_id != MISSION_CHANNEL_ID or
        payload.message_id != MISSION_MESSAGE_ID
    ):
        return

    guild = bot.get_guild(MAIN_GUILD_ID)
    if guild is None:
        return

    # bỏ qua bot tự react
    if payload.user_id == bot.user.id:
        return

    member = guild.get_member(payload.user_id)
    if member is None:
        return

    # tìm role theo tên
    role = discord.utils.get(guild.roles, name=SUBSCRIBE_ROLE_NAME)
    if role is None:
        # bạn CHƯA tạo role này trong server -> bot chịu, không gán được
        return

    # bot phải có quyền Manage Roles và role bot phải ở cao hơn role này
    try:
        if role not in member.roles:
            await member.add_roles(role, reason="Đăng ký nhận thông báo sự kiện")
    except discord.Forbidden:
        # bot không có quyền gán role (cần Manage Roles và thứ tự role đúng)
        pass
    except Exception:
        pass

async def _remove_sub_role(payload):
    """Gỡ role SUBSCRIBE_ROLE_NAME nếu người chơi bỏ reaction."""
    if (
        payload.guild_id != MAIN_GUILD_ID or
        payload.channel_id != MISSION_CHANNEL_ID or
        payload.message_id != MISSION_MESSAGE_ID
    ):
        return

    guild = bot.get_guild(MAIN_GUILD_ID)
    if guild is None:
        return

    # bỏ qua bot
    if payload.user_id == bot.user.id:
        return

    member = guild.get_member(payload.user_id)
    if member is None:
        return

    role = discord.utils.get(guild.roles, name=SUBSCRIBE_ROLE_NAME)
    if role is None:
        return

    try:
        if role in member.roles:
            await member.remove_roles(role, reason="Hủy đăng ký thông báo sự kiện")
    except discord.Forbidden:
        pass
    except Exception:
        pass

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """
    Khi ai đó bấm icon ở bất kỳ message/public channel,
    payload sẽ chạy qua đây.
    Mình lọc lại 3 ID: guild/channel/message, chỉ xử lý nếu đúng bài nhiệm vụ.
    """
    await _give_sub_role(payload)

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """
    Khi ai đó bỏ icon (unreact), mình gỡ role để họ ngừng nhận ping.
    """
    await _remove_sub_role(payload)

# ====================================================================================================================================
# 🧍 
# ====================================================================================================================================

# ==========================================================
# 🏆 BẢNG XẾP HẠNG (obxh / bxh)
# ==========================================================

def _bxh_safe_user_for_rank(u: dict) -> dict:
    clone = dict(u)

    stats = dict(clone.get("stats", {}))
    clone["stats"] = stats
    stats.setdefault("ol_count", 0)
    stats.setdefault("odt_count", 0)
    stats.setdefault("opened", 0)

    r_raw = clone.get("rungs", {})
    clone["rungs"] = {
        "S": int(r_raw.get("S", 0)),
        "A": int(r_raw.get("A", 0)),
        "B": int(r_raw.get("B", 0)),
        "C": int(r_raw.get("C", 0)),
        "D": int(r_raw.get("D", 0)),
    }

    clone["ngan_phi"] = int(clone.get("ngan_phi", 0))
    return clone

def _bxh_collect_users(data: dict) -> dict[str, dict]:
    prepared = {}
    for uid, raw in data.get("users", {}).items():
        if isinstance(raw, dict):
            prepared[uid] = _bxh_safe_user_for_rank(raw)
    return prepared

def _bxh_total_ruong_alltime(u: dict) -> tuple[int, dict]:
    """
    Tổng Rương Báu (đang giữ + đã mở).
    """
    stats = u["stats"]
    opened_total = int(stats.get("opened", 0))

    r = u["rungs"]
    s = r["S"]; a = r["A"]; b = r["B"]; c = r["C"]; d = r["D"]

    holding_now = s + a + b + c + d
    total_alltime = holding_now + opened_total
    breakdown_now = {"S": s, "A": a, "B": b, "C": c, "D": d}
    return total_alltime, breakdown_now

async def _bxh_display_name(uid: str) -> str:
    try:
        obj = bot.get_user(int(uid))
        if not obj:
            obj = await bot.fetch_user(int(uid))
        if obj:
            return obj.display_name or obj.name
    except Exception:
        pass
    return f"ID:{uid}"

def _bxh_rank(prepared: dict[str, dict], category: str):
    """
    category:
      "ol"    => stats.ol_count
      "odt"   => stats.odt_count
      "tien"  => ngan_phi
      "ruong" => tổng rương báu (lifetime)
    """
    arr = []
    for uid, u in prepared.items():
        if category == "ol":
            val = int(u["stats"].get("ol_count", 0))
        elif category == "odt":
            val = int(u["stats"].get("odt_count", 0))
        elif category == "tien":
            val = int(u["ngan_phi"])
        elif category == "ruong":
            val, _ = _bxh_total_ruong_alltime(u)
        else:
            continue
        arr.append((uid, val))

    arr.sort(key=lambda x: x[1], reverse=True)
    return arr[:10], arr

async def _bxh_build_overview_embed(requestor_name: str):
    """
    Hiển thị 4 khối lifetime:
      🗺️ Thám Hiểm (TOP1 ol_count)
      💎 Đổ Thạch (TOP1 odt_count)
      💰 Ngân Phiếu (TOP1 giàu nhất)
      📦 Rương Báu (TOP1 nhiều rương)
    """
    data = load_data()
    prepared = _bxh_collect_users(data)

    top_ol,   _all_ol   = _bxh_rank(prepared, "ol")
    top_odt,  _all_odt  = _bxh_rank(prepared, "odt")
    top_tien, _all_tien = _bxh_rank(prepared, "tien")
    top_r,    _all_r    = _bxh_rank(prepared, "ruong")

    async def block_thamhiem():
        if not top_ol:
            return "🗺️ Thám Hiểm\nKhông có dữ liệu."
        uid, val = top_ol[0]
        dn = await _bxh_display_name(uid)
        return (
            "🗺️ Thám Hiểm\n"
            f"🥇 TOP 1 — {dn} — {val} lần"
        )

    async def block_dothach():
        if not top_odt:
            return f"{EMOJI_DOTHACHT} Đổ Thạch\nKhông có dữ liệu."
        uid, val = top_odt[0]
        dn = await _bxh_display_name(uid)
        return (
            f"{EMOJI_DOTHACHT} Đổ Thạch\n"
            f"🥇 TOP 1 — {dn} — {val} lần"
        )

    async def block_tien():
        if not top_tien:
            return f"{NP_EMOJI} Ngân Phiếu\nKhông có dữ liệu."
        uid, val = top_tien[0]
        dn = await _bxh_display_name(uid)
        return (
            f"{NP_EMOJI} Ngân Phiếu\n"
            f"🥇 TOP 1 — {dn} — {format_num(val)} Ngân Phiếu"
        )

    async def block_ruong():
        if not top_r:
            return "<:ruongthuong:1433525898107158660> Rương Báu\nKhông có dữ liệu."
        uid, _val = top_r[0]
        dn = await _bxh_display_name(uid)

        total_alltime, breakdown = _bxh_total_ruong_alltime(prepared[uid])

        emo_S = RARITY_CHEST_EMOJI.get("S", "🟣")
        emo_A = RARITY_CHEST_EMOJI.get("A", "🟡")
        emo_B = RARITY_CHEST_EMOJI.get("B", "🟠")
        emo_C = RARITY_CHEST_EMOJI.get("C", "🔵")
        emo_D = RARITY_CHEST_EMOJI.get("D", "⚪")

        s = breakdown["S"]; a = breakdown["A"]; b = breakdown["B"]; c = breakdown["C"]; d = breakdown["D"]

        return (
            "<:ruongthuong:1433525898107158660> Rương Báu\n"
            f"🥇 TOP 1 — {dn} — {total_alltime} Rương Báu\n"
            f"{emo_S} {s}  {emo_A} {a}  {emo_B} {b}  {emo_C} {c}  {emo_D} {d}"
        )

    desc = "\n\n".join([
        await block_thamhiem(),
        await block_dothach(),
        await block_tien(),
        await block_ruong(),
        "Chọn các nút bên dưới để xem TOP 10 chi tiết."
    ])

    emb = make_embed(
        title="🏆 TỔNG BẢNG XẾP HẠNG",
        description=desc,
        color=0xF1C40F,
        footer=f"Yêu cầu bởi {requestor_name}"
    )
    return emb

async def _bxh_render_overview_ctx(ctx: commands.Context):
    return await _bxh_build_overview_embed(ctx.author.display_name)

async def _bxh_render_overview_inter(inter: discord.Interaction, owner_name: str):
    return await _bxh_build_overview_embed(owner_name)

def _bxh_footer_with_rank(category: str, author_id: int, author_name: str, full_sorted: list):
    """
    Footer hiển thị vị trí cá nhân người đang bấm.
    """
    pos = None
    you_line = None
    aid = str(author_id)

    for rank_idx, item in enumerate(full_sorted, start=1):
        uid_here = str(item[0])
        if uid_here != aid:
            continue
        val = item[1]
        if category == "ol":
            you_line = f"Bạn: {val} lần"
        elif category == "odt":
            you_line = f"Bạn: {val} lần"
        elif category == "tien":
            you_line = f"Bạn: {format_num(val)} Ngân Phiếu"
        elif category == "ruong":
            you_line = f"Bạn: {val} Rương Báu (tính cả đã mở)"
        pos = rank_idx
        break

    if pos is None:
        return f"Yêu cầu bởi {author_name}"

    footer_txt = f"Vị trí của bạn: #{pos}"
    if you_line:
        footer_txt += f" • {you_line}"
    return footer_txt

async def _bxh_render_detail(category: str, author_id: int, author_name: str):
    """
    Chi tiết TOP 10 cho từng hạng mục.
    category in ["ol","odt","tien","ruong"]
    """
    data = load_data()
    prepared = _bxh_collect_users(data)

    topN, full_sorted = _bxh_rank(prepared, category)
    lines = []

    if category == "ol":
        title = "🗺️ TOP 10 — THÁM HIỂM"
        for i, (uid, val) in enumerate(topN, start=1):
            dn = await _bxh_display_name(uid)
            lines.append(f"#{i} {dn} — {val} lần")

    elif category == "odt":
        title = f"{EMOJI_DOTHACHT} TOP 10 — ĐỔ THẠCH"
        for i, (uid, val) in enumerate(topN, start=1):
            dn = await _bxh_display_name(uid)
            lines.append(f"#{i} {dn} — {val} lần")

    elif category == "tien":
        title = f"{NP_EMOJI} TOP 10 — NGÂN PHIẾU"
        for i, (uid, val) in enumerate(topN, start=1):
            dn = await _bxh_display_name(uid)
            lines.append(f"#{i} {dn} — {format_num(val)} NP")

    elif category == "ruong":
        title = "💎 TOP 10 — RƯƠNG BÁU"

        # Top 3 có chi tiết từng phẩm (dùng emoji RARITY_EMOJI)
        for i, (uid, _v) in enumerate(topN, start=1):
            dn = await _bxh_display_name(uid)
            total_alltime, brk = _bxh_total_ruong_alltime(prepared[uid])

            s = brk["S"]; a = brk["A"]; b = brk["B"]; c = brk["C"]; d = brk["D"]

            if i <= 3:
                # Top 3 có breakdown chi tiết với emoji đẹp
                lines.append(
                    f"#{i} {dn} — {total_alltime} Rương Báu\n"
                    f"{RARITY_EMOJI['S']} {s}  "
                    f"{RARITY_EMOJI['A']} {a}  "
                    f"{RARITY_EMOJI['B']} {b}  "
                    f"{RARITY_EMOJI['C']} {c}  "
                    f"{RARITY_EMOJI['D']} {d}"
                )
            else:
                # Từ hạng 4 trở đi chỉ hiển thị tổng
                lines.append(f"#{i} {dn} — {total_alltime} Rương Báu")


    else:
        title = "TOP 10"
        lines = ["Chưa có dữ liệu."]

    if not lines:
        lines = ["Chưa có dữ liệu."]

    footer_txt = _bxh_footer_with_rank(category, author_id, author_name, full_sorted)

    emb = make_embed(
        title=title,
        description="\n".join(lines),
        color=0xF1C40F,
        footer=footer_txt
    )
    return emb

class BXHView(discord.ui.View):
    """
    View chỉ còn 5 nút (không có Tuần / Ngày nữa):
      🏆 Tổng
      🗺️ Thám Hiểm
      💎 Đổ Thạch
      💰 Ngân Phiếu
      📦 Rương Báu
    current_tab in ["all","ol","odt","tien","ruong"]
    """
    def __init__(self, owner_id: int, owner_name: str, current_tab: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.owner_name = owner_name
        self.current_tab = current_tab
        self._apply_disabled_state()

    async def _is_owner(self, inter: discord.Interaction) -> bool:
        if inter.user.id != self.owner_id:
            try:
                await inter.response.send_message(
                    "⚠️ Đây không phải bảng xếp hạng của bạn.",
                    ephemeral=True
                )
            except Exception:
                pass
            return False
        return True

    def _apply_disabled_state(self):
        tab_map = {
            "all":  "btn_total",
            "ol":   "btn_thamhiem",
            "odt":  "btn_dothach",
            "tien": "btn_tien",
            "ruong":"btn_ruong",
        }
        target = tab_map.get(self.current_tab)
        if target:
            try:
                getattr(self, target).disabled = True
            except Exception:
                pass

    @discord.ui.button(label="Tổng", emoji="🏆", style=discord.ButtonStyle.danger)
    async def btn_total(self, inter: discord.Interaction, button: discord.ui.Button):
        if not await self._is_owner(inter):
            return
        emb = await _bxh_render_overview_inter(inter, self.owner_name)
        new_view = BXHView(self.owner_id, self.owner_name, current_tab="all")
        await inter.response.edit_message(embed=emb, view=new_view)

    @discord.ui.button(label="Thám Hiểm", emoji="🗺️", style=discord.ButtonStyle.success)
    async def btn_thamhiem(self, inter: discord.Interaction, button: discord.ui.Button):
        if not await self._is_owner(inter):
            return
        emb = await _bxh_render_detail("ol", self.owner_id, self.owner_name)
        new_view = BXHView(self.owner_id, self.owner_name, current_tab="ol")
        await inter.response.edit_message(embed=emb, view=new_view)

    @discord.ui.button(label="Đổ Thạch", emoji=EMOJI_DOTHACHT, style=discord.ButtonStyle.success)
    async def btn_dothach(self, inter: discord.Interaction, button: discord.ui.Button):
        if not await self._is_owner(inter):
            return
        emb = await _bxh_render_detail("odt", self.owner_id, self.owner_name)
        new_view = BXHView(self.owner_id, self.owner_name, current_tab="odt")
        await inter.response.edit_message(embed=emb, view=new_view)

    @discord.ui.button(label="Ngân Phiếu", emoji=NP_EMOJI, style=discord.ButtonStyle.success)
    async def btn_tien(self, inter: discord.Interaction, button: discord.ui.Button):
        if not await self._is_owner(inter):
            return
        emb = await _bxh_render_detail("tien", self.owner_id, self.owner_name)
        new_view = BXHView(self.owner_id, self.owner_name, current_tab="tien")
        await inter.response.edit_message(embed=emb, view=new_view)

    @discord.ui.button(label="Rương Báu", emoji="<:ruongthuong:1433525898107158660>", style=discord.ButtonStyle.success)
    async def btn_ruong(self, inter: discord.Interaction, button: discord.ui.Button):
        if not await self._is_owner(inter):
            return
        emb = await _bxh_render_detail("ruong", self.owner_id, self.owner_name)
        new_view = BXHView(self.owner_id, self.owner_name, current_tab="ruong")
        await inter.response.edit_message(embed=emb, view=new_view)

@bot.command(name="obxh", aliases=["bxh"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_obxh(ctx: commands.Context):
    """
    Mở BXH lần đầu:
    - Mặc định tab = Tổng
    """
    emb = await _bxh_render_overview_ctx(ctx)
    view = BXHView(ctx.author.id, ctx.author.display_name, current_tab="all")
    await ctx.send(embed=emb, view=view)

# ================================
# 🚀 BXH
# ================================










# ====================================================================================================================================
# PL-008 🧍 BẮT ĐẦU KHU VỰC GAME PLAY      BẮT ĐẦU KHU VỰC GAME PLAY      BẮT ĐẦU KHU VỰC GAME PLAY     BẮT ĐẦU KHU VỰC GAME PLAY
# ====================================================================================================================================
# 🧍 BẮT ĐẦU KHU VỰC GAME PLAY      BẮT ĐẦU KHU VỰC GAME PLAY      BẮT ĐẦU KHU VỰC GAME PLAY     BẮT ĐẦU KHU VỰC GAME PLAY
# ====================================================================================================================================S

import random
import string

# ---------------------------------------------------------------------------------
# A. CHỐT EMOJI & PREFIX (để bạn dễ đổi sau này)
# ---------------------------------------------------------------------------------
EMOJI_PREFIX = ""  # muốn thêm tiền tố cho toàn bộ emoji → sửa ở đây

def _emj(v: str) -> str:
    return f"{EMOJI_PREFIX}{v}"

# emoji gốc của bạn (giữ nguyên, chỉ bọc qua _emj nếu cần)
NP_EMOJI = _emj("<a:np:1431713164277448888>")
XU_EMOJI = _emj("<a:tienxu:1431717943980589347>")

# emoji phẩm trang bị như trong file gốc bạn nói:
RARITY_EMOJI = {
    "S": _emj("<a:S11:1432467644761509948>"),
    "A": _emj("<a:S10:1432467640858323076>"),
    "B": _emj("<a:S9:1432467637478897724>"),
    "C": _emj("<a:S8:1432467634355697714>"),
    "D": _emj("<a:S12:1432467648951560253>"),
}

# emoji rương (có thể bạn đã có – nếu đã có thì giữ cái của bạn, đoạn này chỉ để đủ code)
RARITY_CHEST_EMOJI = globals().get("RARITY_CHEST_EMOJI", {
    "S": "🎁",
    "A": "🎁",
    "B": "🎁",
    "C": "🎁",
    "D": "🎁",
})
RARITY_CHEST_OPENED_EMOJI = globals().get("RARITY_CHEST_OPENED_EMOJI", RARITY_CHEST_EMOJI)
RARITY_COLOR = globals().get("RARITY_COLOR", {
    "S": 0xF1C40F,
    "A": 0x9B59B6,
    "B": 0x3498DB,
    "C": 0x2ECC71,
    "D": 0x95A5A6,
})

# emoji tạp vật theo phẩm
TAP_VAT_EMOJI = {
    "S": _emj("💎"),
    "A": _emj("💍"),
    "B": _emj("🐚"),
    "C": _emj("🪨"),
    "D": _emj("🪵"),
}

# emoji HOÀN MỸ (bạn bảo dùng :diamond_shape_with_a_dot_inside:)
HOAN_MY_EMOJI = ":diamond_shape_with_a_dot_inside:"

# emoji LỰC CHIẾN (bạn đưa)
LC_EMOJI = "<:3444:1434780655794913362>"

# ---------------------------------------------------------------------------------
# B. CẤU HÌNH TỈ LỆ – GIÁ TRỊ
# ---------------------------------------------------------------------------------
# tỉ lệ rơi trang bị khi mở rương
ITEM_DROP_RATE_BY_CHEST = {
    "D": 0.01,
    "C": 0.03,
    "B": 0.05,
    "A": 0.10,
    "S": 0.20,
}

# Xu rơi phụ khi mở rương
XU_RANGE = {
    "D": (0, 1),
    "C": (1, 3),
    "B": (2, 6),
    "A": (5, 15),
    "S": (10, 40),
}

# Giá bán trang bị → Xu
EQUIP_SELL_XU_RANGE = {
    "D": (100, 300),
    "C": (300, 900),
    "B": (900, 2700),
    "A": (2700, 6000),
    "S": (6000, 12000),
}

# Giá bán tạp vật → NP
TAP_VAT_SELL_NP_RANGE = {
    "D": (20, 100),
    "C": (100, 500),
    "B": (500, 5000),
    "A": (5000, 20000),
    "S": (20000, 200000),
}

# ---------------------------------------------------------------------------------
# C. ĐẢM BẢO USER CÓ FIELD KINH TẾ MỚI
# ---------------------------------------------------------------------------------
def _ensure_economy_fields(user: dict):
    user.setdefault("xu", 0)
    tv = user.setdefault("tap_vat", {})
    for r in ["D", "C", "B", "A", "S"]:
        tv.setdefault(r, 0)

# nếu trong file gốc chưa có quest_runtime_increment thì tạo no-op để khỏi lỗi
if "quest_runtime_increment" not in globals():
    def quest_runtime_increment(user: dict, field: str, amount: int = 1):
        # no-op
        pass

# ---------------------------------------------------------------------------------
# D. DANH SÁCH TÊN + LORE (70 món) – rút gọn nhóm theo phái
# ---------------------------------------------------------------------------------
ITEM_NAME_POOLS = {
    "kiem_toai_mong": [
        ("Kiếm Bóng Nguyệt", "Lưỡi kiếm phản chiếu ánh trăng cuối mùa, chém cả niềm hối tiếc."),
        ("Ảnh Kiếm Vô Tâm", "Đâm ra không ý niệm, chém xuống không nhân từ."),
        ("Nguyệt Ảnh Tàn Hồn", "Mỗi nhát vung là một kiếp hồn tan."),
        ("Kiếm U Ảnh", "Ẩn mình trong bóng tối, chỉ thấy tia sáng cuối."),
        ("Huyết Ảnh Kiếm", "Tắm máu trăm trận, rỉ sét bằng ký ức."),
        ("Kiếm Trảm Không", "Chém cả không gian, để lại vết rách trong hư vô."),
        ("Kiếm Thiên Mệnh", "Kẻ định đoạt số phận chính là lưỡi này."),
        ("Kiếm Tĩnh Dạ", "Lặng im như đêm, nhưng giết người không tiếng."),
        ("Kiếm Sát Hồn", "Một khi đã rút ra, hồn người không thể trở lại."),
        ("Kiếm Lưu Quang", "Tia sáng cuối cùng của kiếm khách thất lạc."),
    ],
    "thuong_huyet_ha": [
        ("Thương Huyết Hà", "Thấm đẫm máu thù, nhuộm đỏ cả sông trời."),
        ("Thương Long Tước", "Hơi thở rồng ẩn trong đầu thương."),
        ("Thương Phá Quân", "Vì nó, vạn quân tan rã."),
        ("Thương Hàn Ảnh", "Lạnh hơn cả gió Bắc, sắc bén như ý chí chết."),
        ("Thương Liệt Diễm", "Bốc cháy như ngọn lửa báo thù."),
        ("Thương Vân Hà", "Truyền thuyết kể nó từng đâm xuyên trời."),
        ("Thương Bạch Cốt", "Cắm xuống nơi nào, nơi đó trắng xóa xương tàn."),
        ("Thương Huyết Ảnh", "Hồn thương nhập máu, kẻ cầm bị nuốt dần."),
        ("Thương Tuyệt Vong", "Tồn tại chỉ để kết thúc."),
        ("Thương Phong Lôi", "Khi vung lên, trời nổi sấm."),
    ],
    "dan_than_tuong": [
        ("Cầm Vân Tương", "Giai điệu ngân dài, dẫn linh hồn lạc về mây."),
        ("Cầm Bích Nguyệt", "Mỗi phím đàn là vết nứt của trăng xanh."),
        ("Cầm Huyễn Âm", "Âm điệu mê hoặc, khiến cả ma thần ngủ quên."),
        ("Cầm Tịch Dương", "Âm cuối tan cùng hoàng hôn."),
        ("Cầm Trầm Không", "Không gian cũng run rẩy theo tiếng đàn."),
        ("Cầm Huyễn Ảnh", "Đàn có hình, âm không thật."),
        ("Cầm Lưu Sa", "Âm thanh như cát rơi giữa sa mạc."),
        ("Cầm Thanh Lãnh", "Lạnh lẽo mà thanh khiết, gột linh hồn."),
        ("Cầm Vọng Hải", "Nghe khúc cuối là quên cả đời."),
        ("Cầm Nguyệt Huyền", "Dây đàn buộc vào ánh trăng, ngân mãi không tắt."),
    ],
    "truong_cuu_linh": [
        ("Trượng Cửu Linh", "Giam hồn của chín linh thú, chỉ người mạnh mới giữ nổi."),
        ("Trượng U Minh", "Từ địa ngục mang về, cháy bằng linh hồn."),
        ("Trượng Hoang Vân", "Hơi thở trời đất ngưng tụ."),
        ("Trượng Phong Ấn", "Niêm phong cả ký ức, mở ra là diệt vong."),
        ("Trượng Mệnh Chi", "Định mệnh bị bẻ cong dưới đầu trượng."),
        ("Trượng Lôi Phệ", "Sấm sét quỳ gối khi nó giáng xuống."),
        ("Trượng Ánh Nguyệt", "Tỏa sáng trong đêm dài như linh hồn vĩnh cửu."),
        ("Trượng Huyền Ma", "Ma lực trào dâng, cuốn phăng cả núi sông."),
        ("Trượng Linh Tế", "Cầu thông âm dương, nghe tiếng khóc của người chết."),
        ("Trượng Tàn Nguyệt", "Nguyệt tàn – nhân diệt."),
    ],
    "lua_to_van": [
        ("Lụa Tố Vấn", "Mềm như mây, nhưng ràng cả định mệnh."),
        ("Lụa Bách Hoa", "Thêu bằng hương của ngàn đóa hoa tàn."),
        ("Lụa Thanh Tâm", "Chạm vào là tan mọi oán hận."),
        ("Lụa Huyền Ảnh", "Ẩn giấu chủ nhân khỏi mọi ánh nhìn."),
        ("Lụa Vân Tiêu", "Bay cao cùng khói trời, tan giữa gió."),
        ("Lụa Yên Sương", "Sương mờ ôm lấy, hư ảo như mộng."),
        ("Lụa Hồng Trần", "Dính một hạt bụi trần, vạn kiếp không sạch."),
        ("Lụa Linh Quang", "Lấp lánh linh khí, bảo hộ người mang."),
        ("Lụa Phù Không", "Nhẹ đến mức gió cũng không chạm được."),
        ("Lụa Nguyệt Hoa", "Nhuộm ánh trăng, thơm mùi đêm."),
    ],
    "gang_thiet_y": [
        ("Quyền Thiết Y", "Nắm đấm rèn trong chiến hỏa, chịu được vảy rồng."),
        ("Hộ Thủ Hắc Thiết", "Đỡ trăm nhát mà không mẻ."),
        ("Huyết Quyền Chi Ảnh", "Mỗi cú đấm là một linh hồn mất."),
        ("Quyền Phá Sơn", "Đập vỡ cả tường núi."),
        ("Hộ Thủ Trấn Hồn", "Giữ tâm không loạn giữa chiến trường."),
        ("Hắc Thiết Chi Thủ", "Nặng như lời thề."),
        ("Quyền Lưu Tinh", "Vung lên như sao rơi."),
        ("Hộ Thủ Hoàng Thiết", "Mạ vàng của vua xưa, truyền lại cho võ giả."),
        ("Quyền Sư Tử Hống", "Tiếng gầm dồn trong nắm đấm."),
        ("Hộ Thủ Thần Vệ", "Che chở cho bằng hữu ở phía sau."),
    ],
    "ao_giap_chung": [
        ("Giáp Long Tinh", "Khảm vảy rồng hóa thạch, đao thương bất nhập."),
        ("Áo Giáp Thanh Ô", "Phủ sương xanh, nhẹ mà bền."),
        ("Y Thần Thạch", "May bằng tơ trời, đỡ được một kích của chân thần."),
        ("Giáp Hộ Linh", "Bảo vệ linh hồn trước tà khí."),
        ("Giáp Bạch Thiết", "Màu trắng bạc, dành cho kỵ sĩ chính đạo."),
        ("Áo Lục Sam", "Giản dị mà linh động, ẩn vào rừng là mất dấu."),
        ("Y Trầm Không", "Tối như vực sâu, che giấu khí tức."),
        ("Giáp U Ảnh", "Ẩn hiện dưới ánh trăng, khó bị nhìn thấy."),
        ("Áo Vệ Đạo", "Thánh quang gia trì, tà ma lùi bước."),
        ("Giáp Thiên Hộ", "Được chúc phúc để bảo vệ chủ nhân đến phút cuối."),
    ],
}

# mapping loại vũ khí → môn phái
WEAPON_CLASS_LOCK = {
    "Kiếm": "Toái Mộng",
    "Thương": "Huyết Hà",
    "Đàn": "Thần Tương",
    "Trượng": "Cửu Linh",
    "Dải Lụa": "Tố Vấn",
    "Găng Tay": "Thiết Y",
}

# ---------------------------------------------------------------------------------
# E. POOL CHỈ SỐ – TÁCH HẲN
# ---------------------------------------------------------------------------------
WEAPON_STAT_POOL = [
    ("atk_physical", "Tấn công vật lý"),
    ("atk_magic", "Tấn công phép"),
    ("atk_team", "Tấn công nhóm"),
    ("crit", "Chí mạng"),
    ("control", "Khống chế"),
    ("agility", "Nhanh nhẹn"),
    ("cast_speed", "Tốc độ ra chiêu"),
    ("cdr", "Giảm hồi chiêu"),
    ("lifesteal", "Hút máu"),
    ("mana_regen", "Hồi năng lượng"),
    ("damage_bonus", "Tăng sát thương tổng (%)"),
    ("all_bonus", "Toàn diện"),
]

ARMOR_STAT_POOL = [
    ("defense", "Phòng thủ"),
    ("res_magic", "Kháng phép"),
    ("hp", "Máu tối đa"),
    ("regen", "Phục hồi"),
    ("damage_reduce", "Giảm sát thương nhận (%)"),
    ("control", "Khống chế"),
    ("agility", "Nhanh nhẹn"),
    ("mana_regen", "Hồi năng lượng"),
    ("all_bonus", "Toàn diện thủ"),
]

# ---------------------------------------------------------------------------------
# F. HÀM TÍNH LỰC CHIẾN (đơn giản để dùng ngay)
# ---------------------------------------------------------------------------------
def calc_luc_chien(item: dict) -> int:
    """
    Tính lực chiến cơ bản từ các dòng thuộc tính.
    Đây là bản đơn giản để xài ngay, sau này bạn muốn tinh hơn thì đổi hệ số ở đây.
    """
    base = 0
    for st in item.get("stats", []):
        key = st.get("key")
        val = st.get("val", 0)
        # hệ số đơn giản
        if key in ("atk_physical", "atk_magic", "hp", "defense"):
            base += int(val)
        elif key in ("crit", "agility", "cast_speed", "cdr", "damage_bonus", "damage_reduce", "res_magic", "lifesteal", "mana_regen", "regen", "control"):
            base += int(val * 50)  # % → quy đổi
        elif key == "all_bonus":
            base += 500
    # bonus theo hoàn mỹ
    perfect = int(item.get("perfect", 0))
    base = int(base * (1 + perfect / 1000))  # nhẹ thôi
    # bonus theo Hoàn Hảo
    if item.get("hoan_hao"):
        base = int(base * 1.1)
    return max(base, 1)

# ---------------------------------------------------------------------------------
# G. HÀM SINH ITEM
# ---------------------------------------------------------------------------------
def _gen_item_id():
    return "".join(random.choices("0123456789ABCDEF", k=4))

def generate_item_from_rarity(rarity: str) -> dict:
    """
    Sinh 1 trang bị mới từ phẩm rương.
    - 70 tên + lore
    - phân loại vũ khí/giáp
    - roll stat từ pool đúng loại
    - có Hoàn Hảo 5% nếu S
    """
    # 50% vũ khí, 50% giáp
    is_weapon = random.random() < 0.5

    if is_weapon:
        # chọn 1 trong 6 dòng vũ khí
        pool_key = random.choice([
            "kiem_toai_mong",
            "thuong_huyet_ha",
            "dan_than_tuong",
            "truong_cuu_linh",
            "lua_to_van",
            "gang_thiet_y",
        ])
        name, lore = random.choice(ITEM_NAME_POOLS[pool_key])
        # suy ra loại vũ khí từ pool
        if pool_key == "kiem_toai_mong":
            item_type = "Kiếm"
            phai = "Toái Mộng"
        elif pool_key == "thuong_huyet_ha":
            item_type = "Thương"
            phai = "Huyết Hà"
        elif pool_key == "dan_than_tuong":
            item_type = "Đàn"
            phai = "Thần Tương"
        elif pool_key == "truong_cuu_linh":
            item_type = "Trượng"
            phai = "Cửu Linh"
        elif pool_key == "lua_to_van":
            item_type = "Dải Lụa"
            phai = "Tố Vấn"
        else:
            item_type = "Găng Tay"
            phai = "Thiết Y"

        # số dòng theo phẩm
        if rarity == "S":
            stat_count = random.randint(4, 5)
        elif rarity == "A":
            stat_count = random.randint(2, 3)
        else:
            stat_count = 0  # B/C/D: không roll

        stats = []
        for _ in range(stat_count):
            key, label = random.choice(WEAPON_STAT_POOL)
            # giá trị demo
            val = random.randint(5, 15) * 10  # số này bạn chỉnh tiếp
            stats.append({"key": key, "label": label, "val": val})

    else:
        # áo giáp
        name, lore = random.choice(ITEM_NAME_POOLS["ao_giap_chung"])
        item_type = "Áo Giáp"
        phai = None
        if rarity == "S":
            stat_count = random.randint(4, 5)
        elif rarity == "A":
            stat_count = random.randint(2, 3)
        else:
            stat_count = 0
        stats = []
        for _ in range(stat_count):
            key, label = random.choice(ARMOR_STAT_POOL)
            val = random.randint(5, 15) * 10
            stats.append({"key": key, "label": label, "val": val})

    # hoàn mỹ
    if rarity == "S":
        perfect = random.randint(61, 100)
    elif rarity == "A":
        perfect = random.randint(1, 60)
    else:
        perfect = 0

    # Hoàn Hảo 5%
    hoan_hao = False
    if rarity == "S" and random.random() < 0.05:
        hoan_hao = True
        # tăng các stat
        for s in stats:
            s["val"] = int(s["val"] * 1.1)

    item = {
        "id": _gen_item_id(),
        "name": name,
        "rarity": rarity,
        "type": item_type,  # để omac kiểm tra slot + phái
        "phai": phai,
        "equipped": False,
        "perfect": perfect,
        "hoan_hao": hoan_hao,
        "stats": stats,
        "lore": lore,
    }

    # gắn giá bán Xu để obantrangbi dùng
    lo_xu, hi_xu = EQUIP_SELL_XU_RANGE.get(rarity, (0, 0))
    item["sell_xu"] = random.randint(lo_xu, hi_xu) if hi_xu >= lo_xu else 0

    # tính lực chiến
    item["luc_chien"] = calc_luc_chien(item)

    return item

# ---------------------------------------------------------------------------------
# H. HỖ TRỢ MỞ RƯƠNG
# ---------------------------------------------------------------------------------
def _rarity_order_index(r: str) -> int:
    order = ["S", "A", "B", "C", "D"]
    try:
        return order.index(r)
    except ValueError:
        return 999

def _pick_highest_available_rarity(user) -> str | None:
    for r in ["S", "A", "B", "C", "D"]:
        if int(user["rungs"].get(r, 0)) > 0:
            return r
    return None

def _open_one_chest(user, r: str):
    # trừ rương
    user["rungs"][r] = int(user["rungs"].get(r, 0)) - 1

    # cộng NP như cũ
    gp = get_nganphieu(r)
    user["ngan_phi"] = int(user.get("ngan_phi", 0)) + gp

    # đảm bảo field mới
    _ensure_economy_fields(user)

    # +1 tạp vật theo phẩm
    user["tap_vat"][r] = int(user["tap_vat"].get(r, 0)) + 1

    # +Xu nhẹ
    lo, hi = XU_RANGE.get(r, (0, 0))
    xu_gain = random.randint(lo, hi) if hi >= lo else 0
    user["xu"] = int(user.get("xu", 0)) + xu_gain

    # log stats
    user.setdefault("stats", {})
    user["stats"]["ngan_phi_earned_total"] = int(user["stats"].get("ngan_phi_earned_total", 0)) + gp
    user["stats"]["opened"] = int(user["stats"].get("opened", 0)) + 1
    return gp, xu_gain, {"rarity": r, "count": 1}, item


# ---------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------
# J. LỆNH OMO – MỞ RƯƠNG
# ---------------------------------------------------------------------------------
@bot.command(name="mo", aliases=["omo"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_omo(ctx, *args):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    _ensure_economy_fields(user)
    argv = [a.strip().lower() for a in args]

    def _open_many_for_rarity(user, r: str, limit: int = 50):
        opened = 0
        total_np = 0
        total_xu = 0
        tv_cnt = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
        items = []
        while opened < limit and int(user["rungs"].get(r, 0)) > 0:
            gp, xu_gain, tv, it = _open_one_chest(user, r)
            opened += 1
            total_np += gp
            total_xu += xu_gain
            tv_cnt[tv["rarity"]] += tv["count"]
            if it:
                items.append(it)
        return opened, total_np, total_xu, tv_cnt, items

    # omo all
    if len(argv) == 1 and argv[0] == "all":
        LIMIT = 50
        opened = 0
        total_np = 0
        total_xu = 0
        tv_all = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
        items = []
        highest_seen = None

        for r in ["S", "A", "B", "C", "D"]:
            while opened < LIMIT and int(user["rungs"].get(r, 0)) > 0:
                gp, xu_gain, tv, it = _open_one_chest(user, r)
                opened += 1
                total_np += gp
                total_xu += xu_gain
                tv_all[tv["rarity"]] += tv["count"]

                if it:
                    items.append(it)
                    # tìm phẩm cao nhất để lấy emoji đẹp
                    if (
                        highest_seen is None
                        or _rarity_order_index(it["rarity"]) < _rarity_order_index(highest_seen)
                    ):
                        highest_seen = it["rarity"]

        if opened == 0:
            await ctx.reply("❗ Bạn không có rương để mở.", mention_author=False)
            return

        # log nhiệm vụ ngày
        quest_runtime_increment(user, "opened_today", opened)
        save_data(data)

        # nếu không rơi item nào thì lấy cái phẩm cao nhất đã mở
        highest_for_title = highest_seen or "D"
        title_emoji = RARITY_CHEST_OPENED_EMOJI.get(highest_for_title, "🎁")

        emb = make_embed(
            title=f"{title_emoji} **{ctx.author.display_name}** đã mở x{opened} rương",
            color=0x2ECC71,
            footer=ctx.author.display_name
        )

        # block phần thưởng
        reward_lines = [
            f"{NP_EMOJI} **{format_num(total_np)}**",
            f"{XU_EMOJI} **{format_num(total_xu)}**",
        ]

        tv_lines = []
        for rr in ["S", "A", "B", "C", "D"]:
            if tv_all[rr] > 0:
                tv_lines.append(f"{TAP_VAT_EMOJI[rr]} x{tv_all[rr]}")
        if tv_lines:
            reward_lines.append("🧩 " + "  ".join(tv_lines))

        emb.add_field(name="Phần thưởng", value="\n".join(reward_lines), inline=False)

        # trang bị rơi
        if items:
            lines = []
            for it in items[:10]:
                lines.append(
                    f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} {HOAN_MY_EMOJI} {it.get('perfect', 0)}%{LC_EMOJI}{format_num(it.get('luc_chien', 0))}"
                )
            if len(items) > 10:
                lines.append(f"... và {len(items) - 10} món khác")
            emb.add_field(name="Trang bị rơi", value="\n".join(lines), inline=False)

        # footer còn rương
        remaining = sum(int(user["rungs"].get(r, 0)) for r in ["S", "A", "B", "C", "D"])
        if remaining > 0:
            emb.set_footer(text=f"Còn {remaining} rương — dùng `omo all` để mở tiếp")

        await ctx.send(embed=emb)
        return

    # ====== omo <rarity> ... ======
    if len(argv) >= 1 and argv[0] in {"d", "c", "b", "a", "s"}:
        r = argv[0].upper()
        available = int(user["rungs"].get(r, 0))
        if available <= 0:
            await ctx.reply(f"❗ Bạn không có rương phẩm {r}.", mention_author=False)
            return

        if len(argv) >= 2:
            if argv[1] == "all":
                req = min(50, available)
            else:
                try:
                    req = int(argv[1].replace(",", ""))
                except Exception:
                    await ctx.reply("⚠️ Ví dụ: `omo d 3` hoặc `omo d all`.", mention_author=False)
                    return
                req = max(1, min(req, 50, available))
        else:
            req = 1

        opened, total_np, total_xu, tv_cnt, items = _open_many_for_rarity(user, r, limit=req)
        if opened == 0:
            await ctx.reply("❗ Không mở được rương nào.", mention_author=False)
            return

        quest_runtime_increment(user, "opened_today", opened)
        save_data(data)

        title_emoji = RARITY_CHEST_OPENED_EMOJI.get(r, "🎁")
        emb = make_embed(
            title=f"{title_emoji} **{ctx.author.display_name}** đã mở x{opened} rương",
            color=RARITY_COLOR.get(r, 0x95A5A6),
            footer=ctx.author.display_name
        )

        reward_lines = [
            f"{NP_EMOJI} **{format_num(total_np)}**",
            f"{XU_EMOJI} **{format_num(total_xu)}**",
        ]
        tv_lines = [f"{TAP_VAT_EMOJI[rr]} x{tv_cnt[rr]}" for rr in ["S", "A", "B", "C", "D"] if tv_cnt[rr] > 0]
        if tv_lines:
            reward_lines.append("🧩 " + "  ".join(tv_lines))
        emb.add_field(name="Phần thưởng", value="\n".join(reward_lines), inline=False)

        if items:
            lines = []
            for it in items[:10]:
                lines.append(
                    f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} — {HOAN_MY_EMOJI} {it.get('perfect',0)}% {LC_EMOJI} {format_num(it.get('luc_chien',0))}"
                )
            if len(items) > 10:
                lines.append(f"... và {len(items) - 10} món khác")
            emb.add_field(name="Trang bị rơi", value="\n".join(lines), inline=False)

        remaining_r = int(user["rungs"].get(r, 0))
        if remaining_r > 0:
            emb.set_footer(text=f"Còn {remaining_r} rương {r} — `omo {r.lower()} all` để mở tiếp")

        await ctx.send(embed=emb)
        return

    # ====== omo mặc định ======
    r_found = _pick_highest_available_rarity(user)
    if not r_found:
        await ctx.reply("❗ Bạn không có rương để mở.", mention_author=False)
        return

    gp, xu_gain, tv, item = _open_one_chest(user, r_found)
    quest_runtime_increment(user, "opened_today", 1)
    save_data(data)

    highest_for_title = item["rarity"] if item else r_found
    title_emoji = RARITY_CHEST_OPENED_EMOJI.get(highest_for_title, "🎁")
    emb = make_embed(
        title=f"{title_emoji} **{ctx.author.display_name}** đã mở 1 rương",
        color=RARITY_COLOR.get(highest_for_title, 0x95A5A6),
        footer=ctx.author.display_name
    )
    reward_lines = [
        f"{NP_EMOJI} **{format_num(gp)}**",
        f"{XU_EMOJI} **{format_num(xu_gain)}**",
        f"🧩 {TAP_VAT_EMOJI[tv['rarity']]} x{tv['count']}",
    ]
    emb.add_field(name="Phần thưởng", value="\n".join(reward_lines), inline=False)

    if item:
        emb.add_field(
            name="Trang bị rơi",
            value=(
                f"{RARITY_EMOJI[item['rarity']]} `{item['id']}` {item['name']} — "
                f"{HOAN_MY_EMOJI} {item.get('perfect',0)}% {LC_EMOJI} {format_num(item.get('luc_chien',0))}"
            ),
            inline=False
        )

    await ctx.send(embed=emb)




import random

def _calc_item_luc_chien(it: dict) -> int:
    """tạm thời: lực chiến = 1000 + perfect*50 + số dòng * 200"""
    base = 1000
    perfect = int(it.get("perfect", 0))
    stats = it.get("stats", [])
    lc = base + perfect * 50 + len(stats) * 200
    # nếu có hoàn hảo thì +10%
    if it.get("hoan_hao"):
        lc = int(lc * 1.1)
    return lc

import random
from datetime import datetime, timedelta

# ===================================================================
# 1) POOL CHỈ SỐ
# ===================================================================

WEAPON_STAT_POOL = {
    "atk_physical": ("Tấn công vật lý", (420, 780)),
    "atk_magic": ("Tấn công phép", (420, 780)),
    "atk_team": ("Tấn công nhóm", (4, 10)),
    "crit": ("Chí mạng", (6, 15)),
    "agility": ("Nhanh nhẹn", (4, 12)),
    "cast_speed": ("Tốc độ ra chiêu", (4, 12)),
    "lifesteal": ("Hút máu", (3, 10)),
    "mana_regen": ("Hồi năng lượng", (3, 9)),
    "cdr": ("Giảm hồi chiêu", (4, 12)),
    "damage_bonus": ("Tăng sát thương tổng (%)", (3, 8)),
    "all_bonus": ("Toàn diện (+% tất cả chỉ số)", (3, 5)),
}

ARMOR_STAT_POOL = {
    "defense": ("Phòng thủ", (220, 360)),
    "res_magic": ("Kháng phép", (220, 360)),
    "hp": ("Máu tối đa (HP)", (2800, 4200)),
    "regen": ("Phục hồi", (80, 180)),
    "damage_reduce": ("Giảm sát thương nhận (%)", (4, 10)),
    "control": ("Kháng/khống chế", (4, 10)),
    "agility": ("Nhanh nhẹn", (2, 6)),
    "mana_regen": ("Hồi năng lượng", (3, 9)),
    "all_bonus": ("Toàn diện thủ (+%)", (3, 5)),
}

# số dòng theo phẩm
RARITY_STAT_ROLLS = {
    "S": (4, 5),
    "A": (2, 3),
    "B": (0, 0),
    "C": (0, 0),
    "D": (0, 0),
}

# ưu tiên theo phái (key phải trùng phái mày đang lưu trong user["class"])
CLASS_STAT_WEIGHT = {
    "toai_mong": {
        "atk_physical": 3,
        "crit": 2,
        "agility": 2,
        "cdr": 1,
    },
    "huyet_ha": {
        "atk_physical": 2,
        "lifesteal": 3,
        "damage_bonus": 2,
        "regen": 1,
    },
    "than_tuong": {
        "atk_magic": 3,
        "cast_speed": 2,
        "cdr": 2,
        "mana_regen": 1,
    },
    "to_van": {
        "atk_team": 3,
        "mana_regen": 2,
        "cdr": 1,
        "control": 1,
    },
    "cuu_linh": {
        "atk_magic": 2,
        "control": 2,
        "mana_regen": 2,
    },
    "thiet_y": {
        "defense": 3,
        "hp": 3,
        "damage_reduce": 2,
    },
}


def _choose_stat_keys_for_item(rarity: str, is_armor: bool, user_class: str | None):
    low, high = RARITY_STAT_ROLLS.get(rarity, (0, 0))
    if high == 0:
        return []
    count = random.randint(low, high)
    pool = ARMOR_STAT_POOL if is_armor else WEAPON_STAT_POOL
    keys = list(pool.keys())

    weight = CLASS_STAT_WEIGHT.get(user_class or "", {})
    weighted = []
    for k in keys:
        w = weight.get(k, 1)
        weighted.extend([k] * w)

    chosen = set()
    # ưu tiên bằng weighted
    while len(chosen) < count and weighted:
        chosen.add(random.choice(weighted))
    # nếu còn thiếu thì bốc thêm từ pool
    while len(chosen) < count and keys:
        chosen.add(random.choice(keys))
    return list(chosen)


def _roll_stat_value(code: str, is_armor: bool):
    pool = ARMOR_STAT_POOL if is_armor else WEAPON_STAT_POOL
    label, (mn, mx) = pool[code]
    val = random.randint(mn, mx)
    if code in (
        "crit", "agility", "cast_speed", "lifesteal", "cdr",
        "damage_bonus", "damage_reduce", "control", "atk_team", "all_bonus"
    ):
        return label, f"{val}%"
    return label, val


def build_item_stats(item: dict, user_class: str | None):
    rarity = item.get("rarity", "D")
    item_type = (item.get("type") or "").lower()
    is_armor = item_type in ("áo giáp", "ao giap", "giáp", "giap", "armor")
    stat_codes = _choose_stat_keys_for_item(rarity, is_armor, user_class)
    stats = []
    for code in stat_codes:
        label, v = _roll_stat_value(code, is_armor)
        stats.append({"code": code, "label": label, "val": v})
    item["stats"] = stats
    return item


# ===================================================================
# 2) TÍNH LỰC CHIẾN
# ===================================================================
def _calc_item_luc_chien(it: dict) -> int:
    base = 800
    perfect = int(it.get("perfect", 0))
    stats = it.get("stats", [])
    lc = base + perfect * 40 + len(stats) * 200
    if it.get("hoan_hao"):
        lc = int(lc * 1.1)
    return lc


# ===================================================================
# 3) SINH ITEM ĐẦY ĐỦ
# ===================================================================
def generate_item_full(rarity: str, user: dict, current_items: list):
    """Sinh 1 item đầy đủ: đúng loại, đúng phái, có chỉ số, Hoàn mỹ, Lực chiến, Lore khớp."""
    # 1️⃣ Gọi hàm gốc tạo khung
    it = generate_item(rarity, current_items)  # hàm gốc của bạn

    # 2️⃣ Xác định phái và loại
    user_class = user.get("class")
    item_type = (it.get("type") or "").lower()
    is_armor = item_type in ("áo giáp", "ao giap", "giáp", "armor")

    # 3️⃣ Chọn tên & lore đúng nhóm
    if is_armor:
        pool_key = "ao_giap_chung"
        type_name = "Áo Giáp"
    else:
        # map phái → pool tương ứng
        pool_map = {
            "toai_mong": ("kiem_toai_mong", "Kiếm"),
            "huyet_ha": ("thuong_huyet_ha", "Thương"),
            "than_tuong": ("dan_than_tuong", "Đàn"),
            "to_van": ("lua_to_van", "Dải Lụa"),
            "cuu_linh": ("truong_cuu_linh", "Trượng"),
            "thiet_y": ("gang_thiet_y", "Găng Tay"),
        }
        pool_key, type_name = pool_map.get(user_class, ("ao_giap_chung", "Áo Giáp"))

        # Nếu chưa chọn phái → random 1 loại bất kỳ
        if not user_class:
            random_pool = random.choice(list({
                "kiem_toai_mong": "Kiếm",
                "thuong_huyet_ha": "Thương",
                "dan_than_tuong": "Đàn",
                "truong_cuu_linh": "Trượng",
                "lua_to_van": "Dải Lụa",
                "gang_thiet_y": "Găng Tay",
            }.items()))
            pool_key, type_name = random_pool

    name, lore = random.choice(ITEM_NAME_POOLS[pool_key])
    it["name"] = name
    it["lore"] = lore
    it["type"] = type_name

    # 4️⃣ Độ hoàn mỹ & dòng Hoàn Hảo
    if rarity == "S":
        it["perfect"] = random.randint(61, 100)
        it["hoan_hao"] = (random.random() < 0.05)
    elif rarity == "A":
        it["perfect"] = random.randint(1, 60)
        it["hoan_hao"] = False
    else:
        it["perfect"] = 0
        it["hoan_hao"] = False

    # 5️⃣ Gán phái (vũ khí mới có, giáp để None)
    if is_armor:
        it["phai"] = None
    else:
        it["phai"] = user_class  # để dạng key như 'than_tuong', 'toai_mong'

    # 6️⃣ Roll stats + tính lực chiến
    build_item_stats(it, user_class)
    it["luc_chien"] = _calc_item_luc_chien(it)

    return it



# ===================================================================
# 4) MỞ 1 RƯƠNG
# ===================================================================
# =========================================================
# HÀM MỞ 1 RƯƠNG (BẢN MỚI)
# trả về: gp, xu_gain, tv_dict, item_or_None
# =========================================================
def _open_one_chest(user: dict, r: str):
    # trừ rương
    user["rungs"][r] = int(user["rungs"].get(r, 0)) - 1

    # NP cố định theo phẩm
    gp = NP_BY_CHEST.get(r, 0)
    user["ngan_phi"] = int(user.get("ngan_phi", 0)) + gp

    # Xu ngẫu nhiên theo phẩm
    xr = XU_RANGE_BY_CHEST.get(r, (0, 0))
    xu_gain = random.randint(xr[0], xr[1]) if xr[1] >= xr[0] else 0
    user["xu"] = int(user.get("xu", 0)) + xu_gain

    # tạp vật
    tv = {"rarity": r, "count": 1}

    # rơi trang bị hiếm
    item = None
    prob = ITEM_DROP_RATE_BY_CHEST.get(r, 0.0)
    if prob > 0 and (random.random() < prob):
        item = generate_item_full(r, user, user["items"])
        user["items"].append(item)

    return gp, xu_gain, tv, item


# =========================================================
# CÁC HẰNG SỐ PHỤ CHO MỞ RƯƠNG
# =========================================================

# emoji Ngân Phiếu bạn đang dùng
NP_EMOJI = "<a:np:1431713164277448888>"
# emoji Xu bạn đang dùng
XU_EMOJI = "<a:tienxu:1431717943980589347>"
# emoji Hoàn mỹ (nếu bạn có emoji riêng thì thay ở đây)
HOAN_MY_EMOJI = "💠"
# emoji Lực chiến (cái bạn gửi)
LC_EMOJI = "<:3444:1434780655794913362>"

# ====== PHÁI HIỂN THỊ CÓ DẤU ======
PHAI_LABEL_FROM_KEY = {
    "thiet_y": "Thiết Y",
    "huyet_ha": "Huyết Hà",
    "than_tuong": "Thần Tương",
    "to_van": "Tố Vấn",
    "cuu_linh": "Cửu Linh",
    "toai_mong": "Toái Mộng",
}


# tạp vật theo phẩm rương
TAP_VAT_EMOJI = {
    "S": "💎",
    "A": "💍",
    "B": "🐚",
    "C": "🪨",
    "D": "🪵",
}

# tỉ lệ rơi TRANG BỊ khi mở rương theo phẩm
ITEM_DROP_RATE_BY_CHEST = {
    "S": 0.20,
    "A": 0.10,
    "B": 0.05,
    "C": 0.03,
    "D": 0.01,
}

# số Xu ngẫu nhiên khi mở rương theo phẩm
XU_RANGE_BY_CHEST = {
    "S": (10, 40),
    "A": (5, 15),
    "B": (2, 6),
    "C": (1, 3),
    "D": (0, 1),
}

# số NP nhận khi mở rương theo phẩm (giữ gần giống bản bạn đang dùng)
NP_BY_CHEST = {
    "S": 5000,
    "A": 2000,
    "B": 800,
    "C": 300,
    "D": 100,
}


# ---------------------------------------------------------------------------------

def generate_item_for_user(rarity: str, user: dict, current_items: list):
    """
    Sinh 1 trang bị theo phẩm, nếu user chưa có phái thì để item['phai'] = None
    để sau này gia nhập phái rồi vẫn dùng được.
    """
    it = generate_item(rarity, current_items)  # hàm cũ của bạn
    # đảm bảo có field phai
    user_class = user.get("class") or user.get("phai")
    if not user_class:
        # chưa có phái → để None
        it["phai"] = None
    else:
        # đã có phái → gán phái của user vào vũ khí, giáp thì cho dùng chung
        # nếu bạn có it["type"] để phân biệt thì làm kỹ hơn:
        it_type = (it.get("type") or "").lower()
        if it_type in ("áo giáp", "ao giap", "giáp", "armor"):
            it["phai"] = None
        else:
            it["phai"] = user_class
    return it

# ---------------------------------------------------------------------------------


# ---------------------------------------------------------------------------------
# K. LỆNH OKHO – XEM KHO
# ---------------------------------------------------------------------------------




# ===================== KHO CÓ NÚT LẬT TRANG =====================

# =========================================================
# KHO + VIEW
# =========================================================

def build_kho_embed(owner_name: str, user: dict, items: list, page_idx: int,
                    page_size: int = 10, total_pages: int = 1) -> discord.Embed:
    start = page_idx * page_size
    page_items = items[start:start + page_size]

    emb = make_embed(
        f"📦 {owner_name} — Kho Nhân Vật",
        color=0x3498DB,
        footer=f"Trang {page_idx+1}/{total_pages}"
    )

    # Rương
    total_r = sum(int(user["rungs"].get(k, 0)) for k in ["D", "C", "B", "A", "S"])
    rtext = (
        f"{RARITY_CHEST_EMOJI['D']} {format_num(user['rungs'].get('D',0))}   "
        f"{RARITY_CHEST_EMOJI['C']} {format_num(user['rungs'].get('C',0))}   "
        f"{RARITY_CHEST_EMOJI['B']} {format_num(user['rungs'].get('B',0))}   "
        f"{RARITY_CHEST_EMOJI['A']} {format_num(user['rungs'].get('A',0))}   "
        f"{RARITY_CHEST_EMOJI['S']} {format_num(user['rungs'].get('S',0))}"
    )
    emb.add_field(name=f"Rương hiện có — {format_num(total_r)}", value=rtext, inline=False)

    # Tài sản
    emb.add_field(
        name="Tài sản",
        value=(
            f"{NP_EMOJI} Ngân Phiếu: **{format_num(user.get('ngan_phi',0))}**\n"
            f"{XU_EMOJI} Tiền Xu: **{format_num(user.get('xu',0))}**"
        ),
        inline=False
    )

    # Tạp vật
    tv = user["tap_vat"]
    tv_line = (
        f"{TAP_VAT_EMOJI['D']} x{format_num(tv['D'])}   "
        f"{TAP_VAT_EMOJI['C']} x{format_num(tv['C'])}   "
        f"{TAP_VAT_EMOJI['B']} x{format_num(tv['B'])}   "
        f"{TAP_VAT_EMOJI['A']} x{format_num(tv['A'])}   "
        f"{TAP_VAT_EMOJI['S']} x{format_num(tv['S'])}"
    )
    emb.add_field(name="Tạp Vật", value=tv_line, inline=False)

    # Trang bị (10 cái / trang)
    if page_items:
        lines = []
        for it in page_items:
            lines.append(
                f"{RARITY_EMOJI.get(it['rarity'],'')} `{it['id']}` {it['name']} "
                f"💠{it.get('perfect',0)}% {LC_EMOJI}{format_num(it.get('luc_chien',0))}"
            )
        emb.add_field(name="Trang bị", value="\n".join(lines), inline=False)
    else:
        emb.add_field(name="Trang bị", value="Không có vật phẩm", inline=False)

    # Thống kê
    st = user.get("stats", {})
    stats_text = (
        f"Rương đã mở: {format_num(st.get('opened',0))}\n"
        f"Số lần thám hiểm: {format_num(st.get('ol_count',0))}\n"
        f"{NP_EMOJI} Tổng NP kiếm được: {format_num(st.get('ngan_phi_earned_total',0))}"
    )
    emb.add_field(name="📊 Thống kê", value=stats_text, inline=False)

    return emb


class KhoView(discord.ui.View):
    def __init__(self, owner_id: str, owner_name: str, user: dict, items: list, page_size: int = 10):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.owner_name = owner_name
        self.user = user
        self.items = items
        self.page_size = page_size
        self.page_idx = 0
        self.total_pages = max(1, (len(items)-1)//page_size + 1)

    async def update_message(self, interaction: discord.Interaction):
        emb = build_kho_embed(
            self.owner_name,
            self.user,
            self.items,
            self.page_idx,
            self.page_size,
            self.total_pages,
        )
        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("Không phải kho của bạn.", ephemeral=True)
            return
        if self.page_idx > 0:
            self.page_idx -= 1
        await self.update_message(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("Không phải kho của bạn.", ephemeral=True)
            return
        if self.page_idx < self.total_pages - 1:
            self.page_idx += 1
        await self.update_message(interaction)


@bot.command(name="kho", aliases=["okho"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_okho(ctx):
    uid = str(ctx.author.id)
    data = ensure_user(uid)
    user = data["users"][uid]
    _ensure_economy_fields(user)

    # chỉ lấy đồ chưa mặc
    items_show = [it for it in user["items"] if not it.get("equipped")]
    total_pages = max(1, (len(items_show)-1)//10 + 1)

    emb = build_kho_embed(ctx.author.display_name, user, items_show, page_idx=0, page_size=10, total_pages=total_pages)
    view = KhoView(uid, ctx.author.display_name, user, items_show, page_size=10)
    await ctx.send(embed=emb, view=view)
# ---------------------------------------------------------------------------------
# L. LỆNH OBAN – BÁN TẠP VẬT → NP
# ---------------------------------------------------------------------------------
@bot.command(name="ban", aliases=["oban"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_oban(ctx, *args):
    """
    bán tạp vật lấy NP
    - oban            → bán hết
    - oban <d|c|b|a|s> all  → bán 1 phẩm
    """
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    _ensure_economy_fields(user)
    args = [a.lower() for a in args]

    def _sell_tv(r: str, qty: int) -> int:
        lo, hi = TAP_VAT_SELL_NP_RANGE.get(r, (0, 0))
        total = 0
        for _ in range(qty):
            total += random.randint(lo, hi) if hi >= lo else 0
        user["tap_vat"][r] -= qty
        user["ngan_phi"] = int(user.get("ngan_phi", 0)) + total
        return total

    # bán hết
    if not args:
        have = False
        lines = []
        total_np = 0
        for r in ["S", "A", "B", "C", "D"]:
            qty = int(user["tap_vat"].get(r, 0))
            if qty > 0:
                have = True
                gain = _sell_tv(r, qty)
                total_np += gain
                lines.append(f"{TAP_VAT_EMOJI[r]} x{qty} → {NP_EMOJI} +{format_num(gain)}")
        if not have:
            await ctx.reply("Bạn không có Tạp Vật để bán.", mention_author=False)
            return
        save_data(data)
        await ctx.send(embed=make_embed(
            "🧾 Bán Tạp Vật",
            " • " + "\n • ".join(lines) + f"\n\nTổng: {NP_EMOJI} **{format_num(total_np)}**",
            color=0xE67E22,
            footer=ctx.author.display_name
        ))
        return

    # oban <r> all
    if len(args) == 2 and args[1] == "all" and args[0] in {"d", "c", "b", "a", "s"}:
        r = args[0].upper()
        qty = int(user["tap_vat"].get(r, 0))
        if qty <= 0:
            await ctx.reply(f"Bạn không có Tạp Vật phẩm {r}.", mention_author=False)
            return
        gain = _sell_tv(r, qty)
        save_data(data)
        await ctx.send(embed=make_embed(
            "🧾 Bán Tạp Vật",
            f"{TAP_VAT_EMOJI[r]} x{qty} → {NP_EMOJI} **+{format_num(gain)}**",
            color=RARITY_COLOR.get(r, 0x95A5A6),
            footer=ctx.author.display_name
        ))
        return

    await ctx.reply("Dùng: `oban` (bán hết) hoặc `oban <D|C|B|A|S> all`", mention_author=False)

# ---------------------------------------------------------------------------------
# M. LỆNH OBANTRANGBI – BÁN TRANG BỊ → XU
# ---------------------------------------------------------------------------------
@bot.command(name="bantrangbi", aliases=["obantrangbi"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_obantrangbi(ctx, *args):
    """
    bán trang bị rảnh để lấy Xu
    - obantrangbi all
    - obantrangbi <D|C|B|A|S> all
    """
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    _ensure_economy_fields(user)
    args = [a.lower() for a in args]

    def settle(lst):
        total_xu = 0
        for it in lst:
            sx = int(it.get("sell_xu", 0))
            if sx <= 0:
                lo, hi = EQUIP_SELL_XU_RANGE.get(it["rarity"], (0, 0))
                sx = random.randint(lo, hi) if hi >= lo else 0
                it["sell_xu"] = sx
            total_xu += sx
        user["xu"] = int(user.get("xu", 0)) + total_xu
        user.setdefault("stats", {})
        user["stats"]["sold_count"] = int(user["stats"].get("sold_count", 0)) + len(lst)
        user["stats"]["sold_value_total"] = int(user["stats"].get("sold_value_total", 0)) + total_xu
        return total_xu

    if not args:
        await ctx.reply("Cú pháp: `obantrangbi all` hoặc `obantrangbi <D|C|B|A|S> all`", mention_author=False)
        return

    if args[0] == "all":
        sell = [it for it in user["items"] if not it.get("equipped")]
        if not sell:
            await ctx.reply("Không có trang bị rảnh để bán.", mention_author=False)
            return
        total = settle(sell)
        user["items"] = [it for it in user["items"] if it.get("equipped")]
        save_data(data)
        await ctx.send(embed=make_embed(
            "🧾 Bán trang bị",
            f"Đã bán **{len(sell)}** món — Nhận {XU_EMOJI} **{format_num(total)}**",
            color=0xE67E22,
            footer=ctx.author.display_name
        ))
        return

    if len(args) == 2 and args[1] == "all" and args[0].upper() in ["D", "C", "B", "A", "S"]:
        rar = args[0].upper()
        sell = [it for it in user["items"] if (it["rarity"] == rar and not it.get("equipped"))]
        if not sell:
            await ctx.reply(f"Không có trang bị phẩm chất {rar} để bán.", mention_author=False)
            return
        total = settle(sell)
        user["items"] = [it for it in user["items"] if not (it["rarity"] == rar and not it.get("equipped"))]
        save_data(data)
        await ctx.send(embed=make_embed(
            "🧾 Bán trang bị",
            f"Đã bán **{len(sell)}** món {rar} — Nhận {XU_EMOJI} **{format_num(total)}**",
            color=RARITY_COLOR.get(rar, 0x95A5A6),
            footer=ctx.author.display_name
        ))
        return

    await ctx.reply("Cú pháp không hợp lệ. Ví dụ: `obantrangbi all` hoặc `obantrangbi D all`.", mention_author=False)
# ====================================================================================================================================


@bot.command(name="thao", aliases=["othao"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_othao(ctx, item_id: str = None):
    if item_id is None:
        await ctx.reply("📝 Cách dùng: `thao <ID>` (xem ID trong `okho`).", mention_author=False)
        return

    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    # phòng dữ liệu cũ
    if "equipped" not in user:
        user["equipped"] = {"slot_vukhi": None, "slot_aogiap": None}
    else:
        user["equipped"].setdefault("slot_vukhi", None)
        user["equipped"].setdefault("slot_aogiap", None)

    # tìm item theo ID
    items = user.get("items", [])
    target = next((it for it in items if it.get("id") == item_id), None)
    if not target:
        await ctx.reply("❗ Không tìm thấy vật phẩm với ID đó.", mention_author=False)
        return

    if not target.get("equipped"):
        await ctx.reply("⚠️ Vật phẩm này hiện không được mặc.", mention_author=False)
        return

    # xác định loại để map sang slot đúng
    item_type = (target.get("type") or "").lower()
    is_armor = item_type in ("áo giáp", "ao giap", "giáp", "giap", "armor")

    # nếu mày có slot_of thì vẫn gọi, rồi map lại
    raw_slot = slot_of(target["type"]) if "slot_of" in globals() else ("armor" if is_armor else "weapon")

    if raw_slot in ("weapon", "vukhi"):
        slot_key = "slot_vukhi"
    elif raw_slot in ("armor", "aogiap", "giap"):
        slot_key = "slot_aogiap"
    else:
        # fallback
        slot_key = raw_slot

    # tháo
    user["equipped"][slot_key] = None
    target["equipped"] = False
    save_data(data)

    emb = make_embed(
        title="🪶 Tháo trang bị",
        description=f"Đã tháo **{target['name']}** (ID `{target['id']}`). Kiểm tra lại `okho`.",
        color=0x95A5A6,
        footer=ctx.author.display_name
    )
    await ctx.send(embed=emb)






# ================================================================
# 🔽 ADD-ON GAMEPLAY BT-1727-KIM
# (dán xuống cuối file bot hiện tại của bạn)
# ================================================================
import random
import math
import discord
from discord.ext import commands

# ------------------------------------------------
# 1) BẢNG RANGE STAT THEO PHẨM & LOẠI ĐỒ
# ------------------------------------------------
# Đây là con số mẫu để bạn vặn sau. Ý tưởng:
# - Vũ khí: chỉ công/tốc
# - Giáp  : chỉ thủ/sống sót
WEAPON_STAT_RANGE = {
    "S": {
        "atk_physical": (520, 720),
        "atk_magic": (520, 720),
        "atk_team": (120, 180),
        "crit": (9, 15),           # %
        "agility": (7, 12),        # %
        "cast_speed": (7, 12),     # %
        "lifesteal": (5, 10),      # %
        "mana_regen": (6, 12),
        "cdr": (6, 10),            # %
        "damage_bonus": (6, 12),   # %
        "control": (6, 10),        # %
    },
    "A": {
        "atk_physical": (280, 400),
        "atk_magic": (280, 400),
        "atk_team": (70, 120),
        "crit": (6, 10),
        "agility": (4, 8),
        "cast_speed": (4, 8),
        "lifesteal": (3, 7),
        "mana_regen": (4, 8),
        "cdr": (3, 6),
        "damage_bonus": (3, 6),
        "control": (3, 5),
    },
}

ARMOR_STAT_RANGE = {
    "S": {
        "defense": (180, 260),
        "res_magic": (9, 15),      # %
        "hp": (2800, 3500),
        "regen": (5, 9),           # HP/5s
        "damage_reduce": (4, 7),   # %
        "control": (4, 7),         # kháng khống
        "agility": (2, 4),
        "mana_regen": (4, 8),
    },
    "A": {
        "defense": (110, 170),
        "res_magic": (5, 10),
        "hp": (1600, 2300),
        "regen": (3, 6),
        "damage_reduce": (2, 4),
        "control": (2, 4),
        "agility": (1, 3),
        "mana_regen": (2, 5),
    },
}

# map mã stat -> text hiển thị
STAT_LABEL = {
    "atk_physical": "Tấn công vật lý",
    "atk_magic": "Tấn công phép",
    "atk_team": "Tấn công nhóm",
    "crit": "Chí mạng",
    "control": "Khống chế",
    "defense": "Phòng thủ",
    "res_magic": "Kháng phép",
    "hp": "Máu tối đa",
    "regen": "Phục hồi",
    "damage_reduce": "Giảm sát thương nhận",
    "lifesteal": "Hút máu",
    "mana_regen": "Hồi năng lượng",
    "agility": "Nhanh nhẹn",
    "cast_speed": "Tốc độ ra chiêu",
    "cdr": "Giảm hồi chiêu",
    "damage_bonus": "Tăng sát thương tổng",
    "all_bonus": "Dòng Toàn Diện",
}

# ------------------------------------------------
# 2) BẢNG WEIGHT THEO MÔN PHÁI
# ------------------------------------------------
CLASS_STAT_WEIGHT = {
    # sát thủ kiếm
    "Toái Mộng": {
        "atk_physical": 3,
        "crit": 3,
        "agility": 2,
        "cdr": 1,
    },
    # thương đấu sĩ hút máu
    "Huyết Hà": {
        "atk_physical": 2,
        "lifesteal": 3,
        "damage_bonus": 2,
        "control": 1,
    },
    # đàn phép
    "Thần Tương": {
        "atk_magic": 3,
        "crit": 2,
        "cast_speed": 2,
        "mana_regen": 1,
    },
    # trượng khống chế
    "Cửu Linh": {
        "atk_magic": 2,
        "control": 3,
        "mana_regen": 2,
        "cdr": 1,
    },
    # dải lụa support
    "Tố Vấn": {
        "atk_team": 3,
        "mana_regen": 2,
        "cdr": 1,
        "regen": 1,
    },
    # găng tay tanker
    "Thiết Y": {
        # vũ khí vẫn công, nhưng giáp ưu tiên thủ
        "defense": 3,
        "hp": 3,
        "damage_reduce": 2,
        "control": 1,
    },
}


# ------------------------------------------------
# 4) HÀM SINH CHỈ SỐ CHO ITEM
# (gọi chỗ bạn generate_item(...))
# ------------------------------------------------
def _rand_from_range(rng):
    return random.randint(rng[0], rng[1])

def fill_stats_for_item(item: dict):
    """
    Bổ sung stats + lực chiến + lore cho item mới sinh.
    item phải có:
        rarity, type, name, phai (có thể None)
    """
    rarity = item.get("rarity", "D")
    it_type = item.get("type", "")
    phai = item.get("phai")  # môn phái dùng

    # xác định là vũ khí hay giáp
    is_weapon = it_type not in ("Áo Giáp", "Giáp", "Giáp chung")

    stats = []
    # xác định pool theo loại + phẩm
    if is_weapon and rarity in WEAPON_STAT_RANGE:
        pool = WEAPON_STAT_RANGE[rarity]
        # số dòng theo phẩm
        line_count = 5 if rarity == "S" else 3
        # lấy weight theo phái để ưu tiên
        weights = CLASS_STAT_WEIGHT.get(phai, {})
        # chọn random stat có ưu tiên
        possible = list(pool.keys())
        chosen = []
        for _ in range(line_count):
            stat = random.choices(
                population=possible,
                weights=[weights.get(s, 1) for s in possible],
                k=1
            )[0]
            if stat in chosen:
                continue
            rng = pool[stat]
            val = _rand_from_range(rng)
            stats.append({"code": stat, "label": STAT_LABEL.get(stat, stat), "val": val})
            chosen.append(stat)

    elif (not is_weapon) and rarity in ARMOR_STAT_RANGE:
        pool = ARMOR_STAT_RANGE[rarity]
        line_count = 5 if rarity == "S" else 3
        possible = list(pool.keys())
        chosen = []
        # giáp chung thì coi như không ưu tiên phái
        for _ in range(line_count):
            stat = random.choice(possible)
            if stat in chosen:
                continue
            rng = pool[stat]
            val = _rand_from_range(rng)
            stats.append({"code": stat, "label": STAT_LABEL.get(stat, stat), "val": val})
            chosen.append(stat)

    item["stats"] = stats

    # 💫 5% chance Hoàn Hảo cho S
    item["hoan_hao"] = False
    if rarity == "S" and random.random() < 0.05:
        item["hoan_hao"] = True

    # LORE: ưu tiên theo tên
    lore = ITEM_LORE_BY_NAME.get(item.get("name", ""), None)
    if lore:
        item["lore"] = lore

    # tính lực chiến
    item["luc_chien"] = calc_luc_chien(item)
    return item


# ------------------------------------------------
# 5) HÀM TÍNH LỰC CHIẾN
# ------------------------------------------------
STAT_LC_WEIGHT = {
    # công
    "atk_physical": 1.0,
    "atk_magic": 1.0,
    "atk_team": 0.6,
    "crit": 35,
    "agility": 25,
    "cast_speed": 25,
    "cdr": 30,
    "damage_bonus": 40,
    "lifesteal": 35,
    # thủ
    "defense": 2.0,
    "hp": 0.9,
    "res_magic": 40,
    "damage_reduce": 50,
    "regen": 15,
    "control": 30,
    "mana_regen": 15,
    "all_bonus": 80,
}

def calc_luc_chien(item: dict) -> int:
    base = 0
    for st in item.get("stats", []):
        code = st["code"]
        val = st["val"]
        w = STAT_LC_WEIGHT.get(code, 1)
        base += val * w

    # bonus từ hoàn mỹ
    perfect = int(item.get("perfect", item.get("hoan_my", 50)))
    base = int(base * (1 + perfect / 200.0))  # perfect 100% → x1.5

    # bonus dòng Hoàn Hảo
    if item.get("hoan_hao"):
        base = int(base * 1.10)

    return max(1, base)
# ------------------------------------------------
# ------------------------------------------------
# ------------------------------------------------
# ------------------------------------------------

# đảm bảo có bảng tên phái hiển thị
PHAI_LABEL_FROM_KEY = {
    "thiet_y": "Thiết Y",
    "huyet_ha": "Huyết Hà",
    "than_tuong": "Thần Tương",
    "to_van": "Tố Vấn",
    "cuu_linh": "Cửu Linh",
    "toai_mong": "Toái Mộng",
}

@bot.command(name="mac", aliases=["omac"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_omac(ctx, item_id: str = None):
    if not item_id:
        await ctx.reply("📝 Cách dùng: `mac <ID>` (xem ID trong `okho`).", mention_author=False)
        return

    uid = str(ctx.author.id)
    data = ensure_user(uid)
    user = data["users"][uid]
    _ensure_economy_fields(user)

    # luôn có 2 slot này
    user.setdefault("equipped", {
        "slot_vukhi": None,
        "slot_aogiap": None,
    })

    # tìm item trong kho
    items = user.get("items", [])
    item = next((it for it in items if it.get("id") == item_id), None)
    if not item:
        await ctx.reply("❗ Không tìm thấy vật phẩm với ID đó.", mention_author=False)
        return

    # xác định loại để tự chọn slot (KHÔNG dùng slot_of nữa)
    it_type = (item.get("type") or "").lower()
    is_armor = it_type in ("áo giáp", "ao giap", "giáp", "giap", "armor")

    # ===== chặn theo môn phái =====
    user_phai = user.get("class")
    item_phai = item.get("phai") or item.get("class")

    if not is_armor:
        # đây là vũ khí
        if item_phai and not user_phai:
            await ctx.reply(
                "⚠️ Bạn chưa gia nhập môn phái nên không thể mặc vũ khí này.\n"
                "Dùng `omonphai` để gia nhập trước.",
                mention_author=False,
            )
            return
        if item_phai and user_phai and item_phai != user_phai:
            nice_user = PHAI_LABEL_FROM_KEY.get(user_phai, user_phai)
            nice_item = PHAI_LABEL_FROM_KEY.get(item_phai, item_phai)
            await ctx.reply(
                f"🚫 Vũ khí này dành cho phái **{nice_item}**, bạn đang là **{nice_user}**.",
                mention_author=False,
            )
            return

    # ===== chọn slot =====
    if is_armor:
        slot = "slot_aogiap"
    else:
        slot = "slot_vukhi"

    # slot đang bận thì báo
    cur_id = user["equipped"].get(slot)
    if cur_id:
        cur_item = next((it for it in items if it.get("id") == cur_id), None)
        if cur_item:
            await ctx.reply(
                f"🔧 Slot này đang mặc **{cur_item['name']}** (ID `{cur_item['id']}`).\n"
                f"Dùng `othao {cur_item['id']}` để tháo trước.",
                mention_author=False,
            )
            return

    # ===== mặc =====
    item["equipped"] = True
    user["equipped"][slot] = item["id"]
    save_data(data)

    emo = RARITY_EMOJI.get(item.get("rarity", "D"), "🔸")
    emb = make_embed(
        title="🪄 Mặc trang bị",
        description=f"Bạn đã mặc {emo} **{item['name']}** (ID `{item['id']}`)",
        color=RARITY_COLOR.get(item.get("rarity", "D"), 0x00FFFF),
        footer=ctx.author.display_name,
    )
    await ctx.send(embed=emb)
# ------------------------------------------------


# ================================================================
# NHANVAT FULL — 2 TAB (NHÂN VẬT / TRANG BỊ)
# ================================================================
# YÊU CẦU FILE GỐC ĐÃ CÓ:
# - bot = commands.Bot(...)
# - make_embed(title, description=..., color=..., footer=...)
# - format_num(x)
# - ensure_user(user_id) -> dict toàn bộ data
# - save_data(data)
# - user["items"] là list item như bạn đang dùng
# - user["equipped"] dùng key "slot_vukhi", "slot_aogiap" (nếu khác thì sửa ở dưới)
# - đã có RARITY_EMOJI, XU_EMOJI, LC_EMOJI (nếu chưa thì copy luôn 3 cái này)
# ================================================================


# ======================================================================
# 0. CONSTANT / BẢNG TRA CHUNG
# ======================================================================

# tên phái có dấu – dùng cho onhanvat, omac báo sai phái, oxem
PHAI_DISPLAY = {
    "thiet_y": "Thiết Y",
    "huyet_ha": "Huyết Hà",
    "than_tuong": "Thần Tương",
    "to_van": "Tố Vấn",
    "cuu_linh": "Cửu Linh",
    "toai_mong": "Toái Mộng",
}

# base stat theo phái – đây là stat gốc khi LV1
# tách thành 3 nhóm như bạn nói: công / thủ / năng lượng
CLASS_BASE_STATS = {
    "thiet_y":   {"offense": 60,  "defense": 120, "energy": 50},
    "huyet_ha":  {"offense": 95,  "defense": 80,  "energy": 60},
    "than_tuong":{"offense": 110, "defense": 60,  "energy": 95},
    "to_van":    {"offense": 70,  "defense": 70,  "energy": 120},
    "cuu_linh":  {"offense": 85,  "defense": 65,  "energy": 110},
    "toai_mong": {"offense": 125, "defense": 55,  "energy": 50},
}

# bonus mỗi cấp theo phái – để level lên còn biết + gì
CLASS_LEVEL_BONUS = {
    "thiet_y":   {"offense": 3,  "defense": 8, "energy": 2},
    "huyet_ha":  {"offense": 6,  "defense": 4, "energy": 3},
    "than_tuong":{"offense": 7,  "defense": 3, "energy": 6},
    "to_van":    {"offense": 4,  "defense": 4, "energy": 7},
    "cuu_linh":  {"offense": 5,  "defense": 3, "energy": 7},
    "toai_mong": {"offense": 8,  "defense": 2, "energy": 3},
}

# nếu user chưa chọn phái thì dùng bộ này
DEFAULT_BASE_STATS = {"offense": 50, "defense": 50, "energy": 50}

# bảng nhãn stat để in cho đẹp ở tab Chi tiết
STAT_LABELS = {
    "atk_physical": "Tấn công vật lý",
    "atk_magic": "Tấn công phép",
    "atk_team": "Tấn công nhóm",
    "crit": "Chí mạng",
    "control": "Khống chế / kháng khống",
    "defense": "Phòng thủ",
    "res_magic": "Kháng phép",
    "hp": "Máu tối đa",
    "regen": "Phục hồi",
    "damage_reduce": "Giảm sát thương",
    "lifesteal": "Hút máu",
    "mana_regen": "Hồi năng lượng",
    "agility": "Nhanh nhẹn",
    "cast_speed": "Tốc độ ra chiêu",
    "cdr": "Giảm hồi chiêu",
    "damage_bonus": "Tăng sát thương tổng",
    "all_bonus": "Toàn diện",
}

# emoji bạn dùng
XU_EMOJI = "<a:tienxu:1431717943980589347>"
LC_EMOJI = "<:3444:1434780655794913362>"

# nếu file gốc đã có RARITY_EMOJI thì bỏ đoạn này
RARITY_EMOJI = globals().get("RARITY_EMOJI", {
    "D": "🟦",
    "C": "🟩",
    "B": "🟨",
    "A": "🟪",
    "S": "🟥",
})


# ======================================================================
# 1. EXP CẦN ĐỂ LÊN CẤP
# ======================================================================

def get_exp_required_for_level(level: int) -> int:
    """
    exp để lên level N.
    level 1 -> 2: 100
    mỗi level sau tăng 20.
    bạn thích thì đổi.
    """
    base = 100
    step = 20
    if level <= 1:
        return base
    return base + (level - 1) * step


# ======================================================================
# 2. HÀM CỘNG CHỈ SỐ TỪ TRANG BỊ ĐANG MẶC
# ======================================================================

def _parse_number_from_val(v):
    """stat trong item có thể là '12%' hoặc số, ta tách thành (giá trị, is_percent)"""
    if isinstance(v, (int, float)):
        return v, False
    if isinstance(v, str) and v.endswith("%"):
        try:
            return float(v[:-1]), True
        except Exception:
            return 0, True
    try:
        return float(v), False
    except Exception:
        return 0, False


def sum_equipment_stats_for_user(user: dict) -> dict:
    """
    trả về dict: { code_stat: {"flat":..., "percent":...}, ... }
    để tab Chi tiết in ra đúng
    """
    eq = user.get("equipped", {})
    items = user.get("items", [])
    # tìm vật phẩm đang mặc
    equipped_items = []
    for slot_id in eq.values():
        if not slot_id:
            continue
        it = next((x for x in items if x.get("id") == slot_id), None)
        if it:
            equipped_items.append(it)

    result = {}
    for it in equipped_items:
        stats = it.get("stats", [])
        # nếu có dòng hoàn hảo → nhân 1.1
        hoan_mul = 1.1 if it.get("hoan_hao") else 1.0
        for st in stats:
            code = st.get("code") or "unknown"
            val = st.get("val", 0)
            num, is_pct = _parse_number_from_val(val)
            num = num * hoan_mul
            if code not in result:
                result[code] = {"flat": 0.0, "percent": 0.0}
            if is_pct:
                result[code]["percent"] += num
            else:
                result[code]["flat"] += num
    return result


# ======================================================================
# 3. HÀM TÍNH CHỈ SỐ NHÂN VẬT TỔNG
# ======================================================================

def calc_character_stats(user: dict) -> dict:
    """
    trả về:
    {
      "offense": {"base":..., "equip":..., "total":...},
      "defense": {...},
      "energy": {...},
      "raw_equipment_stats": {...}   # để tab chi tiết xài
    }
    """
    user_class = user.get("class")
    level = int(user.get("level", 1))
    base = CLASS_BASE_STATS.get(user_class, DEFAULT_BASE_STATS).copy()
    bonus = CLASS_LEVEL_BONUS.get(user_class, {"offense": 3, "defense": 3, "energy": 3})

    # cộng bonus theo level
    if level > 1:
        lv_up = level - 1
        base["offense"] += bonus.get("offense", 0) * lv_up
        base["defense"] += bonus.get("defense", 0) * lv_up
        base["energy"] += bonus.get("energy", 0) * lv_up

    # cộng từ đồ
    equip_stats = sum_equipment_stats_for_user(user)

    # chuyển từ từng code stat sang 3 nhóm
    # tấn công lấy mấy code này
    offense_codes = ("atk_physical", "atk_magic", "atk_team", "crit", "damage_bonus", "lifesteal", "cast_speed", "agility", "cdr", "control")
    defense_codes = ("defense", "res_magic", "hp", "regen", "damage_reduce", "control", "agility")
    energy_codes = ("mana_regen", "cast_speed", "cdr")

    off_add = 0
    def_add = 0
    en_add = 0

    for code, valdict in equip_stats.items():
        flat = valdict["flat"]
        percent = valdict["percent"]
        # tấn công
        if code in offense_codes:
            off_add += flat
            off_add += base["offense"] * (percent / 100.0)
        # phòng thủ
        if code in defense_codes:
            def_add += flat
            def_add += base["defense"] * (percent / 100.0)
        # năng lượng
        if code in energy_codes:
            en_add += flat
            en_add += base["energy"] * (percent / 100.0)

    return {
        "offense": {
            "base": int(base["offense"]),
            "equip": int(off_add),
            "total": int(base["offense"] + off_add),
        },
        "defense": {
            "base": int(base["defense"]),
            "equip": int(def_add),
            "total": int(base["defense"] + def_add),
        },
        "energy": {
            "base": int(base["energy"]),
            "equip": int(en_add),
            "total": int(base["energy"] + en_add),
        },
        "raw_equipment_stats": equip_stats,
    }


# ======================================================================
# 4. LỰC CHIẾN TỔNG
# ======================================================================

def calc_user_luc_chien(user: dict) -> int:
    eq = user.get("equipped", {})
    items = user.get("items", [])
    total = 0
    for slot_id in eq.values():
        if not slot_id:
            continue
        it = next((x for x in items if x.get("id") == slot_id), None)
        if it:
            total += int(it.get("luc_chien", 0))
    return total


# ======================================================================
# 5. EMBED BUILDER CHO 3 TAB
# ======================================================================

import discord
from discord.ext import commands

def build_nv_embed(ctx, target_user: dict, target_member: discord.Member) -> discord.Embed:
    user_class = target_user.get("class")
    phai_name = PHAI_DISPLAY.get(user_class, "Chưa chọn")
    level = int(target_user.get("level", 1))
    exp = int(target_user.get("exp", 0))
    exp_need = get_exp_required_for_level(level)

    char_stats = calc_character_stats(target_user)
    lc_total = calc_user_luc_chien(target_user)

    # thời trang
    fashion = target_user.get("fashion")
    if fashion:
        fashion_text = f"{EMOJI_THIENTHUONG} Thời trang: **{fashion}**"
    else:
        fashion_text = f"{EMOJI_THIENTHUONG} Thời trang: — Chưa có —"

    emb = discord.Embed(
        title=f"👤 Nhân vật — {target_member.display_name}",
        description=(
            f"Phái: **{phai_name}**\n"
            f"Cấp: **{level}**  •  EXP: **{exp}/{exp_need}**\n"
            f"Lực chiến: {LC_EMOJI} **{lc_total:,}**\n\n"
            f"{fashion_text}\n"
        ),
        color=0x9B59B6,
    )
    emb.add_field(
        name="Tấn công",
        value=f"{char_stats['offense']['total']:,} (**+{char_stats['offense']['equip']:,}**)",
        inline=True,
    )
    emb.add_field(
        name="Phòng thủ",
        value=f"{char_stats['defense']['total']:,} (**+{char_stats['defense']['equip']:,}**)",
        inline=True,
    )
    emb.add_field(
        name="Năng lượng",
        value=f"{char_stats['energy']['total']:,} (**+{char_stats['energy']['equip']:,}**)",
        inline=True,
    )
    emb.set_footer(text=f"Bấm Trang bị / Chi tiết để xem thêm • {target_member.display_name}")
    return emb


def build_trang_bi_embed(ctx, target_user: dict, target_member: discord.Member) -> discord.Embed:
    eq = target_user.get("equipped", {})
    items = target_user.get("items", [])

    def _find_item(item_id):
        if not item_id:
            return None
        return next((x for x in items if x.get("id") == item_id), None)

    def _render_item(slot_label: str, it: dict | None):
        if not it:
            return f"• {slot_label}: — Chưa mặc —"
        emo = RARITY_EMOJI.get(it.get("rarity", "D"), "🔸")
        name = it.get("name", "Trang bị")
        iid = it.get("id", "????")
        perfect = int(it.get("perfect", 0))
        lc = int(it.get("luc_chien", 0))
        stats = it.get("stats", [])
        lines = [
            f"• {slot_label}: {emo} **{name}** (ID `{iid}`)",
            f"  Hoàn mỹ: 💠 {perfect}%   {LC_EMOJI} {lc:,}",
        ]
        if it.get("hoan_hao"):
            lines.append("  💫 Hoàn Hảo: +10% tất cả chỉ số")
        for st in stats:
            label = st.get("label") or st.get("code", "Thuộc tính")
            val = st.get("val", 0)
            lines.append(f"  + {label} {val}")
        return "\n".join(lines)

    vu_khi = _find_item(eq.get("slot_vukhi"))
    giap = _find_item(eq.get("slot_aogiap"))

    desc_lines = [
        _render_item("Vũ khí", vu_khi),
        "",
        _render_item("Áo giáp", giap),
    ]

    emb = discord.Embed(
        title=f"Trang bị — {target_member.display_name}",
        description="\n".join(desc_lines),
        color=0x3498DB,
    )
    emb.set_footer(text="Dùng oxem <ID> để xem chi tiết 1 món.")
    return emb


def build_chi_tiet_embed(ctx, target_user: dict, target_member: discord.Member) -> discord.Embed:
    stats = calc_character_stats(target_user)
    equip_raw = stats["raw_equipment_stats"]

    lines = []
    for code, data in equip_raw.items():
        label = STAT_LABELS.get(code, code)
        flat = data["flat"]
        pct = data["percent"]
        parts = []
        if flat:
            parts.append(f"+{flat:g}")
        if pct:
            parts.append(f"+{pct:g}%")
        lines.append(f"{label}: " + "  ".join(parts))

    if not lines:
        lines.append("Trang bị hiện tại không cộng chỉ số nào.")

    emb = discord.Embed(
        title=f"Chi tiết chỉ số — {target_member.display_name}",
        description="\n".join(lines),
        color=0x1ABC9C,
    )
    return emb


# ======================================================================
# 6. VIEW 3 NÚT
# ======================================================================
class OnhanvatView(discord.ui.View):
    def __init__(self, ctx, target_user: dict, target_member: discord.Member):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.target_user = target_user
        self.target_member = target_member
        self.owner_id = ctx.author.id
        self.current_tab = "nv"  # nv | tb | ct

        # nút đầu tiên disable luôn vì đang ở tab nhân vật
        self.btn_nv.disabled = True

    async def _edit(self, interaction: discord.Interaction, tab: str):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❗ Không phải nhân vật của bạn.", ephemeral=True)
            return

        self.current_tab = tab
        # bật/tắt nút
        self.btn_nv.disabled = (tab == "nv")
        self.btn_tb.disabled = (tab == "tb")
        self.btn_ct.disabled = (tab == "ct")

        if tab == "nv":
            emb = build_nv_embed(self.ctx, self.target_user, self.target_member)
        elif tab == "tb":
            emb = build_trang_bi_embed(self.ctx, self.target_user, self.target_member)
        else:
            emb = build_chi_tiet_embed(self.ctx, self.target_user, self.target_member)

        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="Nhân vật", style=discord.ButtonStyle.secondary)
    async def btn_nv(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "nv")

    @discord.ui.button(label="Trang bị", style=discord.ButtonStyle.secondary)
    async def btn_tb(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "tb")

    @discord.ui.button(label="Chi tiết", style=discord.ButtonStyle.secondary)
    async def btn_ct(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "ct")


# ======================================================================
# 7. LỆNH onhanvat
# ======================================================================
@bot.command(name="nhanvat", aliases=["onhanvat", "nv"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_onhanvat(ctx, member: discord.Member = None):
    data = load_data()          # <— thêm dòng này
    # chọn target
    target = member or ctx.author
    uid = str(target.id)
    data = ensure_user(uid)
    user = data["users"][uid]

    # đảm bảo có mấy field mới
    user.setdefault("class", None)
    user.setdefault("level", 1)
    user.setdefault("exp", 0)
    user.setdefault("fashion", None)
    user.setdefault("equipped", {"slot_vukhi": None, "slot_aogiap": None})

    # nếu bạn muốn lưu lại khi bổ sung field mới:
    save_data(data)

    emb = build_nv_embed(ctx, user, target)
    view = OnhanvatView(ctx, user, target)
    await ctx.reply(embed=emb, view=view, mention_author=False)


# ======================================================================
# 8. _open_one_chest BẢN CHUẨN (dán đè lên bản cũ)
# ======================================================================
# nếu chưa import random thì thêm:
import random

# nếu chưa có mấy bảng này thì giữ luôn
ITEM_DROP_RATE_BY_CHEST = globals().get("ITEM_DROP_RATE_BY_CHEST", {
    "S": 0.20,
    "A": 0.10,
    "B": 0.05,
    "C": 0.03,
    "D": 0.01,
})
NP_BY_CHEST = globals().get("NP_BY_CHEST", {
    "S": 5000,
    "A": 2000,
    "B": 800,
    "C": 300,
    "D": 100,
})
XU_RANGE_BY_CHEST = globals().get("XU_RANGE_BY_CHEST", {
    "S": (10, 40),
    "A": (5, 15),
    "B": (2, 6),
    "C": (1, 3),
    "D": (0, 1),
})


def _open_one_chest(user: dict, r: str):
    # trừ rương
    user["rungs"][r] = int(user["rungs"].get(r, 0)) - 1

    # NP
    gp = NP_BY_CHEST.get(r, 0)
    user["ngan_phi"] = int(user.get("ngan_phi", 0)) + gp

    # Xu
    xr = XU_RANGE_BY_CHEST.get(r, (0, 0))
    xu_gain = random.randint(xr[0], xr[1]) if xr[1] >= xr[0] else 0
    user["xu"] = int(user.get("xu", 0)) + xu_gain

    # tạp vật
    tv = {"rarity": r, "count": 1}
    user["tap_vat"][r] = int(user["tap_vat"].get(r, 0)) + 1

    # rơi trang bị
    item = None
    prob = ITEM_DROP_RATE_BY_CHEST.get(r, 0.0)
    if prob > 0 and (random.random() < prob):
        # chú ý: ở file của bạn phải có generate_item_full, nếu chưa có thì thay bằng generate_item
        item = generate_item_full(r, user, user["items"])
        user["items"].append(item)

    return gp, xu_gain, tv, item




# ====================================================================================================================================
# 🧍 XEM BẮT ĐẦU
# ====================================================================================================================================

# emoji phẩm chất giữ nguyên như file gốc
RARITY_EMOJI = {
    "D": "<a:D12:1432473477616505023>",
    "C": "<a:C11:1432467636943454315>",
    "B": "<a:B11:1432467633932075139>",
    "A": "<a:A11:1432467623051919390>",
    "S": "<a:S11:1432467644761509948>",
}

LC_EMOJI = "<:3444:1434780655794913362>"

# emoji Xu nếu bạn chưa có ở trên thì thêm
XU_EMOJI = "<a:tienxu:1431717943980589347>"

# giá bán mặc định theo phẩm
DEFAULT_SELL_XU_BY_RARITY = {
    "S": 12_000,
    "A": 6_800,
    "B": 2_400,
    "C": 900,
    "D": 300,
}

# map key -> tên có dấu để hiển thị đẹp
PHAI_LABELS = {
    "thiet_y": "Thiết Y",
    "huyet_ha": "Huyết Hà",
    "than_tuong": "Thần Tương",
    "to_van": "Tố Vấn",
    "cuu_linh": "Cửu Linh",
    "toai_mong": "Toái Mộng",
}


def _build_item_embed(ctx: commands.Context, item: dict, user_display_name: str = None) -> discord.Embed:
    """Tạo 1 embed xem chi tiết 1 trang bị (dùng cho cả oxem ID và oxem all)."""
    rarity = item.get("rarity", "D")
    re = RARITY_EMOJI.get(rarity, "💠")
    name = item.get("name", "Vật phẩm không tên")
    iid = item.get("id", "????")
    perfect = int(item.get("perfect", 0))
    luc_chien = int(item.get("luc_chien", 0))
    it_type = item.get("type", "Trang bị")

    # phái hiển thị có dấu
    raw_phai = item.get("phai")
    phai_hien = PHAI_LABELS.get(raw_phai, "Dùng chung") if raw_phai else "Dùng chung"

    # lấy giá bán: ưu tiên trong item, không có thì lấy theo phẩm
    raw_sell = item.get("sell_xu")
    if raw_sell is None:
        sell_xu = DEFAULT_SELL_XU_BY_RARITY.get(rarity, 0)
    else:
        sell_xu = int(raw_sell)

    lore = item.get("lore")
    hoan_hao = bool(item.get("hoan_hao", False))
    stats = item.get("stats", [])

    emb = make_embed(
        title=f"{re} {name}",
        description=(
            f"ID: `{iid}`\n"
            f"Hoàn mỹ: 💠 **{perfect}%**\n"
            f"Lực chiến: {LC_EMOJI} **{format_num(luc_chien)}**"
        ),
        color=0x9B59B6,
        footer=(user_display_name or ctx.author.display_name)
    )

    # Thuộc tính
    if stats:
        lines = []
        for st in stats:
            label = st.get("label") or st.get("code", "Thuộc tính")
            val = st.get("val", 0)
            lines.append(f"+ {label} {val}")
        emb.add_field(name="Thuộc tính", value="\n".join(lines), inline=False)
    else:
        emb.add_field(name="Thuộc tính", value="(Trang bị này chưa có thuộc tính hiển thị)", inline=False)

    # Dòng Hoàn Hảo
    if hoan_hao:
        emb.add_field(
            name="💫 Hoàn Hảo",
            value="+10% tất cả chỉ số của trang bị này",
            inline=False
        )

    # Thông tin
    info_lines = [
        f"Loại: **{it_type}**",
        f"Môn phái dùng: **{phai_hien}**",
        f"Giá bán: {XU_EMOJI} **{format_num(sell_xu)}** Xu",
    ]
    emb.add_field(name="Thông tin", value="\n".join(info_lines), inline=False)

    # Lore
    if lore:
        emb.add_field(name="Mô tả", value=lore, inline=False)

    return emb


class OxemAllView(discord.ui.View):
    def __init__(self, ctx: commands.Context, items: list):
        super().__init__(timeout=180.0)
        self.ctx = ctx
        self.author_id = ctx.author.id
        self.items = items
        self.index = 0  # bắt đầu từ item đầu tiên

    async def _refresh(self, interaction: discord.Interaction):
        # chặn người khác bấm
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❗ Chỉ người gọi lệnh mới xem được danh sách này.", ephemeral=True)
            return

        item = self.items[self.index]
        emb = _build_item_embed(self.ctx, item, user_display_name=self.ctx.author.display_name)
        emb.set_footer(text=f"Trang {self.index+1}/{len(self.items)} — {self.ctx.author.display_name}")

        # bật/tắt nút
        self.prev_btn.disabled = (self.index == 0)
        self.next_btn.disabled = (self.index == len(self.items) - 1)

        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="◀ Trước", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
        await self._refresh(interaction)

    @discord.ui.button(label="Tiếp ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.items) - 1:
            self.index += 1
        await self._refresh(interaction)


@bot.command(name="xem", aliases=["oxem"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_oxem(ctx, item_id: str = None):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    # oxem all
    if item_id is not None and item_id.lower() == "all":
        items = list(user.get("items", []))
        if not items:
            await ctx.reply("Bạn không có trang bị nào để xem.", mention_author=False)
            return

        rarity_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
        items.sort(key=lambda it: (
            rarity_order.get(it.get("rarity", "D"), 99),
            -int(it.get("luc_chien", 0))
        ))

        first = items[0]
        emb = _build_item_embed(ctx, first, user_display_name=ctx.author.display_name)
        emb.set_footer(text=f"Trang 1/{len(items)} — {ctx.author.display_name}")

        view = OxemAllView(ctx, items)
        await ctx.send(embed=emb, view=view)
        return

    # oxem <ID>
    if item_id is None:
        await ctx.reply("📝 Cách dùng: `oxem <ID>` hoặc `oxem all`.", mention_author=False)
        return

    it = next((x for x in user.get("items", []) if x.get("id") == item_id), None)
    if not it:
        await ctx.reply("❗ Không tìm thấy trang bị với ID đó.", mention_author=False)
        return

    emb = _build_item_embed(ctx, it, user_display_name=ctx.author.display_name)
    await ctx.send(embed=emb)

# ====================================================================================================================================
# 🧍 XEM KẾT THÚC
# ====================================================================================================================================


import discord
from discord.ext import commands
import asyncio, datetime, pytz, time, random

# ======================================================
# 🧭 LỆNH GIA NHẬP MÔN PHÁI
# ======================================================


# =====================================================================
# 🔰 MÔN PHÁI — chọn / đổi / hiển thị
# =====================================================================

# ================== MÔN PHÁI ==================
from datetime import datetime, timedelta, timezone

TZ_GMT7 = timezone(timedelta(hours=7))

PHAI_INFO = {
    "thiet_y": "Đóng vai chống chịu/tanker, thủ trâu, bảo kê tuyến sau.",
    "huyet_ha": "Đấu sĩ hút máu, đánh lâu dài, train quái khỏe.",
    "than_tuong": "Pháp sư đánh xa, cấu rỉa, có khống chế.",
    "to_van": "Hỗ trợ / hồi phục, bảo vệ đồng đội.",
    "cuu_linh": "Triệu hồi / quần thể, mạnh PvE nhưng máu mỏng.",
    "toai_mong": "Sát thủ DPS, chí mạng cao, dồn sát thương nhanh.",
}

# label để hiển thị, key để lưu vào user["class"]
PHAI_BUTTONS = [
    ("Thiết Y", "thiet_y"),
    ("Huyết Hà", "huyet_ha"),
    ("Thần Tương", "than_tuong"),
    ("Tố Vấn", "to_van"),
    ("Cửu Linh", "cuu_linh"),
    ("Toái Mộng", "toai_mong"),
]

# map key -> tên hiển thị đẹp
PHAI_DISPLAY = {
    "thiet_y": "Thiết Y",
    "huyet_ha": "Huyết Hà",
    "than_tuong": "Thần Tương",
    "to_van": "Tố Vấn",
    "cuu_linh": "Cửu Linh",
    "toai_mong": "Toái Mộng",
}



PHAI_COOLDOWN_HOURS = 24
PHAI_REJOIN_COST_XU = 10_000


class PhaiView(discord.ui.View):
    def __init__(self, user_id: str, current_class: str | None):
        super().__init__(timeout=120)
        self.user_id = user_id
        for label, key in PHAI_BUTTONS:
            is_current = (current_class == key)
            btn = self.PhaiButton(label, key, user_id, is_current)
            self.add_item(btn)

    class PhaiButton(discord.ui.Button):
        def __init__(self, label: str, key: str, user_id: str, is_current: bool):
            style = discord.ButtonStyle.secondary if is_current else discord.ButtonStyle.primary
            super().__init__(label=label, style=style, disabled=is_current)
            self.phai_key = key
            self.user_id = user_id

        async def callback(self, interaction: discord.Interaction):
            # chỉ chủ lệnh được bấm
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❗ Không phải lựa chọn của bạn.", ephemeral=True)
                return

            data = ensure_user(self.user_id)
            user = data["users"][self.user_id]
            _ensure_economy_fields(user)

            now = datetime.now(TZ_GMT7)
            last = user.get("phai_last_change_ts")

            # kiểm tra cooldown
            if last:
                last_dt = datetime.fromtimestamp(last, TZ_GMT7)
                diff = now - last_dt
                if diff < timedelta(hours=PHAI_COOLDOWN_HOURS):
                    remain_dt = last_dt + timedelta(hours=PHAI_COOLDOWN_HOURS)
                    remain = remain_dt - now
                    h = int(remain.total_seconds() // 3600)
                    m = int((remain.total_seconds() % 3600) // 60)
                    await interaction.response.send_message(
                        f"⏳ Bạn đã chọn môn phái rồi. Chờ thêm **{h}h{m}m** để đổi.\n"
                        f"🔁 Sau khi hết thời gian, đổi sẽ tốn **{PHAI_REJOIN_COST_XU:,} Xu**.",
                        ephemeral=True
                    )
                    return
                else:
                    # hết cooldown → phải trả phí
                    if user.get("xu", 0) < PHAI_REJOIN_COST_XU:
                        await interaction.response.send_message(
                            f"💰 Đổi môn phái tốn **{PHAI_REJOIN_COST_XU:,} Xu**, bạn không đủ.",
                            ephemeral=True
                        )
                        return
                    user["xu"] -= PHAI_REJOIN_COST_XU
            # nếu chưa từng chọn → miễn phí

            # gán phái
            user["class"] = self.phai_key
            user["phai_last_change_ts"] = now.timestamp()
            save_data(data)

            desc = PHAI_INFO.get(self.phai_key, "Môn phái.")
            await interaction.response.send_message(
                f"🎉 **Gia nhập môn phái thành công!**\n"
                f"Bạn hiện là đệ tử **{self.label}**.\n"
                f"» {desc}\n"
                f"⏳ Bạn có thể đổi lại sau **{PHAI_COOLDOWN_HOURS}h**, lần đổi sau tốn **{PHAI_REJOIN_COST_XU:,} Xu**.",
                ephemeral=True
            )

            # cập nhật lại view: nút phái đang chọn xám lại
            for child in self.view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = (child.label == self.label)
                    child.style = discord.ButtonStyle.secondary if child.disabled else discord.ButtonStyle.primary
            try:
                await interaction.message.edit(view=self.view)
            except Exception:
                pass


@bot.command(name="monphai", aliases=["omonphai"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_omonphai(ctx):
    uid = str(ctx.author.id)
    data = ensure_user(uid)
    user = data["users"][uid]
    _ensure_economy_fields(user)

    cur = user.get("class")
    last_ts = user.get("phai_last_change_ts")
    note = ""
    if last_ts:
        now = datetime.now(TZ_GMT7)
        last_dt = datetime.fromtimestamp(last_ts, TZ_GMT7)
        if now - last_dt < timedelta(hours=PHAI_COOLDOWN_HOURS):
            remain = (last_dt + timedelta(hours=PHAI_COOLDOWN_HOURS)) - now
            h = int(remain.total_seconds() // 3600)
            m = int((remain.total_seconds() % 3600) // 60)
            note = (
                f"⏳ Bạn đã chọn phái. Có thể đổi sau **{h}h{m}m** "
                f"(sau đó tốn **{PHAI_REJOIN_COST_XU:,} Xu**)."
            )

    phai_label = next((label for label, key in PHAI_BUTTONS if key == cur), "Chưa chọn")

    emb = make_embed(
        title="⚔️ Chọn môn phái",
        description=(
            "Chọn 1 trong 6 môn phái dưới đây. Mỗi phái sẽ dùng vũ khí riêng và ưu tiên chỉ số riêng.\n\n"
            "• **Thiết Y** — Đóng vai “tanker” – chịu đòn mạnh, bảo vệ đồng đội. Thích hợp cho người chơi thích đứng tuyến trước, thu hút sát thương.\n"
            "• **Huyết Hà** — Lối chơi đấu sĩ – có sát thương khá, khả năng chống chịu trung bình, có kỹ năng “hút máu”. Phù hợp cho train quái, solo lâu dài.\n"
            "• **Thần Tương** — Là lớp tầm xa, kiểu pháp sư/đấu sĩ từ xa – gây sát thương liên tục, có khả năng cấu rỉa, khống chế.\n"
            "• **Tố Vấn** — Hỗ trợ/Healer – hồi máu và support đồng đội, đồng thời có khả năng khống chế để bảo vệ team.\n"
            "• **Cửu Linh** — Lối chơi đặc biệt – có khả năng triệu hồi thực thể hỗ trợ chiến đấu, rất mạnh trong PvE/quần thể nhưng máu yếu khi bị tiếp cận.\n"
            "• **Toái Mộng** — Sát thủ/DPS đơn mục tiêu – dồn sát thương mạnh, tỉ lệ bạo kích cao, lối chơi yêu cầu kỹ năng cao và độ nhanh nhạy.\n\n"
            f"\nHiện tại: **{phai_label}**"
            + (f"\n{note}" if note else "")
        ),
        color=0x2ECC71,
        footer=ctx.author.display_name,
    )

    view = PhaiView(uid, cur)
    await ctx.reply(embed=emb, view=view, mention_author=False)





# 🧍 TÍNH NĂNG CŨ
# ====================================================================================================================================
# 🧍 TÍNH NĂNG CŨ
# ====================================================================================================================================


# ====================================================================================================================================
# 🧍 KHÁM PHÁ BẮT ĐẦU
# ====================================================================================================================================

COOLDOWN_OL = 10

@bot.command(name="l", aliases=["ol"])
async def cmd_ol(ctx):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    if "touch_user_activity" in globals():
        touch_user_activity(ctx, user)

    now = time.time()
    if now < user["cooldowns"]["ol"]:
        await ctx.reply(f"⏳ Hãy chờ {int(user['cooldowns']['ol'] - now)} giây nữa.", mention_author=False)
        return

    # chọn phẩm
    if "choose_rarity" in globals():
        rarity = choose_rarity()
    else:
        roll = random.random()
        if roll < 0.01:
            rarity = "S"
        elif roll < 0.05:
            rarity = "A"
        elif roll < 0.20:
            rarity = "B"
        elif roll < 0.50:
            rarity = "C"
        else:
            rarity = "D"

    if "MAP_POOL" in globals():
        map_loc = random.choice(MAP_POOL)
    else:
        map_loc = "Biện Kinh"

    user["rungs"][rarity] += 1
    user["stats"]["ol_count"] = int(user["stats"].get("ol_count", 0)) + 1
    quest_runtime_increment(user, "ol_today", 1)
    user["cooldowns"]["ol"] = now + COOLDOWN_OL
    save_data(data)

    rarity_name = {
        "D": "Phổ Thông",
        "C": "Hiếm",
        "B": "Tuyệt Phẩm",
        "A": "Sử Thi",
        "S": "Truyền Thuyết",
    }[rarity]

    chest_emo = RARITY_CHEST_EMOJI.get(rarity, "🎁")
    title = f"**[{map_loc}]** **{ctx.author.display_name}** thu được Rương {rarity_name} {chest_emo} x1"

    desc = ""
    if "get_loot_description" in globals():
        desc = get_loot_description(map_loc, rarity)

    emb = make_embed(
        title=title,
        description=desc,
        color=RARITY_COLOR.get(rarity, 0x95A5A6),
        footer=ctx.author.display_name
    )

    if "images_enabled_global" in globals() and images_enabled_global():
        try:
            img = MAP_IMAGES.get(rarity, IMG_BANDO_DEFAULT)
            emb.set_image(url=img)
        except Exception:
            pass

    msg = await ctx.send(embed=emb)

    try:
        await asyncio.sleep(3)
        if emb.image:
            emb.set_image(url=discord.Embed.Empty)
            await msg.edit(embed=emb)
    except Exception:
        pass
# ====================================================================================================================================
# 🧍 KHÁM PHÁ KẾT THÚC
# ====================================================================================================================================
# ====================================================================================================================================
# 🧍 ĐỔ THẠCH BẮT ĐẦU
# ====================================================================================================================================
# ----- Đổ thạch (odt/dt) + Jackpot (module-style) -----
ODT_MAX_BET        = 250_000
POOL_ON_LOSS_RATE  = 1.0

JACKPOT_PCT         = 0.10
JACKPOT_GATE        = 0.05
JACKPOT_BASE        = 0.02
JACKPOT_HOT_BOOST   = 0.01
JACKPOT_HOT_CAP     = 5.0
JACKPOT_WINDOW_SEC  = 5 * 60
JACKPOT_THRESH_MIN  = 10_000_000
JACKPOT_THRESH_MAX  = 12_000_000
JACKPOT_THRESH_STEP = 1_000_000

ODT_TEXTS_WIN = [
    "Viên đá nổ sáng, kim quang lấp lánh!",
    "Bụi vỡ tung, lộ bảo thạch thượng cổ!",
    "Có kẻ trả giá gấp mười muốn thu mua ngay!",
    "Một tia sáng vụt lên, linh khí cuồn cuộn!",
    "Long ngâm mơ hồ, bảo vật hiện thân!",
    "Khảm trận khởi động, linh thạch hóa kim!",
]

ODT_TEXTS_LOSE = [
    "Mở ra... bụi là bụi.",
    "Hóa tro tàn trước khi kịp vui.",
    "Viên đá vỡ vụn, lòng bạn cũng vậy.",
    "Đá bay mất. Không kịp nhìn.",
    "Bạn chưa đập, nó đã nổ!",
    "Mọi người đang chờ... rồi thất vọng.",
    "Quạ đen cắp đá, bay mất tiêu.",
    "Bạn run tay, đá rơi vỡ luôn.",
    "Có cô nương xinh đẹp xin viên đá. Bạn cho luôn.",
    "Khói trắng bốc lên... đá giả rồi.",
]

def _odt_init_state(user: dict):
    mg = user.setdefault("minigames", {})
    odt = mg.setdefault("odt", {"win_streak": 0, "loss_streak": 0})
    return odt

def _odt_pick_outcome(odt_state: dict) -> int:
    w = int(odt_state.get("win_streak", 0))
    l = int(odt_state.get("loss_streak", 0))
    base_p5, base_win = 0.005, 0.49
    delta = max(-0.04, min(0.04, (l - w) * 0.02))
    win_p = max(0.05, min(0.95, base_win + delta))
    p5 = min(base_p5, win_p)
    p2 = max(0.0, win_p - p5)
    r = random.random()
    if r < p5:
        return 5
    if r < p5 + p2:
        return 2
    return 0

def _jp(data: dict) -> dict:
    jp = data.setdefault("jackpot", {})
    jp.setdefault("pool", 0)
    jp.setdefault("hidden_threshold", 0)
    jp.setdefault("window_start", 0.0)
    jp.setdefault("hot_log", [])
    return jp

def _jp_next_threshold() -> int:
    return random.randint(JACKPOT_THRESH_MIN, JACKPOT_THRESH_MAX)

def _jp_is_window_open(jp: dict, now: float) -> bool:
    ws = float(jp.get("window_start", 0))
    return ws > 0 and (now - ws) <= JACKPOT_WINDOW_SEC

def _jp_open_window_if_needed(jp: dict, now: float):
    thr = int(jp.get("hidden_threshold", 0))
    if thr <= 0:
        thr = _jp_next_threshold()
        jp["hidden_threshold"] = thr
    if jp["pool"] >= thr and not _jp_is_window_open(jp, now):
        jp["window_start"] = now

def _jp_shift_threshold_if_expired(jp: dict, now: float):
    if jp.get("window_start", 0) and not _jp_is_window_open(jp, now):
        jp["hidden_threshold"] = int(jp.get("hidden_threshold", 0)) + JACKPOT_THRESH_STEP
        jp["window_start"] = 0

def _jp_record_hot(jp: dict, now: float):
    jp["hot_log"] = [t for t in jp.get("hot_log", []) if now - t <= 180.0]
    jp["hot_log"].append(now)

def _jp_hot_factor(jp: dict) -> float:
    recent = [t for t in jp.get("hot_log", []) if time.time() - t <= 180.0]
    return min(JACKPOT_HOT_CAP, len(recent) / 10.0)

def _try_jackpot(data: dict, member: discord.Member) -> int:
    now = time.time()
    jp = _jp(data)
    _jp_open_window_if_needed(jp, now)
    _jp_shift_threshold_if_expired(jp, now)
    _jp_record_hot(jp, now)

    pool = int(jp.get("pool", 0))
    thr  = int(jp.get("hidden_threshold", 0))

    if pool <= 0 or thr <= 0 or pool < thr or not _jp_is_window_open(jp, now):
        return 0

    if random.random() >= JACKPOT_GATE:
        return 0

    hot = _jp_hot_factor(jp)
    trigger = JACKPOT_BASE + min(JACKPOT_HOT_CAP * JACKPOT_HOT_BOOST, hot * JACKPOT_HOT_BOOST)

    if random.random() >= trigger:
        return 0

    gain = max(1, int(pool * JACKPOT_PCT))
    jp["pool"] = 0
    jp["hidden_threshold"] = _jp_next_threshold()
    jp["window_start"] = 0

    return gain



#==============ODT======================

@bot.command(name="odt", aliases=["dt"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_odt(ctx, amount: str = None):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    odt_state = _odt_init_state(user)

    # cập nhật log hoạt động
    touch_user_activity(ctx, user)

    if amount is None:
        await ctx.reply(
            "💬 Dùng: `odt <số tiền>` hoặc `odt all`. Ví dụ: `odt 1,000`.",
            mention_author=False
        )
        return

    a = str(amount).strip().lower()
    if a == "all":
        amount_val = min(int(user.get("ngan_phi", 0)), ODT_MAX_BET)
        if amount_val <= 0:
            await ctx.reply(
                "❗ Số dư bằng 0 — không thể `odt all`.",
                mention_author=False
            )
            return
    else:
        try:
            amount_val = int(a.replace(",", ""))
            if amount_val <= 0:
                raise ValueError()
        except Exception:
            await ctx.reply(
                "⚠️ Số tiền không hợp lệ. Ví dụ: `odt 500`, `odt 1,000` hoặc `odt all`.",
                mention_author=False
            )
            return
        if amount_val > ODT_MAX_BET:
            await ctx.reply(
                f"⚠️ Mỗi ván tối đa {format_num(ODT_MAX_BET)} Ngân Phiếu.",
                mention_author=False
            )
            return

    bal = int(user.get("ngan_phi", 0))
    if bal < amount_val:
        await ctx.reply(
            f"❗ Bạn không đủ Ngân Phiếu. (Hiện có: {format_num(bal)})",
            mention_author=False
        )
        return

    # log: người này vừa chơi thêm 1 lần
    user["stats"]["odt_count"] = int(user["stats"].get("odt_count", 0)) + 1
    # log: đã chi bao nhiêu NP vào odt
    user["stats"]["odt_np_spent_total"] = int(user["stats"].get("odt_np_spent_total", 0)) + amount_val

    # trừ tiền trước khi biết kết quả
    user["ngan_phi"] = bal - amount_val
    save_data(data)

    outcome = _odt_pick_outcome(odt_state)
    try:
        map_name = random.choice(MAP_POOL)
    except Exception:
        map_name = random.choice([
            "Biện Kinh","Đào Khê Thôn","Tam Thanh Sơn",
            "Hàng Châu","Từ Châu","Nhạn Môn Quan"
        ])

    title = f"Đổ Thạch — {map_name}"
    color = 0x2ECC71 if outcome else 0xE74C3C
    jackpot_announce = ""

    if outcome == 0:
        # THUA
        odt_state["loss_streak"] += 1
        odt_state["win_streak"] = 0

        jp = _jp(data)
        jp["pool"] = int(jp.get("pool", 0)) + int(amount_val * POOL_ON_LOSS_RATE)

        text = random.choice(ODT_TEXTS_LOSE)
        desc = (
            f"**{ctx.author.display_name}** bỏ ra **{format_num(amount_val)}** "
            f"**Ngân Phiếu**\n"
            f"Để mua một viên đá {EMOJI_DOTHACHT} phát sáng tại thạch phường {map_name}.\n\n"
            f"💬 {text}\n"
            f"{EMOJI_DOTHACHTHUA} Trắng tay thu về **0 Ngân Phiếu**."
        )

        gain = _try_jackpot(data, ctx.author)
        if gain > 0:
            user["ngan_phi"] += gain

            # log tiền nhận từ jackpot vào tổng earned
            user["stats"]["odt_np_earned_total"] = int(user["stats"].get("odt_np_earned_total", 0)) + gain

            jp = _jp(data)
            jp["last_win"] = {
                "user_id": ctx.author.id,
                "name": ctx.author.display_name,
                "amount": int(gain),
                "ts": time.time(),
            }
            jackpot_announce = (
                f"\n\n🎉 **Quỹ Thạch Phường NỔ HŨ!** "
                f"{ctx.author.mention} nhận **{format_num(gain)}** Ngân Phiếu."
            )
            try:
                await ctx.author.send(
                    f"{NP_EMOJI} Chúc mừng! Bạn vừa trúng "
                    f"**{format_num(gain)}** NP từ Quỹ Thạch Phường."
                )
            except Exception:
                pass

        save_data(data)

    else:
        # THẮNG
        odt_state["win_streak"] += 1
        odt_state["loss_streak"] = 0

        reward = amount_val * outcome
        user["ngan_phi"] += reward

        # log tiền kiếm được từ odt
        user["stats"]["odt_np_earned_total"] = int(user["stats"].get("odt_np_earned_total", 0)) + reward

        text = random.choice(ODT_TEXTS_WIN)
        if outcome == 5:
            desc = (
                f"**{ctx.author.display_name}** bỏ ra **{format_num(amount_val)}** "
                f"**Ngân Phiếu**\n"
                f"Để mua một viên đá {EMOJI_DOTHACHT} phát sáng tại thạch phường {map_name}.\n\n"
                f"💬 {text}\n"
                f"{EMOJI_DOTHACH} Thật bất ngờ, chủ thạch phường tổ chức đấu giá vật phẩm bạn mở!\n"
                f"— Thu về x5 giá trị nhận **{format_num(reward)} Ngân Phiếu!**"
            )
        else:
            desc = (
                f"**{ctx.author.display_name}** bỏ ra **{format_num(amount_val)}** "
                f"**Ngân Phiếu**\n"
                f"Để mua một viên đá {EMOJI_DOTHACHT} phát sáng tại thạch phường {map_name}.\n\n"
                f"💬 {text}\n"
                f"{EMOJI_DOTHACH} Bất ngờ lãi lớn — thu về **{format_num(reward)} Ngân Phiếu**!"
            )

        _jp_open_window_if_needed(_jp(data), time.time())
        save_data(data)

    # footer hiển thị quỹ jackpot + người trúng gần nhất
    jp_now = _jp(data)
    pool_now = int(jp_now.get("pool", 0))
    footer_lines = [
        f"Số dư hiện tại: {format_num(user['ngan_phi'])} Ngân Phiếu",
        f"Quỹ Thạch Phường: {format_num(pool_now)} Ngân Phiếu",
    ]
    last_win = jp_now.get("last_win")
    if isinstance(last_win, dict) and last_win.get("name") and last_win.get("amount"):
        footer_lines.append(
            f"Gần nhất {last_win['name']} đã nhận {format_num(int(last_win['amount']))} Ngân Phiếu"
        )

    emb = make_embed(
        title=title,
        description=desc + jackpot_announce,
        color=color,
        footer="\n".join(footer_lines)
    )
    await ctx.send(
        content=(ctx.author.mention if jackpot_announce else None),
        embed=emb
    )

# ====================================================================================================================================
# 🧍 ĐỔ THẠCH KẾT THÚC
# ====================================================================================================================================

# ====================================================================================================================================
# 🧍 TẶNG TIỀN BẮT ĐẦU
# ====================================================================================================================================
@bot.command(name="otang", aliases=["tang"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_otang(ctx, member: discord.Member = None, so: str = None):

    """
    Chuyển Ngân Phiếu cho người chơi khác.
    Cú pháp:
        otang @nguoi_nhan <số_ngan_phiếu>
    Ví dụ:
        otang @Nam 1,000
        otang @Linh 50000
    """
    # 1. Kiểm tra target và số tiền
    if member is None or so is None:
        await ctx.reply(
            f"📝 Cách dùng: `otang @nguoichoi <số>`\n"
            f"Ví dụ: `otang {ctx.author.mention} 1,000`",
            mention_author=False
        )
        return

    if member.id == ctx.author.id:
        await ctx.reply(
            "❗ Bạn không thể tự chuyển tiền cho chính mình.",
            mention_author=False
        )
        return

    # 2. Parse số tiền
    try:
        raw = so.replace(",", "")
        amount = int(raw)
    except Exception:
        await ctx.reply(
            "⚠️ Số tiền không hợp lệ. Ví dụ: `otang @user 1,000`.",
            mention_author=False
        )
        return
    if amount <= 0:
        await ctx.reply(
            "⚠️ Số tiền phải lớn hơn 0.",
            mention_author=False
        )
        return

    # 3. Lấy data 2 thằng (người gửi + người nhận)
    sender_id = str(ctx.author.id)
    recv_id   = str(member.id)

    data = ensure_user(sender_id)
    # ensure_user chỉ đảm bảo sender tồn tại
    # ta vẫn phải đảm bảo nhận cũng tồn tại nếu chưa từng chơi
    ensure_user(recv_id)

    sender = data["users"][sender_id]
    receiver_data = data["users"][recv_id]

    # 4. Check đủ tiền
    bal = int(sender.get("ngan_phi", 0))
    if bal < amount:
        await ctx.reply(
            f"❗ Bạn không đủ tiền. Bạn hiện có {format_num(bal)} Ngân Phiếu.",
            mention_author=False
        )
        return

    # 5. Thực hiện chuyển
    sender["ngan_phi"]   = bal - amount
    receiver_data["ngan_phi"] = int(receiver_data.get("ngan_phi", 0)) + amount

    # 6. Ghi log thống kê người gửi
    st_s = sender.setdefault("stats", {})
    st_s["np_given_total"] = int(st_s.get("np_given_total", 0)) + amount
    st_s["np_given_count"] = int(st_s.get("np_given_count", 0)) + 1

    # 7. Ghi log thống kê người nhận
    st_r = receiver_data.setdefault("stats", {})
    st_r["np_received_total"] = int(st_r.get("np_received_total", 0)) + amount
    st_r["np_received_count"] = int(st_r.get("np_received_count", 0)) + 1

    # 8. Ghi nhận nhiệm vụ ngày "tặng tiền cho người khác"
    quest_runtime_increment(sender, "give_today", 1)

    # Lưu lại sau khi cập nhật hết
    save_data(data)


    # ==================================================================
    # 📊 Ghi log nhiệm vụ ngày: "Tặng tiền cho người chơi khác"
    # Người được tính là NGƯỜI GỬI (ctx.author)
    # ==================================================================
    sender_id = str(ctx.author.id)
    data = ensure_user(sender_id)
    sender_user = data["users"][sender_id]

    # tăng biến đếm nhiệm vụ "tang_today"
    quest_runtime_increment(sender_user, "tang_today", 1)
    save_data(data)
    # ==================================================================


    # 9. Thông báo cho người gửi (public reply)
    emb_sender = make_embed(
        title=f"{NP_EMOJI} CHUYỂN NGÂN PHIẾU",
        description=(
            f"Bạn đã chuyển {NP_EMOJI} **{format_num(amount)}** cho **{member.display_name}** thành công!\n"
            f"Số dư còn lại: **{format_num(sender['ngan_phi'])}** NP."
        ),
        color=0x2ECC71,
        footer=ctx.author.display_name
    )
    await ctx.reply(embed=emb_sender, mention_author=False)

    # 🔔 Gửi DM riêng cho người nhận
    try:
        emb_recv = make_embed(
            title=f"{NP_EMOJI} NHẬN THƯỞNG THÀNH CÔNG",
            description=(
                f"Bạn vừa nhận {NP_EMOJI} **{format_num(amount)}** từ **{ctx.author.display_name}**.\n"
                f"Số dư hiện tại: **{format_num(receiver_data['ngan_phi'])}** NP."
            ),
            color=0x3498DB,
            footer="Chuyển khoản giữa người chơi"
        )
        await member.send(embed=emb_recv)
    except Exception:
        # Người nhận khóa DM, bỏ qua
        pass

# ====================================================================================================================================
# 🧍 TẶNG TIỀN KẾT THÚC
# ====================================================================================================================================
# ====================================================================================================================================
# 🧍 PHÓ BẢN BẮT ĐẦU
# ====================================================================================================================================




# =========================================================
# OPB – PHÓ BẢN ĐÁNH QUÁI CÓ ẢNH + DIỄN BIẾN
# =========================================================
# =========================================================
# OPB – ĐÁNH PHÓ BẢN (vẽ ảnh, diễn biến từng lượt, có emoji ở diễn biến)
# =========================================================
import io
import os
import random
import asyncio
from PIL import Image, ImageDraw, ImageFont
import discord
from discord.ext import commands

# nếu bạn muốn chậm hơn thì tăng lên 3 → 4 → 5
OPB_TURN_DELAY = 3.0  # giây giữa các lượt


# ---------------------------------------------------------
# 1) LOAD FONT AN TOÀN CHO RAILWAY
# ---------------------------------------------------------
# Railway thường có sẵn DejaVuSans trong /usr/share/..., còn nếu bạn
# upload file .ttf cạnh file .py thì nó sẽ bắt được ở BASE_DIR.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
    "arial.ttf",              # nếu host có arial
]

def load_font_safe(size=20):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    # fallback chắc chắn không lỗi
    return ImageFont.load_default()


# ---------------------------------------------------------
# 2) BẢNG TÊN PHÁI CÓ DẤU
# ---------------------------------------------------------
PHAI_DISPLAY = {
    "thiet_y": "Thiết Y",
    "huyet_ha": "Huyết Hà",
    "than_tuong": "Thần Tương",
    "to_van": "Tố Vấn",
    "cuu_linh": "Cửu Linh",
    "toai_mong": "Toái Mộng",
}

# quái có emoji (dùng ở DIỄN BIẾN)
MONSTER_WITH_EMOJI = {
    "D": ["🐭 Chuột Rừng", "🐰 Thỏ Xám", "🐸 Ếch Con", "🐝 Ong Độc", "🐤 Chim Non"],
    "C": ["🐺 Sói Rừng", "🐗 Lợn Rừng", "🦎 Thằn Lằn Cát", "🐢 Rùa Rừng", "🦆 Vịt Hoang"],
    "B": ["🐯 Hổ Núi", "🦊 Cáo Lửa", "🦉 Cú Đêm", "🐊 Cá Sấu Nham", "🦝 Gấu Trộm"],
    "A": ["🦁 Sư Tử Linh", "🐻 Gấu Núi", "🐼 Gấu Trúc", "🦧 Vượn Thần", "🦛 Hà Mã Linh"],
    "S": ["🦄 Kỳ Lân", "🐉 Long Thú", "🦬 Thú Thần", "🦣 Tượng Cổ", "🦙 Linh Thú"],
}

# màu thanh máu quái theo phẩm
RARITY_BAR_COLOR = {
    "D": (120, 120, 120),
    "C": (60, 135, 245),
    "B": (170, 90, 245),
    "A": (245, 155, 60),
    "S": (235, 65, 65),
}


# ---------------------------------------------------------
# 3) EXP CẦN CHO MỖI LEVEL
# ---------------------------------------------------------
def get_exp_required_for_level(level: int) -> int:
    if level <= 5:
        return 100 + level * 50
    if level <= 10:
        return 350 + (level - 5) * 200
    if level <= 20:
        return 1350 + (level - 10) * 350
    if level <= 30:
        return 4850 + (level - 20) * 700
    if level <= 40:
        return 11850 + (level - 30) * 1000
    if level <= 50:
        return 21850 + (level - 40) * 1300
    return 34850 + (level - 50) * 1800


# ---------------------------------------------------------
# 4) CÁC HÀM VẼ
# ---------------------------------------------------------
def _strip_emoji(name: str) -> str:
    parts = name.split(" ", 1)
    if len(parts) == 2 and len(parts[0]) <= 3:  # "🐭 bla bla"
        return parts[1]
    return name

def _draw_bar(draw: ImageDraw.ImageDraw, x, y, w, h, ratio, bg, fg):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=int(h / 2), fill=bg)
    ratio = max(0.0, min(1.0, ratio))
    fill_w = int(w * ratio)
    if fill_w > 0:
        draw.rounded_rectangle((x, y, x + fill_w, y + h), radius=int(h / 2), fill=fg)

def render_battle_image(
    user_name: str,
    phai_key: str,
    user_hp: int,
    user_hp_max: int,
    user_def: int,
    user_energy: int,
    user_atk: int,
    monsters: list,   # [{name_plain, rarity, hp, hp_max, atk, ko}, ...]
    turn_idx: int,
    total_turns: int,
) -> bytes:
    # kích thước khung
    W, H = 900, 240

    # nền trắng trong suốt để còn bo góc + viền
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # nền tối bo góc bên trong
    bg_radius = 26
    inner_rect = (4, 4, W - 4, H - 4)
    draw.rounded_rectangle(inner_rect, radius=bg_radius, fill=(46, 48, 52, 255))

    # viền mỏng
    draw.rounded_rectangle(inner_rect, radius=bg_radius, outline=(225, 225, 225, 90), width=2)

    # font
    ft_title = load_font_safe(22)
    ft = load_font_safe(16)
    ft_small = load_font_safe(13)

    # tên phái có dấu
    phai_name = PHAI_DISPLAY.get(phai_key, phai_key or "Chưa chọn")

    # ---------------- HEADER ----------------
    # tiêu đề
    draw.text((37, 14), f"{user_name} — Phó bản sơ cấp", font=ft_title, fill=(280, 280, 280))
    # lượt ở góc phải
    draw.text((W - 130, 16), f"Lượt: {turn_idx}/{total_turns}", font=ft_small, fill=(225, 225, 225))

    # ---------------- KHỐI PLAYER (TRÁI) ----------------
    left_x = 37
    top_y = 54

    # dòng phái + tấn công
    draw.text(
        (left_x, top_y),
        f"Phái: {phai_name}   |   Tấn công: {user_atk}",
        font=ft_small,
        fill=(230, 230, 230),
    )

    # máu
    draw.text(
        (left_x, top_y + 24),
        f"Máu: {user_hp}/{user_hp_max}",
        font=ft_small,
        fill=(255, 255, 255),
    )
    _draw_bar(
        draw,
        left_x,
        top_y + 42,
        270,
        14,
        user_hp / user_hp_max if user_hp_max else 0,
        (90, 35, 35),
        (230, 70, 70),
    )

    # thủ
    draw.text(
        (left_x, top_y + 66),
        f"Thủ: {user_def}",
        font=ft_small,
        fill=(255, 255, 255),
    )
    _draw_bar(
        draw,
        left_x,
        top_y + 84,
        270,
        12,
        1,
        (70, 70, 70),
        (150, 150, 150),
    )

    # năng lượng
    draw.text(
        (left_x, top_y + 106),
        f"Năng lượng: {user_energy}",
        font=ft_small,
        fill=(255, 255, 255),
    )
    _draw_bar(
        draw,
        left_x,
        top_y + 124,
        270,
        12,
        1,
        (40, 65, 105),
        (95, 165, 230),
    )

    # ---------------- KHỐI QUÁI (PHẢI) ----------------
    # đẩy sát phải hơn chút
    right_x = 590  # 540 + 270 = 810, vẫn còn 90px mép phải
    slot_y = 37

    for m in monsters:
        name_no_emo = m["name_plain"]
        rar = m["rarity"]
        hp = m["hp"]
        hpmax = m["hp_max"]
        atk = m["atk"]
        ko = m["ko"]

        bar_color = RARITY_BAR_COLOR.get(rar, (200, 200, 200))

        # tên quái
        draw.text((right_x, slot_y), f"{name_no_emo} [{rar}]", font=ft, fill=(255, 255, 255))
        # dòng nhỏ: công + hp
        draw.text((right_x, slot_y + 18), f"Công: {atk}", font=ft_small, fill=(220, 220, 220))
        draw.text((right_x + 180, slot_y + 18), f"{hp}/{hpmax}", font=ft_small, fill=(220, 220, 220))

        # thanh máu quái
        _draw_bar(
            draw,
            right_x,
            slot_y + 38,
            270,
            13,
            hp / hpmax if hpmax else 0.0,
            (70, 70, 70),
            (95, 95, 95) if ko else bar_color,
        )

        # chữ THUA
        if ko:
            draw.text(
                (right_x + 200, slot_y + 38),
                "THUA",
                font=ft_small,
                fill=(255, 90, 90),
            )

        slot_y += 64  # khoảng cách giữa các quái

    # xuất bytes
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------
# 5) LỆNH opb / pb
# ---------------------------------------------------------
@bot.command(name="opb", aliases=["pb"])
@commands.cooldown(1, 8, commands.BucketType.user)
async def cmd_opb(ctx: commands.Context):
    uid = str(ctx.author.id)
    data = ensure_user(uid)
    user = data["users"][uid]

    # bảo đảm field
    user.setdefault("level", 1)
    user.setdefault("exp", 0)
    user.setdefault("xu", 0)
    user.setdefault("ngan_phi", 0)
    user.setdefault("tap_vat", {"D": 0, "C": 0, "B": 0, "A": 0, "S": 0})

    # lấy chỉ số tổng (bạn đã có hàm này)
    stats = calc_character_stats(user)
    user_atk = stats["offense"]["total"]
    user_def = stats["defense"]["total"]
    user_energy = stats["energy"]["total"]
    user_hp_max = 3000 + user_def
    user_hp = user_hp_max

    # tạo 3 quái
    monsters = []
    for _ in range(3):
        roll = random.random()
        if roll < 0.02:
            rar = "S"
        elif roll < 0.10:
            rar = "A"
        elif roll < 0.25:
            rar = "B"
        elif roll < 0.55:
            rar = "C"
        else:
            rar = "D"
        display_name = random.choice(MONSTER_WITH_EMOJI[rar])   # có emoji để ghi diễn biến
        plain_name = _strip_emoji(display_name)                  # bỏ emoji để vẽ
        base_hp = {"D": 180, "C": 240, "B": 420, "A": 650, "S": 1000}[rar]
        atk = {"D": 18, "C": 36, "B": 80, "A": 140, "S": 200}[rar]
        monsters.append({
            "name": display_name,
            "name_plain": plain_name,
            "rarity": rar,
            "hp": base_hp,
            "hp_max": base_hp,
            "atk": atk,
            "ko": False,
        })

    # render lượt đầu
    img_bytes = render_battle_image(
        ctx.author.display_name,
        user.get("class", ""),
        user_hp, user_hp_max,
        user_def, user_energy,
        user_atk,
        monsters,
        1, 1
    )
    file = discord.File(io.BytesIO(img_bytes), filename="battle.png")

    emb = discord.Embed(
        title=f"**{ctx.author.display_name}** — **Bầy quái nhỏ**",
        description="**Diễn biến phó bản**:\n**Lượt 1**",
        color=0xE67E22,
    )
    msg = await ctx.send(embed=emb, file=file)

    turn = 1
    max_turns = 12
    battle_over = False

    while turn <= max_turns and not battle_over:
        turn_logs = []

        # quái đánh trước
        for m in monsters:
            if m["ko"]:
                continue
            dmg = max(1, m["atk"] - int(user_def * 0.12))
            user_hp = max(0, user_hp - dmg)
            turn_logs.append(f"{m['name']} tấn công bạn: **-{dmg} HP**")
            if user_hp <= 0:
                turn_logs.append("💥 Bạn đã gục!")
                battle_over = True
                break

        # bạn đánh lại
        if not battle_over:
            target = next((mm for mm in monsters if not mm["ko"]), None)
            if target:
                dmg = max(15, int(user_atk * 0.6))
                target["hp"] = max(0, target["hp"] - dmg)
                turn_logs.append(f"🤜 Bạn đánh {target['name']}: **-{dmg} HP**")
                if target["hp"] <= 0:
                    target["ko"] = True
                    turn_logs.append(f"💥 {target['name']} bị hạ gục!")
            if all(m["ko"] for m in monsters):
                battle_over = True

        # vẽ lại ảnh
        img_bytes = render_battle_image(
            ctx.author.display_name,
            user.get("class", ""),
            user_hp, user_hp_max,
            user_def, user_energy,
            user_atk,
            monsters,
            turn,
            max_turns,
        )
        file = discord.File(io.BytesIO(img_bytes), filename="battle.png")

        # mô tả lượt
        desc = "**Diễn biến phó bản**:\n"
        desc += f"**Lượt** {turn}\n"
        desc += "\n".join(turn_logs) if turn_logs else "(không có hành động)"

        emb = discord.Embed(
            title=f"**{ctx.author.display_name}** — **Bầy quái nhỏ**",
            description=desc,
            color=0xE67E22,
        )
        await msg.edit(embed=emb, attachments=[file])

        if battle_over:
            break

        turn += 1
        await asyncio.sleep(OPB_TURN_DELAY)

     # ===== tổng kết =====
    killed = sum(1 for m in monsters if m["ko"])
    exp_gain = 18 * max(1, killed)
    user["exp"] += exp_gain

    # lên cấp nếu đủ exp
    leveled = False
    while user["exp"] >= get_exp_required_for_level(user["level"]):
        user["exp"] -= get_exp_required_for_level(user["level"])
        user["level"] += 1
        leveled = True

    # kinh tế
    np_gain = 40 * killed
    xu_gain = 8 * killed
    user["ngan_phi"] += np_gain
    user["xu"] += xu_gain

    # tạp vật theo phẩm quái
    tv = user.setdefault("tap_vat", {})
    for r in ["S", "A", "B", "C", "D"]:
        tv.setdefault(r, 0)

    drop_counter = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    for m in monsters:
        if m["ko"]:
            rr = m["rarity"]
            drop_counter[rr] += 1
            tv[rr] = int(tv.get(rr, 0)) + 1

    save_data(data)

    # emoji
    np_emo = globals().get("NP_EMOJI", "📦")
    xu_emo = globals().get("XU_EMOJI", "🪙")
    tap_emo = globals().get("TAP_VAT_EMOJI", {
        "S": "💎", "A": "💍", "B": "🐚", "C": "🪨", "D": "🪵"
    })

    # ghép dòng tổng kết
    summary = (
        f"⚔️ Đánh {killed}/3 quái → nhận **{exp_gain} EXP**.\n"
        f"📈 EXP: {user['exp']}/{get_exp_required_for_level(user['level'])} • Cấp: **{user['level']}**"
    )
    if leveled:
        summary += " 🎉 Lên cấp!"

    reward_parts = [f"{np_emo} +{np_gain}", f"{xu_emo} +{xu_gain}"]
    for r in ["S", "A", "B", "C", "D"]:
        if drop_counter[r] > 0:
            reward_parts.append(f"{tap_emo[r]} +{drop_counter[r]}")
    summary += "\n" + "  |  ".join(reward_parts)

    # lấy lại diễn biến lượt cuối để vẫn hiển thị
    # (emb hiện giờ bạn đang tạo trong vòng lặp, ở đây tạo cái mới)
    final_desc = emb.description  # emb của lượt cuối trong code cũ

    # gắn tổng kết vào embed hiện tại
    final_emb = discord.Embed(
        title=emb.title,
        description=f"{final_desc}\n\n**Hoàn thành**:\n{summary}",
        color=emb.color,
    )

    # giữ ảnh battle cuối
    final_file = discord.File(io.BytesIO(img_bytes), filename="battle.png")
    await msg.edit(embed=final_emb, attachments=[final_file])





# ====================================================================================================================================
# 🧍 PHÓ BẢN PHÓ BẢN
# ====================================================================================================================================
# ====================================================================================================================================
# 🧍 KẾT THÚC GAME PLAY      KẾT THÚC GAME PLAY      KẾT THÚC GAME PLAY     KẾT THÚC GAME PLAY        KẾT THÚC GAME PLAY
# ====================================================================================================================================
# 🧍 KẾT THÚC GAME PLAY      KẾT THÚC GAME PLAY      KẾT THÚC GAME PLAY     KẾT THÚC GAME PLAY        KẾT THÚC GAME PLAY
# ====================================================================================================================================


# =========================================================
# 0. THÔNG BÁO TOÀN BOT
# =========================================================
import json
import os

GLOBAL_NOTICE_FILE = "data/global_notice.json"

# load thông báo nếu đã từng lưu
if os.path.exists(GLOBAL_NOTICE_FILE):
    try:
        with open(GLOBAL_NOTICE_FILE, "r", encoding="utf-8") as f:
            _tmp = json.load(f)
            GLOBAL_FOOTER_TEXT = _tmp.get("footer", " ")
    except Exception:
        GLOBAL_FOOTER_TEXT = " "
else:
    # mặc định nếu chưa có
    GLOBAL_FOOTER_TEXT = "Đã có thêm tính năng đi Phó Bản — dùng lệnh opb"


def set_global_footer(text: str):
    """lưu xuống file để restart bot vẫn còn"""
    global GLOBAL_FOOTER_TEXT
    GLOBAL_FOOTER_TEXT = text
    os.makedirs("data", exist_ok=True)
    with open(GLOBAL_NOTICE_FILE, "w", encoding="utf-8") as f:
        json.dump({"footer": text}, f, ensure_ascii=False, indent=2)


# =========================================================
# 1. HÀM make_embed BỌC LẠI
# =========================================================
# nếu bạn đã có make_embed rồi thì sửa lại như vầy
def make_embed(title, description=None, color=0x2ECC71, footer=None, fields=None):
    import discord
    emb = discord.Embed(title=title, description=description or "", color=color)

    if fields:
        for name, value, inline in fields:
            emb.add_field(name=name, value=value, inline=inline)

    # GLOBAL_FOOTER_TEXT phải được khai báo ở ngoài trước
    if footer and GLOBAL_FOOTER_TEXT.strip():
        emb.set_footer(text=f"{footer}\n{GLOBAL_FOOTER_TEXT}")
    elif footer:
        emb.set_footer(text=footer)
    elif GLOBAL_FOOTER_TEXT.strip():
        emb.set_footer(text=GLOBAL_FOOTER_TEXT)

    return emb


# =========================================================
# LỆNH: othongbao <nội dung> — chỉ chủ bot được phép dùng
# =========================================================
BOT_OWNER_ID = 821066331826421840  # 👈 thay bằng ID thật của bạn

@bot.command(name="thongbao")
async def cmd_thongbao(ctx, *, text: str):
    """Chỉ chủ bot mới có thể thay đổi thông báo footer toàn hệ thống"""
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.reply("❌ Bạn đang cố thực hiện lệnh không có", mention_author=False)
        return

    set_global_footer(text)
    await ctx.reply(f"✅ Đã cập nhật thông báo chung:\n> {text}", mention_author=False)








# ====================================================================================================================================
# 💬 GHI NHẬT KÝ TIN NHẮN TRONG SERVER (NHIỆM VỤ CHAT)
# ====================================================================================================================================
@bot.event
async def on_message(message):
    # Bỏ qua tin nhắn của bot
    if message.author.bot:
        return

    # Chỉ tính khi chat trong server (không tính DM)
    if message.guild:
        uid = str(message.author.id)
        data = ensure_user(uid)
        user = data["users"][uid]

        # ✅ Ghi log nhiệm vụ "Gửi 50 tin nhắn trong server"
        quest_runtime_increment(user, "messages_today", 1)
        save_data(data)

    # Cho phép các lệnh bot hoạt động bình thường
    await bot.process_commands(message)
# ====================================================================================================================================
# 💬 GHI NHẬT KÝ TIN NHẮN TRONG SERVER (NHIỆM VỤ CHAT)
# ====================================================================================================================================







# ================================
# 🚀 KHỞI TẠO & CHẠY BOT
# ================================
async def _main():
    ensure_data()
    # (Module đã full command, không cần load_extension)
    await bot.start(TOKEN)

if __name__ == "__main__":
    TOKEN = os.environ.get("TU_TIEN_BOT_TOKEN", "")
    if not TOKEN:
        print("Vui lòng đặt biến môi trường TU_TIEN_BOT_TOKEN với token bot của bạn.")
    else:
        import asyncio
        asyncio.run(_main())
# ================================
# ✅ KẾT THÚC FILE
# ================================
