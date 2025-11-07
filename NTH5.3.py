# ============================================================
# BUFF_MEM_AO_v1_2.py
# Phiên bản: v1_2
# Ngày cập nhật: 2025-11-02
#
# Chức năng:
# - Buff mem ảo cho server: auto đổi biệt danh thành tên kiểu Discord Việt,
#   auto gán nhiều role, log lại nguồn invite.
# - Chủ Bot có thể kiểm tra thành viên theo user / role / thời gian.
#
# Lệnh Chủ Bot:
#   /setlink <invite_url> <@role1> <@role2> ...
#   /xemlink
#   /xoalink <invite_url>
#   /batbuff
#   /tatbuff
#   /kiemtratv [@user] [role:@role] [gio:<số>] [ngay:<số>]
#   /lenhchubot
#
# Yêu cầu:
#   pip install discord.py==2.4.0
#   Intents bật: SERVER MEMBERS INTENT, MESSAGE CONTENT INTENT
#   Quyền bot: Manage Nicknames, Manage Roles, View Audit Log, Read/Send Messages
#
# Biến môi trường:
#   DISCORD_TOKEN
#   OWNER_DISCORD_ID
#
# Lưu trữ:
#   data/invite_map.json
#   data/buffmem_log.json
#   data/names_used.json
# ============================================================

import os
import json
import random
import asyncio
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands

DATA_DIR = "data"
INVITE_MAP_FILE = os.path.join(DATA_DIR, "invite_map.json")
LOG_FILE = os.path.join(DATA_DIR, "buffmem_log.json")
USED_NAMES_FILE = os.path.join(DATA_DIR, "names_used.json")

os.makedirs(DATA_DIR, exist_ok=True)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OWNER_DISCORD_ID = 821066331826421840

# Intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.invites = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    help_command=None
)

# Cache invite lúc trước join
invite_cache = {}  # {guild_id_str: {code: uses_int, ...}}

# ---------------------------
# Helpers: load / save JSON
# ---------------------------

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_invite_map():
    data = load_json(INVITE_MAP_FILE, {})
    if "guilds" not in data:
        data["guilds"] = {}
    return data

def set_invite_map(data):
    save_json(INVITE_MAP_FILE, data)

def get_log_data():
    # [
    #   {
    #     "time": "2025-11-02T18:41:10Z",
    #     "guild_id": "...",
    #     "user_id": "...",
    #     "new_name": "...",
    #     "role_ids": [...],
    #     "invite_code": "..."
    #   },
    #   ...
    # ]
    return load_json(LOG_FILE, [])

def set_log_data(data):
    save_json(LOG_FILE, data)

def get_used_names():
    # { "<guild_id>": ["name1","name2",...] }
    return load_json(USED_NAMES_FILE, {})

def set_used_names(data):
    save_json(USED_NAMES_FILE, data)

# ---------------------------
# Quyền Chủ Bot
# ---------------------------

async def is_owner_user(ctx: commands.Context):
    return ctx.author.id == OWNER_DISCORD_ID

def only_owner():
    async def predicate(ctx):
        return await is_owner_user(ctx)
    return commands.check(predicate)

# ---------------------------
# Sinh nickname kiểu Discord Việt
# ---------------------------

BASE_NAMES_WITH_ACCENT = [
    "béVy", "BôngTuyết", "BảoTrân", "HuyĐăng", "TúVy",
    "ThảoVy", "TrâmAnh", "HuyềnAnh", "BéNa", "ThúyVy",
    "MinhPhúc", "PhátBảo", "ĐăngKhang", "LongĐẹpTrai",
    "BảoAnh", "PhúcAn", "TâmAnh", "KhảiĐăng", "BăngTuyết",
    "TuấnPhong", "HạoNam", "GiaBảo", "BăngTâm", "VyAnh",
    "LanAnh", "BảoMy", "LinhMy", "HoàngLong", "AnhThư",
]

BASE_NAMES_NO_ACCENT = [
    "phong", "long", "khang", "tuananh", "huy", "anhthu",
    "trang", "my", "vy", "kiet", "bao", "linh", "tram", "phuc",
    "minhphong", "thienan", "ngocvy", "hoanglam", "dat", "tuanpro",
    "mit", "bongtuyet", "vychanh", "nganbui", "phatdz", "lamkute",
    "tramy", "khangvip", "tienanh", "phongx", "thienbao", "mycute",
    "naNa", "thanhx", "phuongx", "huyvip", "hoanglongdz"
]

SUFFIX_TOKENS = [
    "vip", "pro", "dz", "cute", "tv", "vn", "x", "z", "no1",
    "real", "off", "idol", "baby", "chanh", "love",
]

DECOR_TOKENS = [
    "彡", "ツ", "♡", "☆", "™", "☯︎", "❄", "✿", "彡☆", "♡彡", "彡ツ"
]

POPULAR_NUMBERS = [
    "69", "99", "888", "123", "2007", "2008", "2005", "2009",
    "03", "07", "09", "2003", "2004", "97", "98"
]

def pick_weighted_has_accent():
    # ~60% có dấu / một phần dấu
    return random.random() < 0.60

def build_base_name():
    if pick_weighted_has_accent() and BASE_NAMES_WITH_ACCENT:
        return random.choice(BASE_NAMES_WITH_ACCENT)
    else:
        return random.choice(BASE_NAMES_NO_ACCENT)

def maybe_mix_suffix(name: str) -> str:
    style = random.randint(0, 6)
    chosen_suffix = random.choice(SUFFIX_TOKENS)
    chosen_num = random.choice(POPULAR_NUMBERS)

    if style == 0:
        out = f"{name}{chosen_num}"
    elif style == 1:
        out = f"{name}{chosen_suffix}"
    elif style == 2:
        out = f"{name}{chosen_suffix}{chosen_num}"
    elif style == 3:
        out = f"{name}_{chosen_suffix}"
    elif style == 4:
        out = f"{chosen_suffix}{name}"
    elif style == 5:
        if not name.lower().startswith("bé"):
            out = f"bé{name}"
        else:
            out = name
    else:
        out = name
    return out

def maybe_add_decor(name: str) -> str:
    roll = random.random()
    if roll < 0.3:
        return f"{name}{random.choice(DECOR_TOKENS)}"
    elif roll < 0.4:
        return f"{random.choice(DECOR_TOKENS)}{name}"
    elif roll < 0.5:
        left = random.choice(DECOR_TOKENS)
        right = random.choice(DECOR_TOKENS)
        return f"{left}{name}{right}"
    else:
        return name

def clamp_name(nick: str) -> str:
    if len(nick) > 32:
        return nick[:32]
    return nick

def generate_nickname(guild_id: int) -> str:
    used_names = get_used_names()
    recent_list = used_names.get(str(guild_id), [])

    for _ in range(50):
        base = build_base_name()
        with_suffix = maybe_mix_suffix(base)
        decorated = maybe_add_decor(with_suffix)
        final_nick = clamp_name(decorated)

        if final_nick not in recent_list:
            recent_list.insert(0, final_nick)
            recent_list = recent_list[:200]
            used_names[str(guild_id)] = recent_list
            set_used_names(used_names)
            return final_nick

    return clamp_name(with_suffix)

# ---------------------------
# Invite tracking
# ---------------------------

async def refresh_guild_invites(guild: discord.Guild):
    gid = str(guild.id)
    try:
        invites = await guild.invites()
    except discord.Forbidden:
        invite_cache[gid] = {}
        return
    except Exception:
        invite_cache[gid] = {}
        return

    invite_cache[gid] = {}
    for inv in invites:
        invite_cache[gid][inv.code] = inv.uses or 0

def detect_used_invite_code(before_uses: dict, after_invites: list[discord.Invite]):
    after_map = {}
    for inv in after_invites:
        after_map[inv.code] = inv.uses or 0

    picked_code = None
    for code, after_val in after_map.items():
        before_val = before_uses.get(code, 0)
        if after_val > before_val:
            picked_code = code
            break

    return picked_code, after_map

# ---------------------------
# Events
# ---------------------------

@bot.event
async def on_ready():
    print(f"✅ Bot buff mem ảo v1_2 đã sẵn sàng. Logged in as {bot.user} (id: {bot.user.id})")
    for g in bot.guilds:
        await refresh_guild_invites(g)

@bot.event
async def on_guild_join(guild: discord.Guild):
    await refresh_guild_invites(guild)

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    gid = str(guild.id)

    before_uses = invite_cache.get(gid, {}).copy()

    try:
        invites_after = await guild.invites()
    except discord.Forbidden:
        invites_after = []
    except Exception:
        invites_after = []

    code_used, after_map = detect_used_invite_code(before_uses, invites_after)
    invite_cache[gid] = after_map

    if code_used is None:
        return

    data = get_invite_map()
    guild_conf = data["guilds"].get(gid)
    if not guild_conf:
        return

    if not guild_conf.get("buff_enabled", True):
        return

    link_conf = guild_conf.get("links", {}).get(code_used)
    if not link_conf or not link_conf.get("active", True):
        return

    role_ids = link_conf.get("role_ids", [])

    # 1. gán tất cả role
    for rid in role_ids:
        r = guild.get_role(rid)
        if r:
            try:
                await member.add_roles(r, reason="buff mem ảo auto-role")
            except discord.Forbidden:
                pass
            except Exception:
                pass
        await asyncio.sleep(0.05)

    # 2. đổi nickname
    new_name = generate_nickname(member.guild.id)
    try:
        await member.edit(nick=new_name, reason="buff mem ảo auto-nick")
    except discord.Forbidden:
        pass
    except Exception:
        pass

    # 3. log
    logs = get_log_data()
    log_entry = {
        "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "guild_id": gid,
        "user_id": str(member.id),
        "new_name": new_name,
        "role_ids": role_ids,
        "invite_code": code_used
    }
    logs.append(log_entry)
    logs = logs[-400:]  # giữ 400 record gần nhất
    set_log_data(logs)

    print(f"[BUFF] {member} -> '{new_name}' via {code_used} roles={role_ids}")

# ---------------------------
# Commands Chủ Bot
# ---------------------------

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


# ========== /kiemtratv ==========

@bot.command(name="kiemtratv")
@only_owner()
async def cmd_kiemtratv(ctx: commands.Context, *args):
    """
    /kiemtratv
    /kiemtratv @user
    /kiemtratv role:@role
    /kiemtratv gio:12
    /kiemtratv ngay:2
    /kiemtratv role:@MemAo ngay:1
    /kiemtratv @user ngay:7

    Lọc log buff theo:
    - user cụ thể
    - role cụ thể
    - khung thời gian giờ / ngày
    - hoặc xem danh sách gần nhất
    """

    gid = str(ctx.guild.id)
    logs = get_log_data()
    # chỉ xem log của bang hiện tại
    logs = [x for x in logs if x.get("guild_id") == gid]

    target_user_id = None
    target_role_id = None
    max_age_hours = None  # số giờ tối đa
    # parse args thô
    for a in args:
        # @user
        if isinstance(a, discord.Member):
            target_user_id = str(a.id)
            continue
        # role:@role
        if isinstance(a, discord.Role):
            target_role_id = a.id
            continue
        # gio:X
        if isinstance(a, str) and a.lower().startswith("gio:"):
            try:
                h = int(a.split(":",1)[1])
                max_age_hours = h
            except:
                pass
            continue
        # ngay:X
        if isinstance(a, str) and a.lower().startswith("ngay:"):
            try:
                d = int(a.split(":",1)[1])
                # nếu chưa có gio:, đổi sang giờ
                if (max_age_hours is None) or (d*24 < max_age_hours):
                    max_age_hours = d * 24
            except:
                pass
            continue

    # lọc theo thời gian
    if max_age_hours is not None:
        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc - timedelta(hours=max_age_hours)

        def too_old(entry):
            t = entry.get("time")
            try:
                # parse "2025-11-02T18:41:10Z"
                dt = datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")
                dt = dt.replace(tzinfo=timezone.utc)
                return dt < cutoff
            except:
                return False

        logs = [x for x in logs if not too_old(x)]

    # lọc theo user
    if target_user_id is not None:
        logs = [x for x in logs if x.get("user_id") == target_user_id]

    # lọc theo role
    if target_role_id is not None:
        logs = [x for x in logs if target_role_id in x.get("role_ids", [])]

    if not logs:
        await ctx.reply("📭 Không tìm thấy thành viên phù hợp với điều kiện.")
        return

    # Nếu user cụ thể -> show chi tiết 1 người mới nhất
    if target_user_id is not None:
        logs_user = logs[-1]  # record mới nhất
        uid = logs_user.get("user_id")
        member = ctx.guild.get_member(int(uid))
        display_mention = f"<@{uid}>" if uid else "N/A"
        new_name = logs_user.get("new_name", "N/A")
        invite_code = logs_user.get("invite_code", "N/A")
        ts_utc = logs_user.get("time", "N/A")
        role_ids = logs_user.get("role_ids", [])

        # build role list
        role_mentions = []
        for rid in role_ids:
            r = ctx.guild.get_role(rid)
            role_mentions.append(r.mention if r else str(rid))

        # tính "bao lâu trước" (ước lượng giờ)
        try:
            dt = datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            diff = now_utc - dt
            hours_ago = int(diff.total_seconds() // 3600)
            ago_txt = f"{hours_ago} giờ trước"
            # giờ VN (GMT+7)
            vn_time = (dt + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M")
        except:
            ago_txt = "N/A"
            vn_time = ts_utc

        msg = (
            "📜 KIỂM TRA THÀNH VIÊN\n"
            f"👤 Thành viên: {display_mention} (ID: {uid})\n"
            f"🏷️ Biệt danh sau buff: {new_name}\n"
            f"🎭 Role được gán: {', '.join(role_mentions) if role_mentions else '—'}\n"
            f"📨 Link mời: {invite_code}\n"
            f"🕒 Thời điểm buff: {vn_time} (giờ GMT+7)\n"
            f"⏳ Đã vào được: {ago_txt}\n"
        )
        await ctx.reply(msg)
        return

    # nếu không phải user cụ thể -> show danh sách
    # lấy tối đa 20 gần nhất
    slice_logs = logs[-20:]

    lines = ["📊 DANH SÁCH THÀNH VIÊN BUFF GẦN NHẤT:"]
    idx = 1
    for entry in slice_logs[::-1]:  # đảo ngược để record mới nhất lên đầu
        uid = entry.get("user_id")
        display_mention = f"<@{uid}>" if uid else "N/A"
        new_name = entry.get("new_name", "N/A")
        invite_code = entry.get("invite_code", "N/A")
        role_ids = entry.get("role_ids", [])
        role_mentions = []
        for rid in role_ids:
            r = ctx.guild.get_role(rid)
            role_mentions.append(r.mention if r else str(rid))

        ts_utc = entry.get("time", "N/A")
        # chuyển sang giờ VN gọn
        try:
            dt = datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            vn_time = (dt + timedelta(hours=7)).strftime("%m-%d %H:%M")
        except:
            vn_time = ts_utc

        lines.append(
            f"{idx}. {display_mention} → \"{new_name}\" "
            f"| Roles: {', '.join(role_mentions) if role_mentions else '—'} "
            f"| Link:{invite_code} "
            f"| {vn_time} GMT+7"
        )
        idx += 1

    lines.append(f"\nTổng: {len(slice_logs)} người")
    await ctx.reply("\n".join(lines))


@bot.command(name="lenhchubot")
@only_owner()
async def cmd_lenhchubot(ctx: commands.Context):
    msg = (
        "LỆNH CHỦ BOT (buff mem ảo):\n"
        "/setlink <invite_url> <@role1> <@role2> ...\n"
        "    Gán link buff + nhiều role.\n\n"
        "/xemlink\n"
        "    Xem tất cả link buff.\n\n"
        "/xoalink <invite_url>\n"
        "    Tắt 1 link buff.\n\n"
        "/batbuff\n"
        "    Bật buff mem ảo cho bang.\n\n"
        "/tatbuff\n"
        "    Tắt buff mem ảo cho bang.\n\n"
        "/kiemtratv [@user] [role:@role] [gio:X] [ngay:Y]\n"
        "    Kiểm tra thành viên đã buff:\n"
        "    - @user: chi tiết 1 người\n"
        "    - role:@role: lọc theo role đã cấp khi buff\n"
        "    - gio:X | ngay:Y: lọc theo thời gian gần nhất\n"
        "    - không tham số: top gần nhất\n"
    )
    await ctx.reply(msg)

# ---------------------------
# Run bot
# ---------------------------

def main():
    if not DISCORD_TOKEN:
        print("❌ Thiếu DISCORD_TOKEN trong biến môi trường.")
        return
    if OWNER_DISCORD_ID == 0:
        print("❌ Thiếu OWNER_DISCORD_ID trong biến môi trường.")
        return
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
