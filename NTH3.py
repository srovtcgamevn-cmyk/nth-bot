#  BOT TU TIÊN — NTH3.volume (Module, no-self) (BT-1727-KIM)
#  Phiên bản: v18_10_statslog (2025-10-30)
#
#  Thay đổi so với v18_9_storage:
#   - Ghi log hoạt động người chơi (name, guild_id, last_active)
#   - Thêm chỉ số stats: ol_count, odt_count, tổng NP tiêu / nhận từ odt
#   - Thêm tổng hợp thống kê toàn hệ thống cho lệnh `othongtinmc`
#   - Hiển thị Top giàu, Top ol, Top odt, tổng ol/odt toàn server


# =========================
# 🔧 HỆ THAM CHIẾU CHUNG — BẮT ĐẦU
# (Core: import, dữ liệu, backup v16, cấu hình kênh, emoji, ảnh, rarity, mô tả, helpers)
# =========================
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




# ===== SAO LƯU TỰ ĐỘNG =====
# ===== SAO LƯU TỰ ĐỘNG =====
# ===== SAO LƯU TỰ ĐỘNG =====
# ===== SAO LƯU TỰ ĐỘNG =====



# Giới hạn số lượng backup thủ công (manual) cần giữ lại
MAX_MANUAL_BACKUPS = 10

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

# ===== SAO LƯU TỰ ĐỘNG =====
# ===== SAO LƯU TỰ ĐỘNG =====
# ===== SAO LƯU TỰ ĐỘNG =====
# ===== SAO LƯU TỰ ĐỘNG =====




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


# ===== Emoji — BẮT ĐẦU =====
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
    "S": "<a:rs_m:1431717941065547866>",
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

}

@bot.command(name="lenh", aliases=["olenh"])
async def cmd_olenh(ctx: commands.Context):
    desc = (
        "**⚔️ LỆNH GAMEPLAY**\n\n"
        "**osetbot** — Kích hoạt BOT trong kênh *(Admin)*\n"
        "**ol** — Đi thám hiểm, tìm rương báu (CD 10s)\n"
        "**omo** — Mở rương (VD: omo D / omo all)\n"
        "**odt** — Đổ thạch (hỗ trợ `odt all`)\n"
        "**okho** — Xem kho đồ\n"
        "**oban all** — Bán tất cả chưa mặc\n"
        "**omac** `<ID>` / `othao <ID>` / `oxem <ID>`\n"
        "**onhanvat** — Thông tin nhân vật\n\n"
        "**⬆️ LỆNH MỚI UPDATE**\n\n"
        "**obxh** — Xem Bảng Xếp Hạng\n"
        "**otang** — `otang @nguoichoi <số>`\n"
        "**onhanthuong** — Nhận thưởng 500K NP + 1 Rương S\n\n"

        "**⚙️ THÔNG TIN NÂNG CẤP**\n\n"
        "• Lưu trữ dữ liệu vĩnh viễn\n"
        "• Sao lưu dữ liệu tự động\n"
        "• BOT hoạt động ổn định, sẽ không bị ngắt kết nối giữa chừng\n"
        "• BOT đang trong giai đoạn phát triển, mong các bạn thông cảm\n"



    )
    embed = discord.Embed(
        title="📜 DANH SÁCH LỆNH CƠ BẢN",
        description=desc,
        color=0xFFD700
    )
    embed.set_footer(text="BOT GAME NGH OFFLINE | NTH3.7")
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

#===============SETBOT=======================
#===============SETBOT=======================
#===============SETBOT=======================
#===============SETBOT=======================
#===============SETBOT=======================


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


#===============SETBOT=======================
#===============SETBOT=======================
#===============SETBOT=======================
#===============SETBOT=======================
#===============SETBOT=======================





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
# =================================================


# ==================================
# 🧑‍⚖️ QUẢN LÝ — CHỦ BOT (module-style)
# ==================================
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
    if amount > 10:
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
MAX_BACKUPS_PER_DIR = 10

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



# ================== XOÁ TOÀN BỘ BACKUP ==================

@bot.command(name="xoabackup", aliases=["oxoabackup"])
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_xoabackup(ctx):
    """
    GIẢI PHÓNG DUNG LƯỢNG.
    Xóa toàn bộ thư mục backups (startup / pre-save / manual / ...).
    KHÔNG xoá data.json chính.
    Nên chạy `osaoluuantoan` trước để chắc chắn luôn còn 1 bản backup mới nhất.
    """
    import shutil
    backup_root = os.path.join(BASE_DATA_DIR, "backups")
    try:
        if os.path.isdir(backup_root):
            shutil.rmtree(backup_root)
        os.makedirs(backup_root, exist_ok=True)
        await ctx.reply(
            "🧹 Đã xoá toàn bộ backup cũ (startup / pre-save / manual / ...).\n"
            "📦 File dữ liệu chính data.json vẫn còn nguyên.\n"
            "💡 Gợi ý: kiểm tra lại dung lượng volume trên Railway.",
            mention_author=False
        )
    except Exception as e:
        await ctx.reply(
            f"❌ Không thể xoá backup: {e}",
            mention_author=False
        )



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












# ======================
# 🧍 KHU VỰC: NHÂN VẬT (module-style)
# ======================
@bot.command(name="nhanvat", aliases=["onhanvat"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_onhanvat(ctx, member: discord.Member=None):
    target = member or ctx.author
    user_id = str(target.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    equip_lines=[]
    for slot, iid in user["equipped"].items():
        if iid:
            it = next((x for x in user["items"] if x["id"]==iid), None)
            if it:
                equip_lines.append(
                    f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} — {it['type']}"
                )

    emb = make_embed(
        f"🧭 Nhân vật — {target.display_name}",
        color=0x9B59B6,
        footer=f"Yêu cầu bởi {ctx.author.display_name}"
    )
    emb.add_field(
        name=f"{NP_EMOJI} Ngân Phiếu",
        value=format_num(user.get('ngan_phi',0)),
        inline=True
    )
    emb.add_field(
        name="Trang bị đang mặc",
        value="\n".join(equip_lines) if equip_lines else "Không có",
        inline=False
    )

    if images_enabled_global():
        try:
            file = await file_from_url_cached(IMG_NHAN_VAT, "nhanvat.png")
            emb.set_image(url="attachment://nhanvat.png")
            await ctx.send(embed=emb, file=file)
            return
        except Exception:
            pass
    await ctx.send(embed=emb)

# =======================
# 🛡️ KHU VỰC: TRANG BỊ (module-style)
# =======================
def slot_of(item_type: str):
    return "slot_aogiap" if item_type == "Áo Giáp" else "slot_vukhi"

class KhoView(discord.ui.View):
    def __init__(self, author_id:int, items:list, page:int=0, per_page:int=10, timeout:float=180.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.items = items
        self.page = page
        self.per_page = per_page
        self.max_page = max(0, (len(items)-1)//per_page)
        self.children[0].disabled = (self.page==0)
        self.children[1].disabled = (self.page==self.max_page)

    def slice(self):
        a = self.page*self.per_page
        b = a+self.per_page
        return self.items[a:b]

    async def update_msg(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❗ Chỉ chủ kho mới thao tác được.",
                ephemeral=True
            )
            return
        content = "\n".join([
            f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} — {it['type']}"
            for it in self.slice()
        ]) or "Không có vật phẩm"
        emb = interaction.message.embeds[0]
        emb.set_field_at(2, name="Trang bị", value=content, inline=False)
        emb.set_footer(text=f"Trang {self.page+1}/{self.max_page+1}")
        self.children[0].disabled = (self.page==0)
        self.children[1].disabled = (self.page==self.max_page)
        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="◀ Trước", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page>0:
            self.page -= 1
        await self.update_msg(interaction)

    @discord.ui.button(label="Tiếp ▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page<self.max_page:
            self.page += 1
        await self.update_msg(interaction)

@bot.command(name="kho", aliases=["okho"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_okho(ctx):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    items_show = [it for it in user["items"] if not it["equipped"]]
    page_items = items_show[:10]
    content = "\n".join([
        f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} — {it['type']}"
        for it in page_items
    ]) or "Không có vật phẩm"
    page_total = max(1, (len(items_show) - 1)//10 + 1)

    emb = make_embed(
        f"📦 {ctx.author.display_name} — Kho nhân vật",
        color=0x3498DB,
        footer=f"Trang 1/{page_total}"
    )
    total_r = sum(int(user["rungs"][k]) for k in ["D","C","B","A","S"])
    rtext = (
        f"{RARITY_CHEST_EMOJI['D']} {format_num(user['rungs']['D'])}   "
        f"{RARITY_CHEST_EMOJI['C']} {format_num(user['rungs']['C'])}   "
        f"{RARITY_CHEST_EMOJI['B']} {format_num(user['rungs']['B'])}   "
        f"{RARITY_CHEST_EMOJI['A']} {format_num(user['rungs']['A'])}   "
        f"{RARITY_CHEST_EMOJI['S']} {format_num(user['rungs']['S'])}"
    )
    emb.add_field(
        name=f"Rương hiện có — {format_num(total_r)}",
        value=rtext,
        inline=False
    )
    emb.add_field(
        name=f"{NP_EMOJI} Ngân phiếu hiện có: {format_num(user['ngan_phi'])}",
        value="\u200b",
        inline=True
    )
    emb.add_field(name="Trang bị", value=content, inline=False)

    stats_text = (
        f"Rương đã mở: {format_num(user['stats']['opened'])}\n"
        f"Số lần thám hiểm: {format_num(user['stats']['ol_count'])}\n"
        f"{NP_EMOJI}Tổng NP đã kiếm được: {format_num(user['stats']['ngan_phi_earned_total'])}"
    )
    emb.add_field(name="📊 Thống kê", value=stats_text, inline=False)

    if images_enabled_global():
        try:
            file = await file_from_url_cached(IMG_KHO_DO, "khodo.png")
            emb.set_image(url="attachment://khodo.png")
            view = KhoView(ctx.author.id, items_show, page=0, per_page=10)
            view.children[0].disabled = True
            view.children[1].disabled = (len(items_show) <= 10)
            msg = await ctx.send(embed=emb, file=file, view=view)
            try:
                await asyncio.sleep(3)
                emb.set_image(url=discord.Embed.Empty)
                try:
                    await msg.edit(embed=emb, attachments=[], view=view)
                except TypeError:
                    await msg.edit(embed=emb, view=view)
            except Exception:
                pass
            return
        except Exception:
            pass

    view = KhoView(ctx.author.id, items_show, page=0, per_page=10)
    view.children[0].disabled = True
    view.children[1].disabled = (len(items_show) <= 10)
    await ctx.send(embed=emb, view=view)

@bot.command(name="mac", aliases=["omac"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_omac(ctx, item_id: str = None):
    if item_id is None:
        await ctx.reply(
            "📝 Cách dùng: `mac <ID>` (Xem ID trong `okho`).",
            mention_author=False
        )
        return
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    target = next((it for it in user["items"] if it["id"] == item_id), None)
    if not target:
        await ctx.reply(
            "❗ Không tìm thấy vật phẩm với ID đó.",
            mention_author=False
        )
        return
    if target["equipped"]:
        await ctx.reply(
            "Vật phẩm đang được mặc.",
            mention_author=False
        )
        return

    slot = slot_of(target["type"])
    if user["equipped"][slot]:
        cur_id = user["equipped"][slot]
        cur_item = next((it for it in user["items"] if it["id"] == cur_id), None)
        await ctx.reply(
            f"🔧 Slot đang bận bởi **{cur_item['name']}** (ID {cur_item['id']}). "
            f"Hãy dùng `othao {cur_item['id']}` để tháo.",
            mention_author=False
        )
        return

    target["equipped"] = True
    user["equipped"][slot] = target["id"]
    save_data(data)

    emoji = RARITY_EMOJI[target["rarity"]]
    emb = make_embed(
        title="🪄 Mặc trang bị",
        description=f"Bạn mặc {emoji} **{target['name']}** (ID `{target['id']}`)",
        color=RARITY_COLOR[target["rarity"]],
        footer=f"{ctx.author.display_name}"
    )
    await ctx.send(embed=emb)

@bot.command(name="thao", aliases=["othao"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_othao(ctx, item_id: str = None):
    if item_id is None:
        await ctx.reply(
            "📝 Cách dùng: `thao <ID>` (Xem ID trong `okho`).",
            mention_author=False
        )
        return
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    target = next((it for it in user["items"] if it["id"] == item_id), None)
    if not target:
        await ctx.reply(
            "❗ Không tìm thấy vật phẩm với ID đó.",
            mention_author=False
        )
        return
    if not target["equipped"]:
        await ctx.reply(
            "Vật phẩm không đang mặc.",
            mention_author=False
        )
        return

    slot = slot_of(target["type"])
    user["equipped"][slot] = None
    target["equipped"] = False
    save_data(data)

    emoji = RARITY_EMOJI[target["rarity"]]
    emb = make_embed(
        title="🪶 Tháo trang bị",
        description=(
            f"Đã tháo {emoji} **{target['name']}** "
            f"(ID `{target['id']}`) → kiểm tra lại Kho."
        ),
        color=0x95A5A6,
        footer=f"{ctx.author.display_name}"
    )
    await ctx.send(embed=emb)

@bot.command(name="xem", aliases=["oxem"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_oxem(ctx, item_id: str = None):
    if item_id is None:
        await ctx.reply(
            "📝 Cách dùng: `xem <ID>` (Xem ID trong `okho`).",
            mention_author=False
        )
        return
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    it = next((x for x in user["items"] if x["id"] == item_id), None)
    if not it:
        await ctx.reply(
            "❗ Không tìm thấy trang bị với ID đó.",
            mention_author=False
        )
        return

    state = "Đang mặc" if it["equipped"] else "Trong kho"
    emoji = RARITY_EMOJI[it["rarity"]]
    emb = make_embed(
        title=f"{emoji} `{it['id']}` {it['name']}",
        description=(
            f"Loại: **{it['type']}** • Phẩm: {emoji} • "
            f"Trạng thái: **{state}**"
        ),
        color=RARITY_COLOR[it["rarity"]],
        footer=ctx.author.display_name
    )

    img_url = ITEM_IMAGE.get(it["type"], IMG_BANDO_DEFAULT)
    if images_enabled_global():
        try:
            file = await file_from_url_cached(img_url, "item.png")
            emb.set_image(url="attachment://item.png")
            await ctx.send(embed=emb, file=file)
            return
        except Exception:
            pass
    await ctx.send(embed=emb)

# ===================
# 💰 KHU VỰC: KINH TẾ (module-style)
# ===================
COOLDOWN_OL = 10

def _rarity_order_index(r: str) -> int:
    order = ["S","A","B","C","D"]
    try:
        return order.index(r)
    except ValueError:
        return 99

def _pick_highest_available_rarity(user) -> str | None:
    for r in ["S","A","B","C","D"]:
        if int(user["rungs"].get(r, 0)) > 0:
            return r
    return None

def _open_one_chest(user, r: str):
    user["rungs"][r] = int(user["rungs"].get(r, 0)) - 1
    gp = get_nganphieu(r)
    user["ngan_phi"] = int(user.get("ngan_phi", 0)) + gp
    user.setdefault("stats", {})
    user["stats"]["ngan_phi_earned_total"] = int(
        user["stats"].get("ngan_phi_earned_total", 0)
    ) + gp
    user["stats"]["opened"] = int(user["stats"].get("opened", 0)) + 1

    item = None
    try:
        if PROB_ITEM_IN_RUONG and (random.random() < PROB_ITEM_IN_RUONG):
            item = generate_item(r, user["items"])
            user["items"].append(item)
    except Exception:
        pass
    return gp, item

def _fmt_item_line(it) -> str:
    return (
        f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} "
        f"— Giá trị: {format_num(it['value'])}"
    )



#==========OL========================

@bot.command(name="l", aliases=["ol"])
async def cmd_ol(ctx):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    # cập nhật danh tính / hoạt động
    touch_user_activity(ctx, user)

    now = time.time()
    if now < user["cooldowns"]["ol"]:
        await ctx.reply(
            f"⏳ Hãy chờ {int(user['cooldowns']['ol'] - now)} giây nữa.",
            mention_author=False
        )
        return

    rarity = choose_rarity()
    map_loc = random.choice(MAP_POOL)

    # user loot được rương
    user["rungs"][rarity] += 1
    # đếm số lần đi thám hiểm
    user["stats"]["ol_count"] = int(user["stats"].get("ol_count", 0)) + 1

    # cooldown
    user["cooldowns"]["ol"] = now + COOLDOWN_OL

    save_data(data)

    rarity_name = {
        "D":"Phổ Thông",
        "C":"Hiếm",
        "B":"Tuyệt Phẩm",
        "A":"Sử Thi",
        "S":"Truyền Thuyết"
    }[rarity]

    title = (
        f"**[{map_loc}]** **{ctx.author.display_name}** Thu được Rương "
        f"trang bị {rarity_name} {RARITY_CHEST_EMOJI[rarity]} x1"
    )
    desc = get_loot_description(map_loc, rarity)
    emb = make_embed(
        title=title,
        description=desc,
        color=RARITY_COLOR[rarity],
        footer=ctx.author.display_name
    )

    if images_enabled_global():
        try:
            emb.set_image(url=MAP_IMAGES.get(rarity, IMG_BANDO_DEFAULT))
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
#==========OL========================


#==========OM========================


@bot.command(name="mo", aliases=["omo"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_omo(ctx, *args):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    argv = [a.strip().lower() for a in args]

    def _open_many_for_rarity(user, r: str, limit: int = 50):
        opened = 0
        total_np = 0
        items = []
        while (opened < limit) and (int(user["rungs"].get(r, 0)) > 0):
            gp, it = _open_one_chest(user, r)
            opened += 1
            total_np += gp
            if it:
                items.append(it)
        return opened, total_np, items

    # omo all
    if len(argv) == 1 and argv[0] == "all":
        LIMIT = 50
        opened = 0
        total_np = 0
        items = []
        per_rarity = {"S":0,"A":0,"B":0,"C":0,"D":0}
        highest_seen = None

        for r in ["S","A","B","C","D"]:
            while (opened < LIMIT) and (int(user["rungs"].get(r, 0)) > 0):
                gp, it = _open_one_chest(user, r)
                opened += 1
                total_np += gp
                per_rarity[r] += 1
                if it:
                    items.append(it)
                    if (
                        (highest_seen is None)
                        or (_rarity_order_index(it["rarity"]) < _rarity_order_index(highest_seen))
                    ):
                        highest_seen = it["rarity"]

        if opened == 0:
            await ctx.reply(
                "❗ Bạn không có rương để mở.",
                mention_author=False
            )
            return

        highest_for_title = highest_seen
        if not highest_for_title:
            for r in ["S","A","B","C","D"]:
                if per_rarity[r] > 0:
                    highest_for_title = r
                    break

        title_emoji = RARITY_CHEST_OPENED_EMOJI.get(highest_for_title or "D", "🎁")
        title = f"{title_emoji} **{ctx.author.display_name}** đã mở x{opened} rương"
        emb = make_embed(
            title=title,
            color=0x2ECC71,
            footer=ctx.author.display_name
        )

        rewards_block = (
            f"{NP_EMOJI}\u2003Ngân Phiếu: **{format_num(total_np)}**\n"
            f"{EMOJI_TRANG_BI_COUNT}\u2003Trang bị: **{len(items)}**"
        )
        emb.add_field(
            name="Phần thưởng nhận được",
            value=rewards_block,
            inline=False
        )

        breakdown_lines = [
            f"{RARITY_EMOJI[r]} x{per_rarity[r]}"
            for r in ["S","A","B","C","D"]
            if per_rarity[r] > 0
        ]
        if breakdown_lines:
            emb.add_field(
                name="Đã mở",
                value="  ".join(breakdown_lines),
                inline=False
            )

        if items:
            lines = [_fmt_item_line(it) for it in items]
            if len(lines) > 10:
                extra = len(lines) - 10
                lines = lines[:10] + [f"... và {extra} món khác"]
            emb.add_field(
                name="Vật phẩm nhận được",
                value="\n".join(lines),
                inline=False
            )

        remaining = sum(
            int(user["rungs"].get(r, 0))
            for r in ["S","A","B","C","D"]
        )
        if remaining > 0:
            emb.set_footer(
                text=(
                    f"Còn {remaining} rương — dùng omo all hoặc "
                    f"omo <phẩm> all để mở tiếp"
                )
            )

        save_data(data)
        await ctx.send(embed=emb)
        return

    # omo <rarity> [all / num]
    if (len(argv) >= 1) and (argv[0] in {"d","c","b","a","s"}):
        r = argv[0].upper()
        available = int(user["rungs"].get(r, 0))
        if available <= 0:
            await ctx.reply(
                f"❗ Bạn không có rương phẩm {r}.",
                mention_author=False
            )
            return

        req = 1
        if len(argv) >= 2:
            if argv[1] == "all":
                req = min(50, available)
            else:
                try:
                    req = int(argv[1].replace(",", ""))
                except Exception:
                    await ctx.reply(
                        "⚠️ Số lượng không hợp lệ. Ví dụ: `omo d 3` hoặc `omo d all`.",
                        mention_author=False
                    )
                    return
                if req <= 0:
                    await ctx.reply(
                        "⚠️ Số lượng phải > 0.",
                        mention_author=False
                    )
                    return
                if req > 50:
                    await ctx.reply(
                        "⚠️ Mỗi lần chỉ mở tối đa **50** rương.",
                        mention_author=False
                    )
                    return
                if req > available:
                    await ctx.reply(
                        f"⚠️ Bạn chỉ có **{available}** rương {r}.",
                        mention_author=False
                    )
                    return

        opened, total_np, items = _open_many_for_rarity(user, r, limit=req)
        if opened == 0:
            await ctx.reply(
                "❗ Không mở được rương nào.",
                mention_author=False
            )
            return

        title_emoji = RARITY_CHEST_OPENED_EMOJI.get(r, "🎁")
        title = f"{title_emoji} **{ctx.author.display_name}** đã mở x{opened} rương"
        emb = make_embed(
            title=title,
            color=RARITY_COLOR.get(r, 0x95A5A6),
            footer=ctx.author.display_name
        )

        rewards_block = (
            f"{NP_EMOJI}\u2003Ngân Phiếu: **{format_num(total_np)}**\n"
            f"{EMOJI_TRANG_BI_COUNT}\u2003Trang bị: **{len(items)}**"
        )
        emb.add_field(
            name="Phần thưởng nhận được",
            value=rewards_block,
            inline=False
        )

        if items:
            lines = [_fmt_item_line(it) for it in items]
            if len(lines) > 10:
                extra = len(lines) - 10
                lines = lines[:10] + [f"... và {extra} món khác"]
            emb.add_field(
                name="Vật phẩm nhận được",
                value="\n".join(lines),
                inline=False
            )

        remaining_r = int(user["rungs"].get(r, 0))
        if remaining_r > 0:
            emb.set_footer(
                text=(
                    f"Còn {remaining_r} rương {r} — dùng "
                    f"omo {r.lower()} all để mở tiếp"
                )
            )

        save_data(data)
        await ctx.send(embed=emb)
        return

    # omo (không tham số): mở 1 rương tốt nhất
    r_found = _pick_highest_available_rarity(user)
    if not r_found:
        await ctx.reply(
            "❗ Bạn không có rương để mở.",
            mention_author=False
        )
        return

    gp, item = _open_one_chest(user, r_found)
    save_data(data)

    highest_for_title = item["rarity"] if item else r_found
    title_emoji = RARITY_CHEST_OPENED_EMOJI.get(highest_for_title, "🎁")
    title = f"{title_emoji} **{ctx.author.display_name}** đã mở 1 rương"

    emb = make_embed(
        title=title,
        color=RARITY_COLOR.get(highest_for_title, 0x95A5A6),
        footer=ctx.author.display_name
    )

    rewards_block = (
        f"{NP_EMOJI}\u2003Ngân Phiếu: **{format_num(gp)}**\n"
        f"{EMOJI_TRANG_BI_COUNT}\u2003Trang bị: **{1 if item else 0}**"
    )
    emb.add_field(
        name="Phần thưởng nhận được",
        value=rewards_block,
        inline=False
    )

    if item:
        emb.add_field(
            name="Vật phẩm nhận được",
            value=_fmt_item_line(item),
            inline=False
        )

    await ctx.send(embed=emb)

@bot.command(name="ban", aliases=["oban"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_oban(ctx, *args):
    user_id=str(ctx.author.id)
    data=ensure_user(user_id)
    user=data["users"][user_id]
    args=list(args)

    def settle(lst):
        total=sum(it["value"] for it in lst)
        user["ngan_phi"]+=total
        user["stats"]["sold_count"]+=len(lst)
        user["stats"]["sold_value_total"]+=total
        return total

    if not args:
        await ctx.reply(
            "Cú pháp: `oban all` hoặc `oban <D|C|B|A|S> all`",
            mention_author=False
        )
        return

    if args[0].lower()=="all":
        sell=[it for it in user["items"] if not it["equipped"]]
        if not sell:
            await ctx.reply(
                "Không có trang bị rảnh để bán.",
                mention_author=False
            )
            return
        total=settle(sell)
        user["items"]=[it for it in user["items"] if it["equipped"]]
        save_data(data)
        await ctx.send(embed=make_embed(
            "🧾 Bán vật phẩm",
            f"Đã bán **{len(sell)}** món — Nhận **{NP_EMOJI} {format_num(total)}**",
            color=0xE67E22,
            footer=ctx.author.display_name
        ))
        return

    if len(args)>=2 and args[1].lower()=="all":
        rar=args[0].upper()
        if rar not in ["D","C","B","A","S"]:
            await ctx.reply(
                "Phẩm chất không hợp lệ (D/C/B/A/S).",
                mention_author=False
            )
            return
        sell=[it for it in user["items"] if (it["rarity"]==rar and not it["equipped"])]
        if not sell:
            await ctx.reply(
                f"Không có vật phẩm phẩm chất {rar} để bán.",
                mention_author=False
            )
            return
        total=settle(sell)
        user["items"]=[
            it for it in user["items"]
            if not (it["rarity"]==rar and not it["equipped"])
        ]
        save_data(data)
        await ctx.send(embed=make_embed(
            "🧾 Bán vật phẩm",
            f"Đã bán **{len(sell)}** món {rar} — Nhận **{NP_EMOJI} {format_num(total)}**",
            color=RARITY_COLOR.get(rar,0x95A5A6),
            footer=ctx.author.display_name
        ))
        return

    await ctx.reply(
        "Cú pháp không hợp lệ. Ví dụ: `oban all` hoặc `oban D all`.",
        mention_author=False
    )

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



# ===============ODT======================







#===========================NHAN THUONG===================
#===========================NHAN THUONG===================
#===========================NHAN THUONG===================
#===========================NHAN THUONG===================




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








#===========================NHAN THUONG===================
#===========================NHAN THUONG===================
#===========================NHAN THUONG===================
#===========================NHAN THUONG===================











@bot.command(name="pingg")
async def cmd_opingg(ctx):
    t0 = time.perf_counter()
    msg = await ctx.send("⏱️ Đang đo...")
    t1 = time.perf_counter()
    gateway_ms = int(bot.latency * 1000)
    send_ms = int((t1 - t0) * 1000)
    await msg.edit(
        content=f"🏓 Gateway: {gateway_ms} ms • Send/edit: {send_ms} ms"
    )





# ===============================================
# 🔄 TỰ ĐỘNG SAO LƯU DỮ LIỆU + THÔNG BÁO KÊNH (CÓ CẤU HÌNH)
# ===============================================
from discord.ext import tasks
import time

# 🧭 Kênh Discord để gửi thông báo
AUTO_BACKUP_CHANNEL_ID = 1433207596898193479  

# ⏱ Thời gian mặc định (có thể thay đổi lúc chạy bằng lệnh othoigiansaoluu)
AUTO_BACKUP_INTERVAL_MINUTES = 10    # sao lưu mỗi X phút
AUTO_REPORT_INTERVAL_MINUTES = 60    # báo lên kênh tối đa 1 lần mỗi Y phút

# Bộ nhớ runtime
_last_report_ts = 0  # timestamp giây lần cuối đã báo
_auto_backup_started = False  # để đảm bảo chỉ start loop 1 lần

@tasks.loop(minutes=1)
async def auto_backup_task():
    """
    Vòng lặp chạy mỗi 1 phút.
    - Tự đếm phút để biết khi nào cần backup.
    - Backup xong thì quyết định có báo vào kênh hay không.
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

    # reset đếm vì sắp backup
    auto_backup_task._minutes_since_backup = 0

    # Thực hiện backup
    try:
        data_now = load_data()
        filename = snapshot_data_v16(data_now, tag="auto", subkey="manual")

        # Dọn backup cũ (giữ lại 10 bản manual mới nhất)
        try:
            _cleanup_old_backups_limit()
        except Exception as e:
            print(f"[AUTO-BACKUP] ⚠️ Lỗi dọn backup cũ: {e}")

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"✅ **Tự động sao lưu dữ liệu thành công!**\n"
            f"📦 File: `{os.path.basename(filename)}`\n"
            f"🕐 Thời gian backup: {current_time}\n"
            f"⏱️ Chu kỳ backup hiện tại: {AUTO_BACKUP_INTERVAL_MINUTES} phút/lần\n"
            f"📣 Chu kỳ báo cáo hiện tại: {AUTO_REPORT_INTERVAL_MINUTES} phút/lần"
        )

        print(f"[AUTO-BACKUP] {msg}")

        # Có nên báo vào kênh không?
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

            _last_report_ts = now_ts  # đánh dấu lần báo gần nhất

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







# ================== /CHUYỂN TIỀN GIỮA NGƯỜI CHƠI ==================
@bot.command(name="otang")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_otang(ctx, member: discord.Member = None, so: str = None):
    """
    Chuyển Ngân Phiếu cho người chơi khác.
    Cú pháp:
        otang @nguoi_nhan <số_ngan_phieu>
    Ví dụ:
        otang @Nam 1,000
        otang @Linh 50000
    """

    # 1. Kiểm tra input
    if member is None or so is None:
        await ctx.reply(
            f"📝 Cách dùng: `otang @nguoichoi <số>`\n"
            f"Ví dụ: `otang {ctx.author.mention} 1,000`",
            mention_author=False
        )
        return

    # 2. Không cho tự chuyển cho chính mình
    if member.id == ctx.author.id:
        await ctx.reply(
            "😅 Bạn không thể tự tặng cho chính mình.",
            mention_author=False
        )
        return

    # 3. Parse số tiền
    try:
        amount = int(str(so).replace(",", "").strip())
    except Exception:
        await ctx.reply(
            "⚠️ Số không hợp lệ. Ví dụ: `otang @abc 1,000`",
            mention_author=False
        )
        return

    if amount <= 0:
        await ctx.reply(
            "⚠️ Số phải > 0.",
            mention_author=False
        )
        return

    # 4. Lấy data 2 người
    giver_id = str(ctx.author.id)
    recv_id  = str(member.id)

    data = ensure_user(giver_id)
    data = ensure_user(recv_id)  # ensure_user() load + save lại, ok

    data = load_data()  # load bản mới nhất sau ensure_user
    giver = data["users"][giver_id]
    recv  = data["users"][recv_id]

    # cập nhật hoạt động để log thống kê
    touch_user_activity(ctx, giver)
    touch_user_activity(ctx, recv)

    # 5. Check tiền người gửi
    bal = int(giver.get("ngan_phi", 0))
    if bal < amount:
        await ctx.reply(
            f"❗ Bạn không đủ Ngân Phiếu. (Hiện có: {bal:,})",
            mention_author=False
        )
        return

    # 6. Trừ người gửi
    giver["ngan_phi"] = bal - amount

    # log: người gửi đã chi NP -> coi như tiêu ra (không cộng earn)
    giver_stats = giver.setdefault("stats", {})
    giver_stats.setdefault("ngan_phi_earned_total", 0)
    giver_stats.setdefault("odt_np_spent_total", 0)
    giver_stats.setdefault("odt_np_earned_total", 0)
    giver_stats.setdefault("ol_count", 0)
    giver_stats.setdefault("odt_count", 0)
    giver_stats.setdefault("opened", 0)
    giver_stats.setdefault("sold_count", 0)
    giver_stats.setdefault("sold_value_total", 0)
    # không cộng gì thêm cho giver ở đây vì đây là tiền đi ra

    # 7. Cộng người nhận
    recv_bal = int(recv.get("ngan_phi", 0))
    recv["ngan_phi"] = recv_bal + amount

    # log: người nhận được tiền -> tính vào tổng kiếm được
    recv_stats = recv.setdefault("stats", {})
    recv_stats.setdefault("ngan_phi_earned_total", 0)
    recv_stats.setdefault("odt_np_spent_total", 0)
    recv_stats.setdefault("odt_np_earned_total", 0)
    recv_stats.setdefault("ol_count", 0)
    recv_stats.setdefault("odt_count", 0)
    recv_stats.setdefault("opened", 0)
    recv_stats.setdefault("sold_count", 0)
    recv_stats.setdefault("sold_value_total", 0)

    recv_stats["ngan_phi_earned_total"] = int(
        recv_stats.get("ngan_phi_earned_total", 0)
    ) + amount

    # 8. Lưu lại
    save_data(data)

         #5. Gửi embed thông báo
    emb = make_embed(
        title=f"{NP_EMOJI} Chuyển Ngân Phiếu thành công!",
        description=(
            f"**{ctx.author.display_name}** ➜ {member.mention}\n"
            f"Đã tặng: **{format_num(amount)}** Ngân Phiếu\n\n"
            f"Số dư còn lại của bạn: **{format_num(sender['ngan_phi'])}** NP"
        ),
        color=0x2ECC71,
        footer=f"Giao dịch bởi {ctx.author.display_name}"
    )
    await ctx.send(embed=emb)

    # 6. Thử báo riêng cho người nhận (không bắt buộc)
    try:
        await member.send(
            f"{NP_EMOJI} Bạn vừa được nhận **{format_num(amount)}** Ngân Phiếu "
            f"từ **{ctx.author.display_name}**!\n"
            f"Số dư hiện tại của bạn: {format_num(receiver['ngan_phi'])} NP"
        )
    except Exception:
        # Có thể DM khóa, ignore
        pass
# ================== /CHUYỂN TIỀN GIỮA NGƯỜI CHƠI ==================

###############################################
# 📅 NHIỆM VỤ NGÀY (onhiemvu)
# - Hiển thị tiến độ nhiệm vụ ngày
# - Cho biết phần thưởng tổng nếu hoàn thành 5/5
###############################################

import math
from datetime import datetime, timezone

# Cấu hình nhiệm vụ mặc định mỗi ngày
# Mỗi mission có:
#   key         -> định danh nội bộ
#   title       -> mô tả cho player
#   stat_field  -> đọc từ đâu để tính tiến độ
#   target      -> mốc cần đạt
#   reward_np   -> thưởng khi hoàn thành nhiệm vụ này
DAILY_MISSION_TEMPLATES = [
    {
        "key": "ol_10",
        "title": "Đi thám hiểm 10 lần (ol)",
        "stat_field": ("stats", "ol_count"),
        "target": 10,
        "reward_np": 5_000,
    },
    {
        "key": "odt_10",
        "title": "Đổ thạch 10 lần (odt)",
        "stat_field": ("stats", "odt_count"),
        "target": 10,
        "reward_np": 4_000,
    },
    {
        "key": "omo_5",
        "title": "Mở 5 rương (omo)",
        # Nhiệm vụ mở rương = tổng rương đã mở trong ngày.
        # Ta sẽ log qua stats["opened"] nhưng TÍNH THEO NGÀY RIÊNG.
        # Vì stats["opened"] là lifetime, nên ta cần counter riêng theo ngày.
        # -> ta sẽ dùng "opened_today" trong quest_state,
        "stat_field": ("quest_runtime", "opened_today"),
        "target": 5,
        "reward_np": 2_000,
    },
    {
        "key": "chat_50",
        "title": "Gửi 50 tin nhắn trong server",
        "stat_field": ("quest_runtime", "messages_today"),
        "target": 50,
        "reward_np": 2_000,
    },
    {
        "key": "cmd_30",
        "title": "Gõ 30 lệnh bot",
        "stat_field": ("quest_runtime", "commands_today"),
        "target": 30,
        "reward_np": 3_000,
    },
]

# Thưởng tổng khi full 5/5
DAILY_FULL_REWARD_NP = 100_000
DAILY_FULL_REWARD_RUONG = {
    "S": 1  # Rương S x1
}
DAILY_FULL_REWARD_EMOJI = "<a:rs_d:1432101376699269364>"  # emoji rương S của bạn


def _today_key_str():
    """Trả về chuỗi ngày dạng YYYY-MM-DD (theo giờ hệ thống)."""
    return datetime.now().strftime("%Y-%m-%d")


def _ensure_daily_quest_block(user: dict) -> dict:
    """
    Đảm bảo user có khối daily_quests.
    Cấu trúc:
    user["daily_quests"] = {
        "date": "2025-11-01",
        "missions": {
            "<key>": {
                "target": int,
                "progress_start": int,  # mốc ban đầu trong stat tại thời điểm tạo nhiệm vụ
                "reward_np": int,
                "done": False,
                "claimed": False
            },
            ...
        },
        "full_done": False,      # đã hoàn thành 5/5?
        "full_claimed": False,  # đã nhận thưởng tổng chưa?
        "quest_runtime": {      # các counter trong ngày không thể lấy từ stats lifetime
            "opened_today": 0,
            "messages_today": 0,
            "commands_today": 0,
        }
    }
    """
    today_key = _today_key_str()

    dq = user.setdefault("daily_quests", {})
    dq_date = dq.get("date")

    # Nếu chưa có nhiệm vụ ngày hôm nay -> tạo mới
    if dq_date != today_key:
        dq.clear()
        dq["date"] = today_key
        dq["missions"] = {}
        dq["full_done"] = False
        dq["full_claimed"] = False
        dq["quest_runtime"] = {
            "opened_today": 0,
            "messages_today": 0,
            "commands_today": 0,
        }

        # snapshot stat ban đầu để tính tiến độ kiểu "đi ol 10 lần trong ngày"
        # Ta lưu giá trị gốc ở thời điểm khởi tạo để biết hôm nay đã làm bao nhiêu.
        for tpl in DAILY_MISSION_TEMPLATES:
            key = tpl["key"]
            target = tpl["target"]
            reward_np = tpl["reward_np"]

            # Đọc giá trị khởi đầu từ user
            # stat_field có dạng ("stats","ol_count") nghĩa là user["stats"]["ol_count"]
            start_val = 0
            sf_root, sf_key = tpl["stat_field"]

            if sf_root == "stats":
                start_val = int(user.get("stats", {}).get(sf_key, 0))
            elif sf_root == "quest_runtime":
                # quest_runtime reset mỗi ngày, nên start_val=0
                start_val = 0
            else:
                start_val = 0

            dq["missions"][key] = {
                "target": target,
                "progress_start": start_val,
                "reward_np": reward_np,
                "done": False,
                "claimed": False,
                "title": tpl["title"],
                "sf_root": sf_root,
                "sf_key": sf_key,
            }

    else:
        # đảm bảo các field luôn tồn tại (phòng code cũ chưa có)
        dq.setdefault("missions", {})
        dq.setdefault("full_done", False)
        dq.setdefault("full_claimed", False)
        qr = dq.setdefault("quest_runtime", {})
        qr.setdefault("opened_today", 0)
        qr.setdefault("messages_today", 0)
        qr.setdefault("commands_today", 0)

        # đảm bảo tất cả mission template đều tồn tại trong ngày hiện tại
        for tpl in DAILY_MISSION_TEMPLATES:
            key = tpl["key"]
            if key not in dq["missions"]:
                # tạo mission mới giữa ngày nếu thiếu
                start_val = 0
                sf_root, sf_key = tpl["stat_field"]
                if sf_root == "stats":
                    start_val = int(user.get("stats", {}).get(sf_key, 0))
                elif sf_root == "quest_runtime":
                    start_val = 0

                dq["missions"][key] = {
                    "target": tpl["target"],
                    "progress_start": start_val,
                    "reward_np": tpl["reward_np"],
                    "done": False,
                    "claimed": False,
                    "title": tpl["title"],
                    "sf_root": sf_root,
                    "sf_key": sf_key,
                }

    return dq


def _calc_progress_for_mission(user: dict, dq: dict, mdata: dict) -> int:
    """
    Tính tiến độ hiện tại cho 1 nhiệm vụ.
    progress = (giá trị hiện tại) - progress_start    (đối với stats...)
            hoặc = quest_runtime[field]               (đối với quest_runtime...)
    """
    sf_root = mdata["sf_root"]
    sf_key  = mdata["sf_key"]
    base    = int(mdata.get("progress_start", 0))
    target  = int(mdata.get("target", 0))

    if sf_root == "stats":
        current_val = int(user.get("stats", {}).get(sf_key, 0))
        delta = current_val - base
    elif sf_root == "quest_runtime":
        current_val = int(dq.get("quest_runtime", {}).get(sf_key, 0))
        delta = current_val  # vì quest_runtime reset daily
    else:
        delta = 0

    if delta < 0:
        delta = 0
    if delta > target:
        delta = target
    return delta


def _refresh_daily_quest_completion(user: dict):
    """
    Cập nhật trạng thái hoàn thành từng nhiệm vụ + trạng thái full_done.
    Không chi trả thưởng ở đây, chỉ đánh dấu logic.
    """
    dq = _ensure_daily_quest_block(user)
    all_done = True
    for key, m in dq["missions"].items():
        prog = _calc_progress_for_mission(user, dq, m)
        if prog >= m["target"]:
            m["done"] = True
        else:
            m["done"] = False
            all_done = False
    dq["full_done"] = all_done
    return dq


def _format_daily_header_block(dq: dict) -> tuple[str, int]:
    """
    Tạo text phần đầu embed:
    - Nếu chưa full_done => hiển thị mục tiêu tổng & phần thưởng tổng
    - Nếu đã full_done => hiển thị đã hoàn thành, và nếu chưa nhận full_claimed thì nói rõ
    Trả về (header_text, done_count)
    """
    missions = dq.get("missions", {})
    done_count = sum(1 for m in missions.values() if m.get("done"))
    total = len(missions)

    date_label = dq.get("date", _today_key_str())

    if not dq.get("full_done", False):
        # chưa full
        header_lines = [
            f"📅 Nhiệm vụ ngày {date_label}",
            f"🎯 Hoàn thành tất cả {total} nhiệm vụ để nhận:",
            f"   {NP_EMOJI} {format_num(DAILY_FULL_REWARD_NP)} Ngân Phiếu + {DAILY_FULL_REWARD_EMOJI} Rương S x1",
            f"──────────────────────────────",
        ]
    else:
        # đã full
        if dq.get("full_claimed", False):
            claim_txt = "✅ Bạn đã nhận thưởng lớn hôm nay."
        else:
            claim_txt = (
                "🏆 Bạn đã hoàn thành tất cả nhiệm vụ hôm nay!\n"
                f"🎁 Sẵn sàng nhận: {NP_EMOJI} +{format_num(DAILY_FULL_REWARD_NP)} "
                f"& {DAILY_FULL_REWARD_EMOJI} +1 Rương S"
            )

        header_lines = [
            f"📅 Nhiệm vụ ngày {date_label}",
            claim_txt,
            f"──────────────────────────────",
        ]

    header_text = "\n".join(header_lines)
    return header_text, done_count


def _format_single_mission_line(idx: int, m: dict, progress_now: int) -> str:
    """
    Hiển thị 1 nhiệm vụ dạng:

    :white_check_mark: 1️⃣ Đi thám hiểm 10 lần (ol)
    • Tiến độ: 7 / 10 → Phần thưởng: 5,000 Ngân Phiếu
    """
    box = "✅" if m.get("done") else "⬛"
    title = m.get("title", f"Nhiệm vụ #{idx}")
    target = int(m.get("target", 0))
    reward_np = int(m.get("reward_np", 0))

    return (
        f"{box} {idx}️⃣ {title}\n"
        f"• Tiến độ: {progress_now} / {target} → Phần thưởng: {format_num(reward_np)} Ngân Phiếu"
    )


###############################################
# 📅 NHIỆM VỤ NGÀY (onhiemvu)
# - Hiển thị tiến độ nhiệm vụ ngày
# - Cho biết phần thưởng tổng nếu hoàn thành 5/5
###############################################

from datetime import datetime

# Danh sách 5 nhiệm vụ mỗi ngày
DAILY_MISSION_TEMPLATES = [
    {
        "key": "ol_10",
        "title": "Đi thám hiểm 10 lần (ol)",
        "stat_field": ("stats", "ol_count"),
        "target": 10,
        "reward_np": 5_000,
    },
    {
        "key": "odt_10",
        "title": "Đổ thạch 10 lần (odt)",
        "stat_field": ("stats", "odt_count"),
        "target": 10,
        "reward_np": 4_000,
    },
    {
        "key": "omo_5",
        "title": "Mở 5 rương (omo)",
        # cái này dùng bộ đếm riêng trong ngày
        "stat_field": ("quest_runtime", "opened_today"),
        "target": 5,
        "reward_np": 2_000,
    },
    {
        "key": "chat_50",
        "title": "Gửi 50 tin nhắn trong server",
        "stat_field": ("quest_runtime", "messages_today"),
        "target": 50,
        "reward_np": 2_000,
    },
    {
        "key": "cmd_30",
        "title": "Gõ 30 lệnh bot",
        "stat_field": ("quest_runtime", "commands_today"),
        "target": 30,
        "reward_np": 3_000,
    },
]

# Thưởng lớn khi hoàn thành cả 5 nhiệm vụ
DAILY_FULL_REWARD_NP = 100_000
DAILY_FULL_REWARD_RUONG = {
    "S": 1  # Rương S x1
}
DAILY_FULL_REWARD_EMOJI = "<a:rs_d:1432101376699269364>"  # emoji rương S của bạn

def _today_key_str():
    """Ví dụ '2025-11-01' (reset theo ngày)."""
    return datetime.now().strftime("%Y-%m-%d")

def _ensure_daily_quest_block(user: dict) -> dict:
    """
    Tạo / bảo đảm khối daily_quests của user có dạng:

    user["daily_quests"] = {
        "date": "2025-11-01",
        "missions": {
            "ol_10": {
                "target": 10,
                "progress_start": <snapshot stat ban đầu>,
                "reward_np": 5000,
                "done": False,
                "claimed": False,
                "title": "Đi thám hiểm 10 lần (ol)",
                "sf_root": "stats",
                "sf_key": "ol_count"
            },
            ... (5 nhiệm vụ)
        },
        "full_done": False,
        "full_claimed": False,
        "quest_runtime": {
            "opened_today": 0,
            "messages_today": 0,
            "commands_today": 0
        }
    }
    """
    today_key = _today_key_str()

    dq = user.setdefault("daily_quests", {})
    dq_date = dq.get("date")

    # Nếu qua ngày mới -> reset nhiệm vụ
    if dq_date != today_key:
        dq.clear()
        dq["date"] = today_key
        dq["missions"] = {}
        dq["full_done"] = False
        dq["full_claimed"] = False
        dq["quest_runtime"] = {
            "opened_today": 0,
            "messages_today": 0,
            "commands_today": 0,
        }

        # tạo 5 mission
        for tpl in DAILY_MISSION_TEMPLATES:
            key = tpl["key"]
            sf_root, sf_key = tpl["stat_field"]

            if sf_root == "stats":
                start_val = int(user.get("stats", {}).get(sf_key, 0))
            elif sf_root == "quest_runtime":
                start_val = 0
            else:
                start_val = 0

            dq["missions"][key] = {
                "target": tpl["target"],
                "progress_start": start_val,
                "reward_np": tpl["reward_np"],
                "done": False,
                "claimed": False,
                "title": tpl["title"],
                "sf_root": sf_root,
                "sf_key": sf_key,
            }

    else:
        # đảm bảo các field luôn tồn tại
        dq.setdefault("missions", {})
        dq.setdefault("full_done", False)
        dq.setdefault("full_claimed", False)
        qr = dq.setdefault("quest_runtime", {})
        qr.setdefault("opened_today", 0)
        qr.setdefault("messages_today", 0)
        qr.setdefault("commands_today", 0)

        # nếu giữa chừng bạn thêm mission mới, thì thêm nó vào
        for tpl in DAILY_MISSION_TEMPLATES:
            key = tpl["key"]
            if key not in dq["missions"]:
                sf_root, sf_key = tpl["stat_field"]
                if sf_root == "stats":
                    start_val = int(user.get("stats", {}).get(sf_key, 0))
                elif sf_root == "quest_runtime":
                    start_val = 0
                else:
                    start_val = 0
                dq["missions"][key] = {
                    "target": tpl["target"],
                    "progress_start": start_val,
                    "reward_np": tpl["reward_np"],
                    "done": False,
                    "claimed": False,
                    "title": tpl["title"],
                    "sf_root": sf_root,
                    "sf_key": sf_key,
                }

    return dq

def _calc_progress_for_mission(user: dict, dq: dict, mdata: dict) -> int:
    """
    Tính tiến độ hiện tại cho nhiệm vụ:
    - Nếu nhiệm vụ dựa trên stats (ví dụ ol_count), tính (stats_now - progress_start)
    - Nếu nhiệm vụ dựa trên quest_runtime (ví dụ opened_today), lấy trực tiếp counter trong ngày
    Kết quả luôn clamp trong [0, target]
    """
    sf_root = mdata["sf_root"]
    sf_key  = mdata["sf_key"]
    base    = int(mdata.get("progress_start", 0))
    target  = int(mdata.get("target", 0))

    if sf_root == "stats":
        current_val = int(user.get("stats", {}).get(sf_key, 0))
        delta = current_val - base
    elif sf_root == "quest_runtime":
        current_val = int(dq.get("quest_runtime", {}).get(sf_key, 0))
        delta = current_val
    else:
        delta = 0

    if delta < 0:
        delta = 0
    if delta > target:
        delta = target
    return delta

def _refresh_daily_quest_completion(user: dict):
    """
    - Đảm bảo daily_quests tồn tại cho hôm nay
    - Cập nhật m["done"] cho từng nhiệm vụ
    - Đánh dấu full_done = True nếu 5/5 đều done
    """
    dq = _ensure_daily_quest_block(user)
    all_done = True
    for key, m in dq["missions"].items():
        prog = _calc_progress_for_mission(user, dq, m)
        m["done"] = (prog >= m["target"])
        if not m["done"]:
            all_done = False
    dq["full_done"] = all_done
    return dq

def _format_daily_header_block(dq: dict) -> tuple[str, int]:
    """
    Phần mở đầu embed:
    - Cho biết phần thưởng tổng nếu chưa xong
    - Nếu đã xong hết 5/5 thì show thông báo khác
    Trả về (text_header, số_nhiệm_vụ_đã_hoàn_thành)
    """
    missions = dq.get("missions", {})
    done_count = sum(1 for m in missions.values() if m.get("done"))
    total = len(missions)

    date_label = dq.get("date", _today_key_str())

    if not dq.get("full_done", False):
        # chưa hoàn thành 5/5
        header_lines = [
            f"📅 Nhiệm vụ ngày {date_label}",
            f"🎯 Hoàn thành tất cả {total} nhiệm vụ để nhận:",
            f"   {NP_EMOJI} {format_num(DAILY_FULL_REWARD_NP)} Ngân Phiếu + {DAILY_FULL_REWARD_EMOJI} Rương S x1",
            f"──────────────────────────────",
        ]
    else:
        # đã xong hết 5/5
        if dq.get("full_claimed", False):
            claim_txt = "✅ Bạn đã nhận thưởng lớn hôm nay."
        else:
            claim_txt = (
                "🏆 Bạn đã hoàn thành tất cả nhiệm vụ hôm nay!\n"
                f"🎁 Sẵn sàng nhận: {NP_EMOJI} +{format_num(DAILY_FULL_REWARD_NP)} "
                f"& {DAILY_FULL_REWARD_EMOJI} +1 Rương S"
            )

        header_lines = [
            f"📅 Nhiệm vụ ngày {date_label}",
            claim_txt,
            f"──────────────────────────────",
        ]

    header_text = "\n".join(header_lines)
    return header_text, done_count

def _format_single_mission_line(idx: int, m: dict, progress_now: int) -> str:
    """
    Ví dụ output:
    ✅ 1️⃣ Đi thám hiểm 10 lần (ol)
    • Tiến độ: 7 / 10 → Phần thưởng: 5,000 Ngân Phiếu
    """
    box = "✅" if m.get("done") else "⬛"
    title = m.get("title", f"Nhiệm vụ #{idx}")
    target = int(m.get("target", 0))
    reward_np = int(m.get("reward_np", 0))

    return (
        f"{box} {idx}️⃣ {title}\n"
        f"• Tiến độ: {progress_now} / {target} → Phần thưởng: {format_num(reward_np)} Ngân Phiếu"
    )

def quest_runtime_increment(user: dict, field: str, amount: int = 1):
    """
    Gọi hàm này ở các chỗ tương ứng để tăng counter trong ngày:
        quest_runtime_increment(user, "opened_today", so_ruong_mo)
        quest_runtime_increment(user, "messages_today", 1)
        quest_runtime_increment(user, "commands_today", 1)
    Sau đó nhớ save_data(data).
    """
    dq = _ensure_daily_quest_block(user)
    qr = dq["quest_runtime"]
    qr[field] = int(qr.get(field, 0)) + amount
    return dq

@bot.command(name="onhiemvu", aliases=["nhiemvu"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_onhiemvu(ctx: commands.Context):
    """
    Hiển thị tình trạng nhiệm vụ ngày (tiến độ từng nhiệm vụ + thưởng lớn 5/5).
    Không trả thưởng ở đây, chỉ show.
    """
    user_id = str(ctx.author.id)

    # tạo user nếu chưa có
    data = ensure_user(user_id)
    user = data["users"][user_id]

    # log hoạt động gần nhất
    touch_user_activity(ctx, user)

    # cập nhật trạng thái done / full_done
    dq = _refresh_daily_quest_completion(user)

    # header (thưởng tổng, vv.)
    header_text, done_count = _format_daily_header_block(dq)

    # build list từng nhiệm vụ
    body_lines = []
    missions_sorted = list(dq["missions"].items())

    # đảm bảo thứ tự 1..5 luôn cố định theo DAILY_MISSION_TEMPLATES
    order_map = {tpl["key"]: i for i, tpl in enumerate(DAILY_MISSION_TEMPLATES, start=1)}
    missions_sorted.sort(key=lambda kv: order_map.get(kv[0], 999))

    for key, m in missions_sorted:
        prog_now = _calc_progress_for_mission(user, dq, m)
        idx_display = order_map.get(key, 0)
        body_lines.append(_format_single_mission_line(idx_display, m, prog_now))

    desc_text = (
        f"{header_text}\n" +
        "\n\n".join(body_lines) +
        f"\n\n📌 Tiến độ tổng: {done_count}/{len(dq['missions'])} nhiệm vụ đã hoàn thành hôm nay."
    )

    emb = make_embed(
        title="📜 NHIỆM VỤ HÀNG NGÀY",
        description=desc_text,
        color=0x00B894,
        footer=f"Yêu cầu bởi {ctx.author.display_name}"
    )

    await ctx.reply(embed=emb, mention_author=False)


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


# ================== /CHUYỂN TIỀN MỚI  GIỮA NGƯỜI CHƠI ==================
@bot.command(name="tang")
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

    # 1️⃣ Kiểm tra input
    if member is None or so is None:
        await ctx.reply(
            "📝 Cách dùng: `otang @nguoichoi <số>`\nVí dụ: `otang @Nam 1,000`",
            mention_author=False
        )
        return

    # 2️⃣ Không cho chuyển cho chính mình
    if member.id == ctx.author.id:
        await ctx.reply("❗ Bạn không thể tự chuyển Ngân Phiếu cho chính mình.", mention_author=False)
        return

    # 3️⃣ Xử lý số tiền
    try:
        amount = int(str(so).replace(",", "").strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await ctx.reply("⚠️ Số tiền không hợp lệ. Ví dụ: `otang @Nam 1,000`", mention_author=False)
        return

    # 4️⃣ Load data người gửi / người nhận
    sender_id = str(ctx.author.id)
    receiver_id = str(member.id)

    data = ensure_user(sender_id)
    data = ensure_user(receiver_id)
    users = data["users"]

    sender = users[sender_id]
    receiver = users[receiver_id]

    # 5️⃣ Kiểm tra số dư
    bal = int(sender.get("ngan_phi", 0))
    if bal < amount:
        await ctx.reply(
            f"💰 Bạn không đủ Ngân Phiếu. (Hiện có: {format_num(bal)})",
            mention_author=False
        )
        return

    # 6️⃣ Cập nhật số dư
    sender["ngan_phi"] -= amount
    receiver["ngan_phi"] = int(receiver.get("ngan_phi", 0)) + amount

    # 7️⃣ Ghi log stats
    s_stats = sender.setdefault("stats", {})
    s_stats["ngan_phi_sent_total"] = int(s_stats.get("ngan_phi_sent_total", 0)) + amount

    r_stats = receiver.setdefault("stats", {})
    r_stats["ngan_phi_received_total"] = int(r_stats.get("ngan_phi_received_total", 0)) + amount

    # 8️⃣ Cập nhật hoạt động
    touch_user_activity(ctx, sender)
    touch_user_activity(ctx, receiver)
    save_data(data)

    # 9️⃣ Embed gửi cho người gửi
    embed_sender = make_embed(
        title=f"{NP_EMOJI} CHUYỂN NGÂN PHIẾU",
        description=(
            f"✅ Bạn đã chuyển **{format_num(amount)}** {NP_EMOJI} cho **{member.display_name}** thành công!\n\n"
            f"Số dư còn lại: **{format_num(sender['ngan_phi'])}** {NP_EMOJI}."
        ),
        color=0x2ECC71,
        footer=f"{ctx.author.display_name}"
    )
    await ctx.reply(embed=embed_sender, mention_author=False)

    # 🔔 Embed riêng gửi cho người nhận
    try:
        embed_receiver = make_embed(
            title=f"{NP_EMOJI} NHẬN NGÂN PHIẾU",
            description=(
                f"💌 Bạn vừa nhận được **{format_num(amount)}** {NP_EMOJI} "
                f"từ **{ctx.author.display_name}**!\n\n"
                f"Số dư hiện tại: **{format_num(receiver['ngan_phi'])}** {NP_EMOJI}."
            ),
            color=0xF1C40F,
            footer="BOT TU TIÊN — Giao dịch thành công"
        )
        await member.send(embed=embed_receiver)
    except Exception:
        pass
###############################################




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
