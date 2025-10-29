# -*- coding: utf-8 -*-


# ===============================================
#  BOT TU TIÊN v18.2
# ===============================================

# ====== Cấu hình & Hằng số Bắt Đầu ======
import discord
from discord.ext import commands
import random, json, os, time, aiohttp, io
import logging
from datetime import datetime
# ===== HỆ THỐNG SAO LƯU DỮ LIỆU (v16) =====
import hashlib
from glob import glob

BACKUP_DIRS = {
    "startup": "backups/startup",
    "pre_save": "backups/pre-save",
    "manual": "backups/manual",
    "before_restore": "backups/before-restore",
    "resetuser": "backups/resetuser",
    "export": "backups/export"
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
    """Tạo 1 bản sao lưu data.json vào thư mục tương ứng, có kèm checksum."""
    _ensure_backup_dirs()
    stamp = _stamp_now()
    fname = f"data.json.v16.{tag}.{stamp}.json"
    dstdir = BACKUP_DIRS.get(subkey, BACKUP_DIRS["manual"])
    out = os.path.join(dstdir, fname)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # checksum
    with open(out + ".sha256", "w", encoding="utf-8") as g:
        g.write(_sha256_file(out))
    return out

def list_recent_backups_v16(limit=10):
    """Trả về danh sách (mtime, key, path) của các file backup gần đây."""
    _ensure_backup_dirs()
    files = []
    for key, d in BACKUP_DIRS.items():
        for p in glob(os.path.join(d, "data.json.v*.json")):
            files.append((os.path.getmtime(p), key, p))
    files.sort(reverse=True)
    return files[:max(1, min(20, limit))]

def total_backup_stats_v16():
    """Thống kê tổng số file, tổng dung lượng, và file gần nhất."""
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
# ===== KẾT THÚC HỆ THỐNG SAO LƯU DỮ LIỆU =====

# ===== CẤU HÌNH KÊNH HOẠT ĐỘNG THEO SERVER (v18.2) =====
def get_guild_settings(data, guild_id: int):
    return data.setdefault("guild_settings", {}).setdefault(str(guild_id), {})

def set_guild_channel(data, guild_id: int, channel_id: int):
    rec = get_guild_settings(data, guild_id)
    rec["channel_id"] = int(channel_id)

def get_guild_channel(data, guild_id: int):
    rec = get_guild_settings(data, guild_id)
    return rec.get("channel_id")
# ===== KẾT THÚC CẤU HÌNH KÊNH HOẠT ĐỘNG THEO SERVER =====

# ===== CÀI ĐẶT EMOJI BẮT ĐẦU=====


logging.getLogger("discord").setLevel(logging.WARNING)

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

DATA_FILE = "data.json"
COOLDOWN_OL = 10  # giây
STARTING_NP = 1000


# Emoji phẩm chất
RARITY_EMOJI = {
    "A": "<:A_:1431390274369622166>",
    "B": "<:B_:1431390268304658546>",
    "C": "<:C_:1431390259945410661>",
    "D": "<:D_:1431390264336978081>",
    "S": "<:S_:1431444254411984917>",
}
RARITY_COLOR = {"D":0x8B6B46,"C":0x2F80ED,"B":0x8A2BE2,"A":0xFF6A00,"S":0xFFD700}
RARITY_THUMBNAIL = {
    "D": "https://i.ibb.co/8gQ4RV5R/D.png",
    "C": "https://i.ibb.co/Xdt92MN/C.png",
    "B": "https://i.ibb.co/6R7g9j0Z/B.png",
    "A": "https://i.ibb.co/rG3SJYj1/A.png",
    "S": "https://i.ibb.co/7d44KrqM/S.png",
}


# Emoji phẩm chất (ITEM QUALITY - animated)
RARITY_EMOJI = {
    "D": "<a:D12:1432473477616505023>",
    "C": "<a:C11:1432467636943454315>",
    "B": "<a:B11:1432467633932075139>",
    "A": "<a:A11:1432467623051919390>",
    "S": "<a:S11:1432467644761509948>",
}

# Emoji rương (UNOPENED)
RARITY_CHEST_EMOJI = {
    "D": "<a:rd_d:1431717925034918052>",
    "C": "<a:rc_d:1431713192123568328>",
    "B": "<a:rb_d:1431713180975108291>",
    "A": "<a:ra_d:1431713170384490726>",
    "S": "<a:rs_d:1432101376699269364>",
}

# Emoji rương (OPENED)
RARITY_CHEST_OPENED_EMOJI = {
    "D": "<a:rd_m:1431717929782870116>",
    "C": "<a:rc_m:1431713195860693164>",
    "B": "<a:rb_m:1431713187924934686>",
    "A": "<a:ra_m:1431713174704492604>",
    "S": "<a:rs_m:1431717941065547866>",
}

# Emoji mở rương (header omo)
EMOJI_MORUONG = "<a:rd_m:1431717929782870116>"
# Emoji đếm trang bị nhận
EMOJI_TRANG_BI_COUNT = "<:motrangbi:1431822388793704508>"
# Emoji Ngân Phiếu
NP_EMOJI = "<a:np:1431713164277448888>"
EMOJI_NOHU4 = "<a:nohu5:1432589822740004934>"
EMOJI_CANHBAO = "<:thongbao:1432852057353621586>"
EMOJI_THONGBAO = "<:canhbao:1432848238104543322>"



# Hình ảnh
IMG_BANDO_DEFAULT = "https://i.postimg.cc/15CvNdQL/bando.png"
IMG_RUONG_MO = "https://i.ibb.co/21NS0t10/ruongdamo.png"
IMG_NGAN_PHIEU = "https://i.ibb.co/DDrgRRF1/nganphieu.png"
# Bổ sung theo yêu cầu
IMG_KHO_DO = "https://i.postimg.cc/W3189R0f/thungdo-min.png"    # dùng trong okho
IMG_NHAN_VAT = "https://i.postimg.cc/Z0trzXyz/nhanvat-min.png"  # dùng trong onhanvat

# Ảnh riêng cho từng loại trang bị (dùng trong oxem)
ITEM_IMAGE = {
    "Kiếm": "https://i.ibb.co/6pDBWyR/kiem.png",
    "Thương": "https://i.ibb.co/S2C7fwJ/thuong.png",
    "Đàn": "https://i.ibb.co/Fk0rSpQg/dan.png",
    "Trượng": "https://i.ibb.co/ymbxhtg5/truong.png",
    "Dải Lụa": "https://i.ibb.co/Myx1fD34/dailua.png",
    "Găng Tay": "https://i.ibb.co/gbn2Q6Gx/gangtay.png",
    "Áo Giáp": "https://i.ibb.co/jkWkT5hj/giap.png"
}

# Rarity logic
RARITY_PROBS = [("D",0.50),("C",0.30),("B",0.15),("A",0.04),("S",0.01)]
NGANPHIEU_RANGE = {"D":(1,5),"C":(5,10),"B":(10,500),"A":(500,2000),"S":(2000,50000)}
PROB_ITEM_IN_RUONG = 0.40

MAP_POOL = ["Biện Kinh","Đào Khê Thôn","Tam Thanh Sơn","Hàng Châu","Từ Châu","Nhạn Môn Quan","Discord NTH Fan"]

ITEM_TYPES = ["Kiếm","Thương","Đàn","Trượng","Dải Lụa","Găng Tay","Áo Giáp"]

ITEM_VALUE_RANGE = {"D":(20,100),"C":(100,500),"B":(500,5000),"A":(5000,20000),"S":(20000,200000)}
ITEM_NAMES = {
    "Kiếm":[("Kiếm Sắt","D"),("Kiếm Lam Tinh","C"),("Kiếm Hàn Vân","B"),("Kiếm Trúc Nguyệt","A"),("Kiếm Thượng Thần","S")],
    "Thương":[("Thương Sơ","D"),("Thương Bão Tố","C"),("Thương Tiêu Hồn","B"),("Thương Huyền Vũ","A"),("Thương Chấn Thiên","S")],
    "Đàn":[("Đàn Tre","D"),("Đàn Thanh","C"),("Đàn Hồn Thanh","B"),("Đàn Pháp Nguyệt","A"),("Đàn Thiên Nhạc","S")],
    "Trượng":[("Trượng Gỗ","D"),("Trượng Ma","C"),("Trượng Phong Ảnh","B"),("Trượng Linh Ngưng","A"),("Trượng Càn Khôn","S")],
    "Dải Lụa":[("Lụa Tầm Thôn","D"),("Lụa Thanh","C"),("Lụa Huyễn Liễu","B"),("Lụa Phượng Hoàng","A"),("Lụa Mị Ảnh","S")],
    "Găng Tay":[("Găng Vải","D"),("Găng Bão","C"),("Găng Ma Pháp","B"),("Găng Kim Cương","A"),("Găng Vô Ảnh","S")],
    "Áo Giáp":[("Áo Da","D"),("Áo Linh Phi","C"),("Áo Ngự Vân","B"),("Áo Hắc Vô Cực","A"),("Áo Vô Song","S")]
}

# ===== CÀI ĐẶT EMOJI KẾT THÚC=====


# ====== Mô tả nhặt rương (Tu Tiên + Discord) Bắt Đầu ======
import random

MAP_DISCORD = "Discord NTH Fan"

# Mặc định (tu tiên truyền thống) — 20 câu mỗi phẩm chất
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

# Bộ mô tả riêng cho map “Discord NTH Fan” — thiên hướng sự kiện/tương lai
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
    """
    Trả về một câu mô tả khi nhặt rương:
    - Nếu map là 'Discord NTH Fan' → dùng bộ DISCORD_DESCRIPTIONS.
    - Ngược lại dùng bộ DESCRIPTIONS (tu tiên truyền thống).
    """
    pool = DISCORD_DESCRIPTIONS if map_name == MAP_DISCORD else DESCRIPTIONS
    arr = pool.get(rarity, DESCRIPTIONS.get("D", []))
    if not arr:
        arr = DESCRIPTIONS["D"]
    return random.choice(arr)
# ====== Mô tả nhặt rương (Tu Tiên + Discord) Kết Thúc ======

# ====== Cấu hình & Hằng số Kết Thúc ======

# ====== Lưu trữ & Tiện ích Bắt Đầu ======
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


import json, os, tempfile

DATA_FILE = "data.json"

def ensure_data():
    """Tạo file data mặc định nếu chưa có"""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"bot_channel": None, "active": False, "users": {}}, f, ensure_ascii=False, indent=2)

def load_data():
    """Đọc file data.json, nếu hỏng hoặc trống thì tự khôi phục; bổ sung khóa mặc định (v16)."""
    ensure_data()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        data = {"users": {}, "bot_channel": None, "active": False}
    # v16: chuẩn hóa khóa mặc định
    data.setdefault("users", {})
    # Giữ bot_channel/active để tương thích ngược, nhưng không còn dùng cho v16
    data.setdefault("bot_channel", None)
    data.setdefault("active", False)
    data.setdefault("guild_settings", {})
    return data

def save_data(data):
    """Ghi file an toàn (ATOMIC) + snapshot trước khi ghi (v16)."""
    # snapshot "pre-save" (best-effort)
    try:
        snapshot_data_v16(data, tag="pre-save", subkey="pre_save")
    except Exception:
        pass
    dir_ = os.path.dirname(os.path.abspath(DATA_FILE)) or "."
    import tempfile
    fd, tmp_path = tempfile.mkstemp(prefix="data_", suffix=".json", dir=dir_)
    os.close(fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, DATA_FILE)


def ensure_user(user_id:str):
    data = load_data()
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "ngan_phi": STARTING_NP,
            "rungs": {"D":0,"C":0,"B":0,"A":0,"S":0},
            "items": [],
            "equipped": {"slot_vukhi": None, "slot_aogiap": None},
            "cooldowns": {"ol":0},
            "stats": {"opened":0,"ol_count":0,"ngan_phi_earned_total":0,"sold_count":0,"sold_value_total":0},
            "claimed_missions": [],
            "achievements": []
        }
        save_data(data)
    return data

def choose_rarity():
    r = random.random(); acc=0.0
    for rar,p in RARITY_PROBS:
        acc += p
        if r <= acc: return rar
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
    # chọn tên theo rarity gần nhất
    candidates = [n for (n,r) in ITEM_NAMES[item_type] if r==rarity]
    name = (random.choice(candidates) if candidates else ITEM_NAMES[item_type][0][0])
    lo,hi = ITEM_VALUE_RANGE[rarity]
    value = random.randint(lo,hi)
    existing = {it["id"] for it in user_items}
    iid = gen_short_id(existing)
    return {"id": iid, "name": name, "type": item_type, "rarity": rarity, "value": value, "equipped": False}

def make_embed(title, description="", fields=None, color=0x9B5CF6, thumb=None, image=None, footer=None):
    emb = discord.Embed(title=title, description=description, color=color)
    if fields:
        for n,v,inline in fields:
            emb.add_field(name=n, value=v, inline=inline)
    if thumb: emb.set_thumbnail(url=thumb)
    if image: emb.set_image(url=image)
    if footer: emb.set_footer(text=footer)
    return emb

def format_num(n:int)->str:
    return f"{n:,}"
# ====== Lưu trữ & Tiện ích Kết Thúc ======

# ====== Khởi tạo Bot & Kiểm soát kênh Bắt Đầu ======
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("o","O"),
    intents=INTENTS,
    help_command=None,
    case_insensitive=True
)

def is_admin():
    def predicate(ctx):
        perms = getattr(getattr(ctx.author, 'guild_permissions', None), 'administrator', False)
        return bool(perms)
    return commands.check(predicate)


def owner_only():
    # Use built-in is_owner() for safety
    return commands.is_owner()

@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user} (id: {bot.user.id})")
    # v16: snapshot khi khởi động (best-effort)
    try:
        data = load_data()
        snapshot_data_v16(data, tag="startup", subkey="startup")
    except Exception:
        pass

@bot.check
async def global_channel_check(ctx):
    """Chan tat ca lenh gameplay ngoai kenh da duoc set cho server (v16+)."""
    whitelisted = {
        "setbot", "lenhquantri", "saoluu", "listbackup", "xemsaoluu", "phuchoi", "resetdata", "resetuser", "addtien", "addruong", "gianlan", "thabong", "phattu", "batanh", "olenh", "lenh", "pingg"
    }

    # Cho phép các lệnh whitelisted và lệnh trong DM
    if ctx.command and ctx.command.name in whitelisted:
        return True
    if not ctx.guild:
        return True

    # Kiểm tra kênh đã được set cho guild hiện tại
    data = load_data()
    ch_id = get_guild_channel(data, ctx.guild.id)

    # Sai kênh hoặc chưa set → cảnh báo và chặn
    if not ch_id or ctx.channel.id != int(ch_id):
        msg = "Yêu cầu Admin Discord sử dụng lệnh `osetbot` để kích hoạt BOT tại kênh này."
        try:
            await ctx.reply(msg, mention_author=False)
        except Exception:
            await ctx.send(msg)
        return False

    # Đúng kênh → cho phép
    return True

from discord.ext.commands import CommandNotFound, CommandOnCooldown, CheckFailure, CommandInvokeError, BadArgument, MissingRequiredArgument
import aiohttp
import asyncio


# ====== Lệnh hệ thống: osetbot / obatdau Kết Thúc ======



@bot.event
async def on_command_error(ctx, error):
    from discord.ext.commands import CommandNotFound, CommandOnCooldown, CheckFailure, BadArgument, MissingRequiredArgument, CommandInvokeError
    import asyncio, aiohttp

    if isinstance(error, CheckFailure):
        return

    if isinstance(error, CommandNotFound):
        await ctx.reply("❓ Lệnh không tồn tại. Dùng `olenh` để xem danh sách.", mention_author=False)
        return

    if isinstance(error, CommandOnCooldown):
        await ctx.reply(f"⏳ Vui lòng chờ thêm {int(error.retry_after)} giây.", mention_author=False)
        return

    if isinstance(error, MissingRequiredArgument):
        name = getattr(ctx.command, "name", "")
        if name in {"mac","thao","xem"}:
            await ctx.reply(f"📝 Lệnh `{name}` cần ID. Ví dụ: `{name} 123`.", mention_author=False)
            return
        if name in {"dt"}:
            await ctx.reply("📝 Dùng: `odt <số_ngân_phiếu>` — ví dụ: `odt 1000`.", mention_author=False)
            return
        await ctx.reply("📝 Thiếu tham số. Dùng `olenh` để xem cú pháp.", mention_author=False)
        return

    if isinstance(error, BadArgument):
        name = getattr(ctx.command, "name", "")
        if name in {"dt"}:
            await ctx.reply("⚠️ Số tiền cược không hợp lệ. Ví dụ: `odt 500`.", mention_author=False)
            return
        if name in {"addtien","addruong"}:
            await ctx.reply("⚠️ Số lượng không hợp lệ. Ví dụ: `oaddtien @user 1,000`.", mention_author=False)
            return
        await ctx.reply("⚠️ Tham số không hợp lệ. Kiểm tra lại cú pháp.", mention_author=False)
        return

    # Ảnh lỗi → im lặng bỏ qua
    if isinstance(error, CommandInvokeError):
        orig = getattr(error, "original", None)
        try:
            import aiohttp  # ensure name exists
        except Exception:
            aiohttp = None
        if aiohttp and isinstance(orig, (aiohttp.ClientResponseError, aiohttp.ClientPayloadError)):
            return
        import asyncio
        if isinstance(orig, asyncio.TimeoutError):
            return

    raise error


    if isinstance(error, CommandNotFound):
        await ctx.reply("❓ Lệnh không tồn tại. Dùng `olenh` để xem danh sách.", mention_author=False)
        return

    if isinstance(error, CommandOnCooldown):
        await ctx.reply(f"⏳ Vui lòng chờ thêm {int(error.retry_after)} giây.", mention_author=False)
        return

    # Thiếu tham số
    if isinstance(error, MissingRequiredArgument):
        name = getattr(ctx.command, "name", "")
        if name in {"mac","thao","xem"}:
            await ctx.reply(f"📝 Lệnh `{name}` cần ID. Ví dụ: `{name} 123`.", mention_author=False)
            return
        if name in {"dt"}:
            await ctx.reply("📝 Dùng: `odt <số_ngân_phiếu>` — ví dụ: `odt 1000`.", mention_author=False)
            return
        await ctx.reply("📝 Thiếu tham số. Dùng `olenh` để xem cú pháp.", mention_author=False)
        return

    # Sai kiểu tham số (ví dụ nhập 'all' cho số nguyên...)
    if isinstance(error, BadArgument):
        name = getattr(ctx.command, "name", "")
        if name in {"dt"}:
            await ctx.reply("⚠️ Số tiền cược không hợp lệ. Ví dụ: `odt 500`.", mention_author=False)
            return
        if name in {"addtien","addruong"}:
            await ctx.reply("⚠️ Số lượng không hợp lệ. Ví dụ: `oaddtien @user 1000`.", mention_author=False)
            return
        await ctx.reply("⚠️ Tham số không hợp lệ. Kiểm tra lại cú pháp.", mention_author=False)
        return

    # Lỗi do gọi API/ảnh (ví dụ 503 từ host ảnh)
    if isinstance(error, CommandInvokeError):
        orig = getattr(error, 'original', None)
        if isinstance(orig, (aiohttp.ClientResponseError, aiohttp.ClientPayloadError, asyncio.TimeoutError)):
            await ctx.reply("⚠️ Gần đây đang xuất hiện thổ phỉ, không an toàn. Hãy mở rương lại sau vài giây", mention_author=False)
            return

    # Các lỗi khác: để nổi lên để còn debug
    raise error

# ====== Khởi tạo Bot & Kiểm soát kênh Kết Thúc ======



# ===== ẢNH & CẤU HÌNH HIỂN THỊ ẢNH (Helper) BẮT ĐẦU =====
def _get_cfg(data: dict) -> dict:
    cfg = data.setdefault("config", {})
    if "images_enabled" not in cfg:
        cfg["images_enabled"] = True
    return cfg

def images_enabled_global() -> bool:
    data = load_data()
    cfg = _get_cfg(data)
    return bool(cfg.get("images_enabled", True))

def should_show_images(ctx, command_name: str = None) -> bool:
    data = load_data()
    cfg = _get_cfg(data)
    enabled = bool(cfg.get("images_enabled", True))
    return enabled
# ===== ẢNH & CẤU HÌNH HIỂN THỊ ẢNH (Helper) KẾT THÚC =====


# ====== Lệnh gameplay: ol / omo / oban Bắt Đầu ======
@bot.command(name="lenh")
async def cmd_olenh(ctx):
    desc = (
        "**⚔️ LỆNH CƠ BẢN — GAME NGH OFFLINE**\n\n"
        "`osetbot` — Kích hoạt BOT trong kênh *(Admin)*\n"
        "`osetbot off` — Tắt BOT tạm thời trong kênh\n"
        "`ol` — Đi thám hiểm, tìm rương báu (CD 10s)\n"
        "`omo` — Mở rương đơn (VD: omo D)\n"
        "`omo all` — Mở 50 rương 1 lần\n"
        "`odt` hoặc `odt all` — Đổ thạch\n"
        "`okho` — Mở kho xem toàn bộ trang bị\n"
        "`oban all` — Bán tất cả trang bị không mặc\n"
        "`oban <D|C|B|A|S> all` — Bán trang bị theo phẩm\n"
        "`omac <ID>` — Mặc trang bị (theo ID trong kho)\n"
        "`othao <ID>` — Tháo trang bị đang mặc\n"
        "`oxem <ID>` — Xem chi tiết trang bị (có ảnh)\n"
        "`onhanvat` — Xem chỉ số nhân vật, lực chiến\n"
    )

    embed = discord.Embed(
        title="📜 DANH SÁCH LỆNH CƠ BẢN",
        description=desc,
        color=0xFFD700
    )
    embed.set_footer(text="BOT GAME NGH OFFLINE | Phiên bản v18.2")
    await ctx.reply(embed=embed, mention_author=False)


# ====== Lệnh ol bắt đầu ======

@bot.command(name="l", aliases=["ol"])
async def cmd_ol(ctx):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    now = time.time()
    if now < user["cooldowns"]["ol"]:
        await ctx.reply(f"⏳ Hãy chờ {int(user['cooldowns']['ol'] - now)} giây nữa.", mention_author=False)
        return

    # Xác định phẩm rương và địa danh
    rarity = choose_rarity()
    map_loc = random.choice(MAP_POOL)

    # Cập nhật dữ liệu người chơi
    user["rungs"][rarity] += 1
    user["stats"]["ol_count"] += 1
    user["cooldowns"]["ol"] = now + COOLDOWN_OL
    save_data(data)

    rarity_name = {"D":"Phổ Thông","C":"Hiếm","B":"Tuyệt Phẩm","A":"Sử Thi","S":"Truyền Thuyết"}[rarity]
    title = f"**[{map_loc}]** **{ctx.author.display_name}** Thu được Rương trang bị {rarity_name} {RARITY_CHEST_EMOJI[rarity]} x1"
    desc = get_loot_description(map_loc, rarity)

    emb = make_embed(
        title=title,
        description=desc,
        color=RARITY_COLOR[rarity],
        footer=ctx.author.display_name
    )

    # Hiển thị bản đồ theo phẩm rương nếu ảnh đang bật
    _map_urls = {
        "S": "https://sv2.anhsieuviet.com/2025/10/28/5-min.png",
        "A": "https://sv2.anhsieuviet.com/2025/10/28/4-min.png",
        "B": "https://sv2.anhsieuviet.com/2025/10/28/3-min.png",
        "C": "https://sv2.anhsieuviet.com/2025/10/28/2-min.png",
        "D": "https://sv2.anhsieuviet.com/2025/10/28/1-min.png",
    }
    if should_show_images(ctx, command_name="ol"):
        try:
            emb.set_image(url=_map_urls.get(rarity, IMG_BANDO_DEFAULT))
        except Exception:
            pass

    msg = await ctx.send(embed=emb)

    # Thu gọn: xóa ảnh sau 3 giây để giảm spam
    try:
        import asyncio
        await asyncio.sleep(3)
        if emb.image:
            emb.set_image(url=discord.Embed.Empty)
            await msg.edit(embed=emb)
    except Exception:
        pass

# ====== Lệnh ol kết thúc ======


# ====== Lệnh mở rương: omo (không ảnh, có mở theo phẩm) BẮT ĐẦU ======

# Emoji rương (OPENED)
RARITY_CHEST_OPENED_EMOJI = {
    "D": "<a:rd_m:1431717929782870116>",
    "C": "<a:rc_m:1431713195860693164>",
    "B": "<a:rb_m:1431713187924934686>",
    "A": "<a:ra_m:1431713174704492604>",
    "S": "<a:rs_m:1431717941065547866>",
}

def _rarity_order_index(r: str) -> int:
    order = ["S", "A", "B", "C", "D"]  # S cao nhất
    try:
        return order.index(r)
    except ValueError:
        return 99

def _pick_highest_available_rarity(user) -> str | None:
    for r in ["S", "A", "B", "C", "D"]:
        if int(user["rungs"].get(r, 0)) > 0:
            return r
    return None

def _open_one_chest(user, r: str):
    """Mở 1 rương phẩm r, trả về (np, item_or_None)."""
    user["rungs"][r] = int(user["rungs"].get(r, 0)) - 1
    gp = get_nganphieu(r)
    user["ngan_phi"] = int(user.get("ngan_phi", 0)) + gp
    # thống kê nhẹ nếu bạn đang dùng
    user.setdefault("stats", {})
    user["stats"]["ngan_phi_earned_total"] = int(user["stats"].get("ngan_phi_earned_total", 0)) + gp
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
    # Ví dụ: A `857` Đàn Pháp Nguyệt — Giá trị: 5,639
    return f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} — Giá trị: {format_num(it['value'])}"

def _open_many_for_rarity(user, r: str, limit: int = 50):
    """Mở nhiều rương của 1 phẩm r, tối đa limit. Trả về (opened, total_np, items:list)."""
    opened = 0
    total_np = 0
    items: list[dict] = []
    while opened < limit and int(user["rungs"].get(r, 0)) > 0:
        gp, it = _open_one_chest(user, r)
        opened += 1
        total_np += gp
        if it:
            items.append(it)
    return opened, total_np, items

@bot.command(name="mo")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_omo(ctx, *args):
    """Mở rương:
    - `omo` → mở 1 rương (ưu tiên S→A→B→C→D)
    - `omo all` → mở tối đa 50 rương (tổng hợp nhiều phẩm)
    - `omo <d|c|b|a|s>` → mở 1 rương đúng phẩm chỉ định
    - `omo <d|c|b|a|s> <số>` → mở N rương đúng phẩm (tối đa 50)
    - `omo <d|c|b|a|s> all` → mở tối đa 50 rương của phẩm chỉ định
    """
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    argv = [a.strip().lower() for a in args]

    # ===== Nhánh: omo all (mở tổng hợp nhiều phẩm, tối đa 50) =====
    if len(argv) == 1 and argv[0] == "all":
        LIMIT = 50
        opened = 0
        total_np = 0
        items: list[dict] = []
        per_rarity = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
        highest_seen: str | None = None

        for r in ["S", "A", "B", "C", "D"]:
            while opened < LIMIT and int(user["rungs"].get(r, 0)) > 0:
                gp, it = _open_one_chest(user, r)
                opened += 1
                total_np += gp
                per_rarity[r] += 1
                if it:
                    items.append(it)
                    if (highest_seen is None) or (_rarity_order_index(it["rarity"]) < _rarity_order_index(highest_seen)):
                        highest_seen = it["rarity"]

        if opened == 0:
            await ctx.reply("❗ Bạn không có rương để mở.", mention_author=False)
            return

        highest_for_title = highest_seen
        if not highest_for_title:
            for r in ["S", "A", "B", "C", "D"]:
                if per_rarity[r] > 0:
                    highest_for_title = r
                    break

        title_emoji = RARITY_CHEST_OPENED_EMOJI.get(highest_for_title or "D", "🎁")
        title = f"{title_emoji} **{ctx.author.display_name}** đã mở x{opened} rương"
        emb = make_embed(title=title, color=0x2ECC71, footer=ctx.author.display_name)

        rewards_block = (
            f"{NP_EMOJI}\u2003Ngân Phiếu: **{format_num(total_np)}**\n"
            f"{EMOJI_TRANG_BI_COUNT}\u2003Trang bị: **{len(items)}**"
        )
        emb.add_field(name="Phần thưởng nhận được", value=rewards_block, inline=False)

        breakdown_lines = [f"{RARITY_EMOJI[r]} x{per_rarity[r]}" for r in ["S","A","B","C","D"] if per_rarity[r] > 0]
        if breakdown_lines:
            emb.add_field(name="Đã mở", value="  ".join(breakdown_lines), inline=False)

        if items:
            lines = [_fmt_item_line(it) for it in items]
            if len(lines) > 10:
                extra = len(lines) - 10
                lines = lines[:10] + [f"... và {extra} món khác"]
            emb.add_field(name="Vật phẩm nhận được", value="\n".join(lines), inline=False)

        remaining = sum(int(user["rungs"].get(r, 0)) for r in ["S","A","B","C","D"])
        if remaining > 0:
            emb.set_footer(text=f"Còn {remaining} rương — dùng omo all hoặc omo <phẩm> all để mở tiếp")

        save_data(data)
        await ctx.send(embed=emb)
        return

    # ===== Nhánh: omo <r> [n|all] (mở theo phẩm chỉ định) =====
    if len(argv) >= 1 and argv[0] in {"d","c","b","a","s"}:
        r = argv[0].upper()
        available = int(user["rungs"].get(r, 0))
        if available <= 0:
            await ctx.reply(f"❗ Bạn không có rương phẩm {r}.", mention_author=False)
            return

        # số lượng yêu cầu
        req = 1
        if len(argv) >= 2:
            if argv[1] == "all":
                req = min(50, available)
            else:
                try:
                    req = int(argv[1].replace(",", ""))
                except Exception:
                    await ctx.reply("⚠️ Số lượng không hợp lệ. Ví dụ: `omo d 3` hoặc `omo d all`.", mention_author=False)
                    return
                if req <= 0:
                    await ctx.reply("⚠️ Số lượng phải > 0.", mention_author=False)
                    return
                if req > 50:
                    await ctx.reply("⚠️ Mỗi lần chỉ mở tối đa **50** rương.", mention_author=False)
                    return
                if req > available:
                    await ctx.reply(f"⚠️ Bạn chỉ có **{available}** rương {r}.", mention_author=False)
                    return

        opened, total_np, items = _open_many_for_rarity(user, r, limit=req)
        if opened == 0:
            await ctx.reply("❗ Không mở được rương nào.", mention_author=False)
            return

        title_emoji = RARITY_CHEST_OPENED_EMOJI.get(r, "🎁")
        title = f"{title_emoji} **{ctx.author.display_name}** đã mở x{opened} rương"
        emb = make_embed(title=title, color=RARITY_COLOR.get(r, 0x95A5A6), footer=ctx.author.display_name)

        rewards_block = (
            f"{NP_EMOJI}\u2003Ngân Phiếu: **{format_num(total_np)}**\n"
            f"{EMOJI_TRANG_BI_COUNT}\u2003Trang bị: **{len(items)}**"
        )
        emb.add_field(name="Phần thưởng nhận được", value=rewards_block, inline=False)

        if items:
            lines = [_fmt_item_line(it) for it in items]
            if len(lines) > 10:
                extra = len(lines) - 10
                lines = lines[:10] + [f"... và {extra} món khác"]
            emb.add_field(name="Vật phẩm nhận được", value="\n".join(lines), inline=False)

        remaining_r = int(user["rungs"].get(r, 0))
        if remaining_r > 0:
            emb.set_footer(text=f"Còn {remaining_r} rương {r} — dùng omo {r.lower()} all để mở tiếp")

        save_data(data)
        await ctx.send(embed=emb)
        return

    # ===== Mặc định: omo (mở 1 rương ưu tiên S→D) =====
    r_found = _pick_highest_available_rarity(user)
    if not r_found:
        await ctx.reply("❗ Bạn không có rương để mở.", mention_author=False)
        return

    gp, item = _open_one_chest(user, r_found)
    save_data(data)

    highest_for_title = item["rarity"] if item else r_found
    title_emoji = RARITY_CHEST_OPENED_EMOJI.get(highest_for_title, "🎁")
    title = f"{title_emoji} **{ctx.author.display_name}** đã mở 1 rương"
    emb = make_embed(title=title, color=RARITY_COLOR.get(highest_for_title, 0x95A5A6), footer=ctx.author.display_name)

    rewards_block = (
        f"{NP_EMOJI}\u2003Ngân Phiếu: **{format_num(gp)}**\n"
        f"{EMOJI_TRANG_BI_COUNT}\u2003Trang bị: **{1 if item else 0}**"
    )
    emb.add_field(name="Phần thưởng nhận được", value=rewards_block, inline=False)

    if item:
        emb.add_field(name="Vật phẩm nhận được", value=_fmt_item_line(item), inline=False)

    # CHỈ 1 lần gửi — ĐÃ SỬA LỖI GỬI TRÙNG
    await ctx.send(embed=emb)
    return

    # ===== Nếu người chơi nhập sai cú pháp (sẽ không tới đây nếu đã return ở trên) =====
    usage_text = (
        "⚠️ Cú pháp lệnh không hợp lệ.\n\n"
        "**Cách dùng hợp lệ:**\n"
        "`omo` → Mở 1 rương (ưu tiên S→A→B→C→D)\n"
        "`omo all` → Mở tối đa 50 rương (tổng hợp nhiều phẩm)\n"
        "`omo <d|c|b|a|s>` → Mở 1 rương theo phẩm chỉ định\n"
        "`omo <d|c|b|a|s> <số>` → Mở N rương (tối đa 50)\n"
        "`omo <d|c|b|a|s> all` → Mở tối đa 50 rương của phẩm chỉ định"
    )
    await ctx.reply(usage_text, mention_author=False)

# ====== Lệnh mở rương: omo (không ảnh, có mở theo phẩm) KẾT THÚC ======



# ====== Lệnh BÁN ĐỒ BẮT ĐẦU ======
@bot.command(name="ban")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_oban(ctx, *args):
    user_id=str(ctx.author.id); data=ensure_user(user_id); user=data["users"][user_id]
    args=list(args)
    def settle(lst):
        total=sum(it["value"] for it in lst)
        user["ngan_phi"]+=total
        user["stats"]["sold_count"]+=len(lst)
        user["stats"]["sold_value_total"]+=total
        return total
    if not args:
        await ctx.reply("Cú pháp: `oban all` hoặc `oban <D|C|B|A|S> all`", mention_author=False); return
    if args[0].lower()=="all":
        sell=[it for it in user["items"] if not it["equipped"]]
        if not sell: await ctx.reply("Không có trang bị rảnh để bán.", mention_author=False); return
        total=settle(sell)
        user["items"]=[it for it in user["items"] if it["equipped"]]
        save_data(data)
        await ctx.send(embed=make_embed("🧾 Bán vật phẩm", f"Đã bán **{len(sell)}** món — Nhận **{NP_EMOJI} {format_num(total)}**",  color=0xE67E22, footer=ctx.author.display_name)); return
    if len(args)>=2 and args[1].lower()=="all":
        rar=args[0].upper()
        if rar not in ["D","C","B","A","S"]:
            await ctx.reply("Phẩm chất không hợp lệ (D/C/B/A/S).", mention_author=False); return
        sell=[it for it in user["items"] if (it["rarity"]==rar and not it["equipped"])]
        if not sell: await ctx.reply(f"Không có vật phẩm phẩm chất {rar} để bán.", mention_author=False); return
        total=settle(sell)
        user["items"]=[it for it in user["items"] if not (it["rarity"]==rar and not it["equipped"])]
        save_data(data)
        await ctx.send(embed=make_embed("🧾 Bán vật phẩm", f"Đã bán **{len(sell)}** món {rar} — Nhận **{NP_EMOJI} {format_num(total)}**", color=RARITY_COLOR.get(rar,0x95A5A6), footer=ctx.author.display_name)); return
    await ctx.reply("Cú pháp không hợp lệ. Ví dụ: `oban all` hoặc `oban D all`.", mention_author=False)
# ====== Lệnh gameplay: ol / omo / oban Kết Thúc ======

# ====== Lệnh kho: okho / omac / othao / oxem Bắt Đầu ======
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
            await interaction.response.send_message("❗ Chỉ chủ kho mới thao tác được.", ephemeral=True)
            return
        content = "\n".join([f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} — {it['type']}" for it in self.slice()]) or "Không có vật phẩm"
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

@bot.command(name="kho")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_okho(ctx):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]

    # Lọc vật phẩm chưa mặc
    items_show = [it for it in user["items"] if not it["equipped"]]
    page_items = items_show[:10]
    content = "\n".join([
        f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} — {it['type']}"
        for it in page_items
    ]) or "Không có vật phẩm"

    # Tổng số trang
    page_total = max(1, (len(items_show) - 1)//10 + 1)

    # Tạo embed hiển thị kho đồ
    emb = make_embed(
        f"📦 {ctx.author.display_name} — Kho nhân vật",
        color=0x3498DB,
        footer=f"Trang 1/{page_total}"
    )

    # Tổng rương
    total_r = (
        user["rungs"]["D"]
        + user["rungs"]["C"]
        + user["rungs"]["B"]
        + user["rungs"]["A"]
        + user["rungs"]["S"]
    )

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
    value="\u200b",   # zero-width space để không xuống dòng nội dung
    inline=True
    )
    emb.add_field(name="Trang bị", value=content, inline=False)

    stats_text = (
        f"Rương đã mở: {format_num(user['stats']['opened'])}\n"
        f"Số lần thám hiểm: {format_num(user['stats']['ol_count'])}\n"
        f"{NP_EMOJI}Tổng NP đã kiếm được: {format_num(user['stats']['ngan_phi_earned_total'])}"
    )
    emb.add_field(name="📊 Thống kê", value=stats_text, inline=False)

    # Gửi embed kèm ảnh kho đồ
    async with aiohttp.ClientSession() as sess:
        file = await file_from_url_cached(IMG_KHO_DO, "khodo.png")  # dùng ảnh kho đồ
        emb.set_image(url="attachment://khodo.png")
        view = KhoView(ctx.author.id, items_show, page=0, per_page=10)
        view.children[0].disabled = True
        view.children[1].disabled = (len(items_show) <= 10)
        msg = await ctx.send(embed=emb, file=file, view=view)

        # Tự động xóa ảnh sau 3 giây để tránh spam
        try:
            import asyncio
            await asyncio.sleep(3)
            emb.set_image(url=discord.Embed.Empty)
            try:
                await msg.edit(embed=emb, attachments=[], view=view)
            except TypeError:
                await msg.edit(embed=emb, view=view)
        except Exception:
            pass

@bot.command(name="mac")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_omac(ctx, item_id: str = None):
    if item_id is None:
        await ctx.reply("📝 Cách dùng: `mac <ID>` (Xem ID trong `okho`).", mention_author=False)
        return
    user_id = str(ctx.author.id)
    data = ensure_user(user_id); user = data["users"][user_id]

    target = next((it for it in user["items"] if it["id"] == item_id), None)
    if not target:
        await ctx.reply("❗ Không tìm thấy vật phẩm với ID đó.", mention_author=False)
        return
    if target["equipped"]:
        await ctx.reply("Vật phẩm đang được mặc.", mention_author=False)
        return

    slot = slot_of(target["type"])
    if user["equipped"][slot]:
        cur_id = user["equipped"][slot]
        cur_item = next((it for it in user["items"] if it["id"] == cur_id), None)
        await ctx.reply(
            f"🔧 Slot đang bận bởi **{cur_item['name']}** (ID {cur_item['id']}). Hãy dùng `othao {cur_item['id']}` để tháo.",
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


@bot.command(name="thao")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_othao(ctx, item_id: str = None):
    if item_id is None:
        await ctx.reply("📝 Cách dùng: `thao <ID>` (Xem ID trong `okho`).", mention_author=False)
        return
    user_id = str(ctx.author.id)
    data = ensure_user(user_id); user = data["users"][user_id]

    target = next((it for it in user["items"] if it["id"] == item_id), None)
    if not target:
        await ctx.reply("❗ Không tìm thấy vật phẩm với ID đó.", mention_author=False)
        return
    if not target["equipped"]:
        await ctx.reply("Vật phẩm không đang mặc.", mention_author=False)
        return

    slot = slot_of(target["type"])
    user["equipped"][slot] = None
    target["equipped"] = False  # trả về kho, không hoàn rương
    save_data(data)

    emoji = RARITY_EMOJI[target["rarity"]]
    emb = make_embed(
        title="🪶 Tháo trang bị",
        description=f"Đã tháo {emoji} **{target['name']}** (ID `{target['id']}`) → kiểm tra lại món đồ tại Kho.",
        color=0x95A5A6,
        footer=f"{ctx.author.display_name}"
    )
    await ctx.send(embed=emb)


@bot.command(name="xem")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_oxem(ctx, item_id: str = None):
    if item_id is None:
        await ctx.reply("📝 Cách dùng: `xem <ID>` (Xem ID trong `okho`).", mention_author=False)
        return
    user_id = str(ctx.author.id)
    data = ensure_user(user_id); user = data["users"][user_id]

    it = next((x for x in user["items"] if x["id"] == item_id), None)
    if not it:
        await ctx.reply("❗ Không tìm thấy trang bị với ID đó.", mention_author=False)
        return

    state = "Đang mặc" if it["equipped"] else "Trong kho"
    emoji = RARITY_EMOJI[it["rarity"]]

    emb = make_embed(
        title=f"{emoji} `{it['id']}` {it['name']}",
        description=f"Loại: **{it['type']}** • Phẩm chất: {emoji} • Trạng thái: **{state}**",
        color=RARITY_COLOR[it["rarity"]],
        footer=ctx.author.display_name
    )

    # Ảnh riêng theo loại trang bị
    img_url = ITEM_IMAGE.get(it["type"], IMG_BANDO_DEFAULT)
    file = await file_from_url_cached(img_url, "item.png")
    emb.set_image(url="attachment://item.png")
    msg = await ctx.send(embed=emb)

    # (ảnh đã được chuẩn bị ở trên; nếu muốn gắn lại thì cần gọi _attach_image_later thủ công)
# ====== Lệnh kho: okho / omac / othao / oxem Kết Thúc ======

# ====== Lệnh nhân vật: onhanvat Bắt Đầu ======
@bot.command(name="nhanvat")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_onhanvat(ctx, member: discord.Member=None):
    target = member or ctx.author
    user_id=str(target.id); data=ensure_user(user_id); user=data["users"][user_id]
    equip_lines=[]
    for slot, iid in user["equipped"].items():
        if iid:
            it = next((x for x in user["items"] if x["id"]==iid), None)
            if it:
                equip_lines.append(f"{RARITY_EMOJI[it['rarity']]} `{it['id']}` {it['name']} — {it['type']}")
    emb = make_embed(f"🧭 Nhân vật — {target.display_name}", color=0x9B59B6, footer=f"Yêu cầu bởi {ctx.author.display_name}")
    emb.add_field(name=f"{NP_EMOJI} Ngân Phiếu", value=format_num(user["ngan_phi"]), inline=True)
    emb.add_field(name="Trang bị đang mặc", value="\n".join(equip_lines) if equip_lines else "Không có", inline=False)
    # Ảnh nhân vật riêng
    file = await file_from_url_cached(IMG_NHAN_VAT, "nhanvat.png")
    emb.set_image(url="attachment://nhanvat.png")
    msg = await ctx.send(embed=emb)

    # (ảnh đã được chuẩn bị ở trên; nếu muốn gắn lại thì cần gọi _attach_image_later thủ công)
# ====== Lệnh nhân vật: onhanvat Kết Thúc ======

# ====== ĐỔ THẠCH (odt) + JACKPOT (bản hiển thị tối ưu) — BẮT ĐẦU ======
import time, random, asyncio, discord
from discord.ext import commands

# --- EMOJI (giữ như bản bạn gửi) ---
EMOJI_DOTHACH      = "<a:dothach:1431793311978491914>"
EMOJI_DOTHACHT     = "<:dothacht:1431806329529303041>"
EMOJI_NOHU4        = "<a:nohu5:1432589822740004934>"
EMOJI_DOTHACH1     = "<a:dothach1:1432592899694002286>"
EMOJI_DOTHACHTHUA  = "<:dothachthua:1432755827621757038>"
NP_EMOJI           = "<a:np:1431713164277448888>"
EMOJI_CANHBAO      = "<:thongbao:1432852057353621586>"


# --- MÔ TẢ NGẪU NHIÊN ---
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

# --- CẤU HÌNH ---
ODT_MAX_BET        = 250_000
POOL_ON_LOSS_RATE  = 1.0

# --- JACKPOT (#1 an toàn) ---
JACKPOT_PCT         = 0.10
JACKPOT_GATE        = 0.05
JACKPOT_BASE        = 0.02
JACKPOT_HOT_BOOST   = 0.01
JACKPOT_HOT_CAP     = 5.0
JACKPOT_WINDOW_SEC  = 5 * 60
JACKPOT_THRESH_MIN  = 10_000_000
JACKPOT_THRESH_MAX  = 12_000_000
JACKPOT_THRESH_STEP = 1_000_000

# --- CÁC HÀM HỖ TRỢ ---
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
    if r < p5: return 5
    if r < p5 + p2: return 2
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

# --- LỆNH ODT ---
@bot.command(name="odt", aliases=["dt"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_odt(ctx, amount: str = None):
    user_id = str(ctx.author.id)
    data = ensure_user(user_id)
    user = data["users"][user_id]
    odt_state = _odt_init_state(user)

    # Parse tiền cược
    if amount is None:
        await ctx.reply("💬 Dùng: `odt <số tiền>` hoặc `odt all`. Ví dụ: `odt 1,000`.", mention_author=False)
        return

    a = str(amount).strip().lower()
    if a == "all":
        amount_val = min(int(user.get("ngan_phi", 0)), ODT_MAX_BET)
        if amount_val <= 0:
            await ctx.reply("❗ Số dư bằng 0 — không thể `odt all`.", mention_author=False)
            return
    else:
        try:
            amount_val = int(a.replace(",", ""))
            if amount_val <= 0:
                raise ValueError()
        except Exception:
            await ctx.reply("⚠️ Số tiền không hợp lệ. Ví dụ: `odt 500`, `odt 1,000` hoặc `odt all`.", mention_author=False)
            return
        if amount_val > ODT_MAX_BET:
            await ctx.reply(f"⚠️ Mỗi ván tối đa {format_num(ODT_MAX_BET)} Ngân Phiếu.", mention_author=False)
            return

    bal = int(user.get("ngan_phi", 0))
    if bal < amount_val:
        await ctx.reply(f"❗ Bạn không đủ Ngân Phiếu. (Hiện có: {format_num(bal)})", mention_author=False)
        return

    user["ngan_phi"] = bal - amount_val
    save_data(data)

    outcome = _odt_pick_outcome(odt_state)
    try:
        map_name = random.choice(MAP_POOL)
    except Exception:
        map_name = random.choice(["Biện Kinh", "Đào Khê Thôn", "Tam Thanh Sơn", "Hàng Châu", "Từ Châu", "Nhạn Môn Quan"])

    title = f"Đổ Thạch — {map_name}"
    color = 0x2ECC71 if outcome else 0xE74C3C
    jackpot_announce = ""

    if outcome == 0:
        odt_state["loss_streak"] += 1
        odt_state["win_streak"] = 0
        jp = _jp(data)
        jp["pool"] = int(jp.get("pool", 0)) + int(amount_val * POOL_ON_LOSS_RATE)

        text = random.choice(ODT_TEXTS_LOSE)
        desc = (
            f"**{ctx.author.display_name}** bỏ ra **{format_num(amount_val)}** **Ngân Phiếu**\n"
            f"Để mua một viên đá {EMOJI_DOTHACHT} phát sáng tại thạch phường {map_name}.\n\n"
            f"💬 {text}\n"
            f"{EMOJI_DOTHACHTHUA} Trắng tay thu về **0 Ngân Phiếu**."
        )

        gain = _try_jackpot(data, ctx.author)
        if gain > 0:
            user["ngan_phi"] += gain
            jackpot_announce = (
                f"\n\n🎉 **Quỹ Thạch Phường NỔ HŨ!** {ctx.author.mention} nhận **{format_num(gain)}** Ngân Phiếu."
            )
            try:
                await ctx.author.send(
                    f"{NP_EMOJI} Chúc mừng! Bạn vừa trúng **{format_num(gain)}** Ngân Phiếu từ Quỹ Thạch Phường."
                )
            except Exception:
                pass

        save_data(data)

    else:
        odt_state["win_streak"] += 1
        odt_state["loss_streak"] = 0
        reward = amount_val * outcome
        user["ngan_phi"] += reward

        text = random.choice(ODT_TEXTS_WIN)
        if outcome == 5:
            desc = (
                f"**{ctx.author.display_name}** bỏ ra **{format_num(amount_val)}** **Ngân Phiếu**\n"
                f"Để mua một viên đá {EMOJI_DOTHACHT} phát sáng tại thạch phường {map_name}.\n\n"
                f"💬 {text}\n"
                f"{EMOJI_DOTHACH} Thật bất ngờ, chủ thạch phường tổ chức đấu giá vật phẩm bạn mở ra từ viên đá!\n"
                f"— Thu về x5 giá trị nhận **{format_num(reward)} Ngân Phiếu!**"
            )
        else:
            desc = (
                f"**{ctx.author.display_name}** bỏ ra **{format_num(amount_val)}** **Ngân Phiếu**\n"
                f"Để mua một viên đá {EMOJI_DOTHACHT} phát sáng tại thạch phường {map_name}.\n\n"
                f"💬 {text}\n"
                f"{EMOJI_DOTHACH} Bất ngờ lãi lớn — thu về **{format_num(reward)} Ngân Phiếu**!"
            )

        _jp_open_window_if_needed(_jp(data), time.time())
        save_data(data)

    pool_now = int(_jp(data).get("pool", 0))
    footer_text = (
        f"Số dư hiện tại: {format_num(user['ngan_phi'])} Ngân Phiếu\n"
        f"Quỹ Thạch Phường: {format_num(pool_now)} Ngân Phiếu\n"
        f"Nếu may mắn, bạn sẽ nhận {int(JACKPOT_PCT * 100)}%"
    )

    emb = make_embed(
        title=title,
        description=desc + jackpot_announce,
        color=color,
        footer=footer_text
    )
    await ctx.send(content=(ctx.author.mention if jackpot_announce else None), embed=emb)

@cmd_odt.error
async def cmd_odt_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"⏳ Bạn cần chờ {error.retry_after:.1f}s nữa mới có thể đổ thạch tiếp.", mention_author=False)

# ====== ĐỔ THẠCH (odt) + JACKPOT (hiển thị tối ưu) — KẾT THÚC ======






# ====== LỆNH QUẢN TRỊ OWNER - BẮT ĐẦU ======

# ==== QUYỀN CHỦ BOT & KIỂM TRA OWNER BẮT ĐẦU ====
BOT_OWNERS = {821066331826421840}  # <— ID Discord của bạn, có thể thêm nhiều

def is_owner_user(user, bot):
    """Kiểm tra xem user có phải chủ bot hay không"""
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
# ==== QUYỀN CHỦ BOT & KIỂM TRA OWNER KẾT THÚC ====



@bot.command(name="lenhquantri")
@owner_only()
async def cmd_olenhquantri(ctx):
    """Hiển thị danh sách lệnh quản trị dành riêng cho Chủ BOT."""
    lines = [
        "**LỆNH CHỦ BOT (Owner)**",
        "`saoluu` — Tạo bản sao lưu thủ công ngay lập tức",
        "`olistbackup [limit]` — Liệt kê các bản sao lưu gần đây",
        "`xemsaoluu` — Xem thống kê backup (số file, dung lượng, bản gần nhất)",
        "`phuchoi` — Khôi phục dữ liệu từ backup",
        "`resetdata` — Reset toàn bộ dữ liệu (tự sao lưu trước khi làm)",
        "`oresetuser @user` — Reset dữ liệu của 1 người chơi",
        "`oaddtien @user <số>` — Cộng Ngân Phiếu",
        "`oaddruong @user <phẩm> <số>` — Cấp rương",
        "`export` / `import` — Xuất/Nhập dữ liệu",
        "`obatanh` / `on/off` — bật/tắt ảnh",

    ]
    await ctx.reply("\n".join(lines), mention_author=False)

@bot.command(name="saoluu")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_osaoluu(ctx):
    """Tạo bản sao lưu thủ công, lưu vào backups/manual/"""
    data = load_data()
    try:
        path = snapshot_data_v16(data, tag="manual", subkey="manual")
        await ctx.reply(f"✅ Đã tạo bản sao lưu: `{os.path.basename(path)}`", mention_author=False)
    except Exception as e:
        await ctx.reply(f"⚠️ Sao lưu thất bại: {e}", mention_author=False)

@bot.command(name="listbackup")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_olistbackup(ctx, limit: int = 10):
    """Liệt kê các bản backup gần đây từ mọi thư mục."""
    recents = list_recent_backups_v16(limit=limit)
    if not recents:
        return await ctx.reply("Không tìm thấy bản sao lưu nào.", mention_author=False)
    lines = ["**Các bản sao lưu gần đây:**"]
    for ts, key, path in recents:
        base = os.path.basename(path)
        lines.append(f"- `{base}` — **{key}**")
    await ctx.reply("\n".join(lines), mention_author=False)

@bot.command(name="xemsaoluu")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_oxemsaoluu(ctx):
    """Thống kê tổng số file, dung lượng, bản gần nhất của hệ thống backup."""
    st = total_backup_stats_v16()
    mb = st["bytes"] / (1024*1024) if st["bytes"] else 0.0
    latest = os.path.basename(st["latest"]) if st["latest"] else "—"
    msg = (f"**Thống kê backup**\n"
           f"- Số file: **{st['files']}**\n"
           f"- Dung lượng: **{mb:.2f} MB**\n"
           f"- Gần nhất: `{latest}`")
    await ctx.reply(msg, mention_author=False)


@bot.command(name="batanh")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_batanh(ctx, mode: str = None):
    """
    Bật/tắt hiển thị ảnh toàn hệ thống.
    - obatanh on  : BẬT ảnh
    - obatanh off : TẮT ảnh
    - obatanh     : Xem trạng thái hiện tại
    """
    data = load_data()
    cfg = _get_cfg(data)

    if mode is None:
        status = "BẬT" if cfg.get("images_enabled", True) else "TẮT"
        await ctx.reply(f"Hiển thị ảnh hiện tại: {status}", mention_author=False)
        return

    m = (mode or "").strip().lower()
    if m in ("on","bật","bat","enable","enabled","true","1"):
        cfg["images_enabled"] = True
        save_data(data)
        await ctx.reply("✅ Đã BẬT hiển thị ảnh.", mention_author=False)
        return
    if m in ("off","tắt","tat","disable","disabled","false","0"):
        cfg["images_enabled"] = False
        save_data(data)
        await ctx.reply("✅ Đã TẮT hiển thị ảnh.", mention_author=False)
        return

    await ctx.reply("Dùng: `obatanh on` hoặc `obatanh off` (hoặc bỏ trống để xem trạng thái).", mention_author=False)




@bot.command(name="phuchoi")
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_phuchoi(ctx, filename: str = None):
    """Khôi phục dữ liệu từ backup gần nhất hoặc theo tên file trong 'backups/'."""
    data = load_data()
    try:
        snapshot_data_v16(data, tag="before-restore", subkey="before_restore")
    except Exception:
        pass

    BACKUP_DIR = os.path.join("backups")
    path = None
    if filename:
        cand = os.path.join(BACKUP_DIR, filename)
        if os.path.isfile(cand):
            path = cand
    else:
        recents = list_recent_backups_v16(limit=1)
        if recents:
            _, _, path = recents[0]

    if not path or not os.path.isfile(path):
        await ctx.reply("Không tìm thấy file backup phù hợp.", mention_author=False)
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            restored = json.load(f)
        save_data(restored)
        await ctx.reply(f"✅ Đã khôi phục dữ liệu từ: `{os.path.basename(path)}`", mention_author=False)
    except Exception as e:
        await ctx.reply(f"Khôi phục thất bại: {e}", mention_author=False)


@bot.command(name="resetdata")
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_resetdata(ctx):
    """Reset toàn bộ dữ liệu người chơi; giữ lại cấu hình kênh và config ảnh."""
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

    save_data(new_data)
    await ctx.reply("✅ Đã reset toàn bộ dữ liệu (giữ cấu hình kênh & thiết lập ảnh).", mention_author=False)


@bot.command(name="resetuser")
@owner_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_resetuser(ctx, member: discord.Member):
    """Reset dữ liệu của 1 người chơi (xóa record user)."""
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
        await ctx.reply(f"✅ Đã reset dữ liệu người chơi: `{member.display_name}`.", mention_author=False)
    else:
        await ctx.reply(f"Người chơi `{member.display_name}` chưa có dữ liệu.", mention_author=False)


# ===== Helpers: chuẩn hoá & truy xuất dữ liệu người chơi (dùng ngan_phi / rungs) =====

def _get_user_ref(data: dict, member: discord.Member):
    """
    Trả về (user_dict, path_info) – tự tìm user trong các nhánh thường gặp:
      1) data["users"][uid]
      2) data["guilds"][gid]["users"][uid]
      3) data["players"][uid]
    Nếu chưa có, sẽ khởi tạo ở data["users"][uid].
    """
    uid = str(member.id)
    gid = str(getattr(getattr(member, "guild", None), "id", None)) if getattr(member, "guild", None) else None

    # 1) Global users
    users = data.setdefault("users", {})
    if uid in users:
        return users[uid], "users"

    # 2) Per-guild users
    if gid and "guilds" in data and gid in data["guilds"]:
        g = data["guilds"][gid]
        if "users" in g and uid in g["users"]:
            return g["users"][uid], f"guilds[{gid}].users"

    # 3) players
    if "players" in data and uid in data["players"]:
        return data["players"][uid], "players"

    # Mặc định tạo mới ở global users
    u = users.setdefault(uid, {})
    return u, "users (new)"


def get_balance(u: dict) -> int:
    """
    Đọc số dư tiền – CHUẨN của bạn là 'ngan_phi'.
    Hỗ trợ tương thích ngược 'ngan_phieu' nếu còn sót.
    """
    return int(u.get("ngan_phi", u.get("ngan_phieu", 0)))


def set_balance(u: dict, value: int) -> None:
    """
    Ghi số dư về khoá CHUẨN 'ngan_phi' và bỏ alias cũ nếu có.
    """
    u["ngan_phi"] = int(value)
    if "ngan_phieu" in u:
        u.pop("ngan_phieu", None)


def ensure_rungs(u: dict) -> dict:
    """
    Đảm bảo luôn có dict rương theo chuẩn 'rungs' với đủ D/C/B/A/S.
    (Nếu còn 'ruong' kiểu cũ sẽ gộp về 'rungs').
    """
    # Di trú từ 'ruong' cũ nếu có
    legacy = u.pop("ruong", None)
    r = u.setdefault("rungs", {})
    if isinstance(legacy, dict):
        for k, v in legacy.items():
            if isinstance(v, int) and k in ("D","C","B","A","S"):
                r[k] = r.get(k, 0) + v

    # Bổ sung khoá còn thiếu
    for k in ("D","C","B","A","S"):
        r.setdefault(k, 0)
    return r


# ===== LỆNH OWNER: CỘNG TIỀN / CẤP RƯƠNG / CHẨN ĐOÁN =====

@bot.command(name="addtien")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_addtien(ctx, member: discord.Member, so: str):
    """Cộng Ngân Phiếu cho 1 người chơi (chuẩn: 'ngan_phi')."""
    try:
        # Cho phép nhập 1,000,000 hoặc 1000000 đều hợp lệ
        amount = int(str(so).replace(",", "").strip())
        if amount <= 0:
            raise ValueError()
    except Exception:
        await ctx.reply("⚠️ Số lượng không hợp lệ. Ví dụ: `oaddtien @user 1,000,000`.", mention_author=False)
        return

    data = load_data()

    u, path = _get_user_ref(data, member)
    bal = get_balance(u)
    set_balance(u, bal + amount)
    save_data(data)

    # Hàm định dạng tiền có dấu phẩy ngăn cách hàng nghìn
    def fmt(n):
        return f"{n:,}"

    await ctx.reply(
        f"✅ Tính năng thử nghiệm BOT nên cộng `{fmt(amount)}` Ngân Phiếu cho `{member.display_name}` — Tổng: `{fmt(get_balance(u))}`",
        mention_author=False
    )


@bot.command(name="addruong")
@owner_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_addruong(ctx, member: discord.Member, pham: str, so: str):
    """Cấp rương theo phẩm chất (D/C/B/A/S) – chuẩn: 'rungs'."""
    pham = pham.strip().upper()
    if pham not in {"D","C","B","A","S"}:
        await ctx.reply("Phẩm rương không hợp lệ. Dùng: D/C/B/A/S", mention_author=False)
        return

    try:
        amount = int(str(so).replace(",", "").strip())
        if amount <= 0:
            raise ValueError()
    except Exception:
        await ctx.reply("⚠️ Số lượng không hợp lệ. Ví dụ: `oaddruong @user S 3`.", mention_author=False)
        return

    # ⚠️ Giới hạn tối đa 10 rương mỗi lần
    if amount > 10:
        await ctx.reply("⚠️ Bạn chỉ có thể tặng tối đa **10 rương** mỗi lần để tránh nhầm lẫn.", mention_author=False)
        return

    data = load_data()
    u, path = _get_user_ref(data, member)
    r = ensure_rungs(u)
    r[pham] = int(r.get(pham, 0)) + amount
    save_data(data)

    # Định dạng có dấu phẩy ngăn cách nghìn cho đẹp
    def fmt(n):
        return f"{n:,}"

    await ctx.reply(
        f"✅ Đã cấp `{fmt(amount)}` rương **{pham}** cho `{member.display_name}` — Tổng hiện có: `{fmt(r[pham])}`",
        mention_author=False
    )


@bot.command(name="xtien")
@owner_only()
@commands.cooldown(1, 3, commands.BucketType.user)
async def cmd_oxtien(ctx, member: discord.Member):
    """
    Chẩn đoán: đang lưu user ở nhánh nào & các khoá tiền còn sót.
    Dùng khi bạn thấy add tiền nhưng gameplay chưa hiện đúng.
    """
    data = load_data()
    u, path = _get_user_ref(data, member)
    keys = {k: u[k] for k in ("ngan_phi", "ngan_phieu") if k in u}
    rinfo = u.get("rungs", {})
    await ctx.reply(
        f"🧩 Path: **{path}**\n"
        f"💰 Số dư đọc chuẩn: **{get_balance(u)}** (keys: {keys})\n"
        f"🎁 Rương hiện có: {rinfo}",
        mention_author=False
    )





# ===== QUYỀN CHỦ BOT & LỆNH QUẢN TRỊ (v16) KẾT THÚC =====


# ====== ping() Bắt Đầu ======
@bot.command(name="pingg")
async def cmd_opingg(ctx):
    """Đo gateway ping + thời gian gửi tin nhắn (send/edit)."""
    import time
    t0 = time.perf_counter()
    msg = await ctx.send("⏱️ Đang đo...")
    t1 = time.perf_counter()
    gateway_ms = int(bot.latency * 1000)
    send_ms = int((t1 - t0) * 1000)
    await msg.edit(content=f"🏓 Gateway: {gateway_ms} ms • Send/edit: {send_ms} ms")
# ====== ping() Kết Thúc ======




# ====== Lệnh hệ thống: osetbot / obatdau Bắt Đầu ======
# =========================
# SETBOT & KHOÁ KÊNH (MỚI)
# =========================

import discord
from discord.ext import commands
from discord import ui, ButtonStyle, Interaction

# Giữ nguyên 2 decorator gốc nếu bạn đã có
def is_admin():
    def predicate(ctx):
        perms = getattr(getattr(ctx.author, 'guild_permissions', None), 'administrator', False)
        return bool(perms)
    return commands.check(predicate)

def owner_only():
    return commands.is_owner()

# -------------------------
# Lưu/đọc cấu hình kênh an toàn & tương thích ngược
# -------------------------
def _sv_cfg(data, guild_id: int) -> dict:
    """Lấy vùng cấu hình server (tạo nếu chưa có)."""
    root = data.setdefault("server_cfg", {})
    return root.setdefault(str(guild_id), {})

def get_guild_channels(data, guild_id: int) -> set[int]:
    """
    Trả về tập kênh được phép dùng bot trong guild.
    - Ưu tiên đọc danh sách mới: server_cfg[guild_id].bot_channels (list int)
    - Tương thích ngược: nếu trống, thử đọc 'kênh cũ' qua get_guild_channel(data, gid) nếu có.
    """
    cfg = _sv_cfg(data, guild_id)
    lst = cfg.get("bot_channels")
    if isinstance(lst, list) and lst:
        try:
            return {int(x) for x in lst}
        except Exception:
            pass

    # Fallback legacy (nếu dự án của bạn có hàm get_guild_channel cũ)
    legacy = None
    try:
        legacy = get_guild_channel(data, guild_id)  # noqa: F821 (tương thích dự án cũ)
    except Exception:
        legacy = None

    if legacy:
        try:
            return {int(legacy)}
        except Exception:
            return set()
    return set()

def set_guild_channels_only(data, guild_id: int, channel_id: int):
    """Chỉ định DUY NHẤT channel_id là kênh bot."""
    cfg = _sv_cfg(data, guild_id)
    cfg["bot_channels"] = [int(channel_id)]

def add_guild_channel(data, guild_id: int, channel_id: int, max_channels: int = 5) -> bool:
    """Thêm channel_id vào danh sách kênh bot. Trả về True nếu thêm được."""
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
    """Gỡ channel_id khỏi danh sách kênh bot. Trả về True nếu gỡ được."""
    cfg = _sv_cfg(data, guild_id)
    cur = list(get_guild_channels(data, guild_id))
    if int(channel_id) not in cur:
        return False
    cur = [c for c in cur if int(c) != int(channel_id)]
    cfg["bot_channels"] = cur
    return True

# -------------------------
# Bộ lọc kênh toàn cục (chỉ chặn khi là lệnh gameplay của bot)
# -------------------------
# Các lệnh quản trị/tiện ích được phép chạy ở mọi nơi:
ADMIN_WHITELIST = {
    "setbot", "osetbot",
    "lenhquantri", "saoluu", "listbackup", "xemsaoluu",
    "phuchoi", "resetdata", "resetuser",
    "addtien", "addruong",
    "gianlan", "thabong", "phattu",
    "batanh", "pingg",
    "lenh", "olenh"  # trang trợ giúp
}

# Các lệnh gameplay yêu cầu đúng kênh (bạn tùy biến theo dự án):
GAMEPLAY_REQUIRE = {
    "ol", "okho", "onhanvat", "omo", "oban", "omac", "othao", "oxem", "odt", "mo"
}

@bot.check
async def global_channel_check(ctx: commands.Context):
    """
    Chỉ chặn khi:
      - tin nhắn là lệnh hợp lệ của CHÍNH bot này (ctx.command không None), và
      - tên lệnh thuộc nhóm GAMEPLAY_REQUIRE, và
      - kênh hiện tại KHÔNG thuộc danh sách kênh được phép.
    Các trường hợp khác (tin nhắn thường, lệnh của bot khác, lệnh quản trị) đều cho qua.
    """
    # DM luôn cho phép
    if not ctx.guild:
        return True

    # Nếu không nhận diện được là lệnh của bot này → cho qua (không cảnh báo)
    if ctx.command is None:
        return True

    name = ctx.command.name.lower()

    # Lệnh whitelisted (quản trị/tiện ích) → cho qua
    if name in ADMIN_WHITELIST:
        return True

    # Gameplay → kiểm tra kênh
    if name in GAMEPLAY_REQUIRE:
        data = load_data()
        allowed = get_guild_channels(data, ctx.guild.id)
        if not allowed or (ctx.channel.id not in allowed):
            msg = (
                "⚠️ BOT sử dụng tiền tố `o` hoặc `O`.\n"
                "Yêu cầu Admin Discord sử dụng lệnh **`osetbot`** để chỉ định kênh dùng BOT tại server này."
            )
            try:
                await ctx.reply(msg, mention_author=False)
            except Exception:
                await ctx.send(msg)
            return False

    # Còn lại → cho qua
    return True

# -------------------------
# UI `osetbot`: nút bấm thao tác
# -------------------------
class SetBotView(ui.View):
    def __init__(self, bot: commands.Bot, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.bot = bot

    async def _is_admin_or_deny(self, interaction: Interaction) -> bool:
        perms = getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False)
        if not perms:
            try:
                await interaction.response.send_message("❌ Bạn cần quyền **Quản trị viên** để thao tác.", ephemeral=True)
            except Exception:
                pass
            return False
        return True

    @ui.button(label="① Set DUY NHẤT kênh này", style=ButtonStyle.success, emoji="✅")
    async def btn_set_only(self, interaction: Interaction, button: ui.Button):
        if not await self._is_admin_or_deny(interaction):
            return
        data = load_data()
        set_guild_channels_only(data, interaction.guild.id, interaction.channel.id)
        save_data(data)
        await interaction.response.send_message(
            f"✅ Đã **chỉ định duy nhất** kênh {interaction.channel.mention} cho BOT.", ephemeral=True
        )

    @ui.button(label="② Gỡ kênh này", style=ButtonStyle.danger, emoji="🗑️")
    async def btn_unset_here(self, interaction: Interaction, button: ui.Button):
        if not await self._is_admin_or_deny(interaction):
            return
        data = load_data()
        ok = remove_guild_channel(data, interaction.guild.id, interaction.channel.id)
        save_data(data)
        if ok:
            await interaction.response.send_message(
                f"🗑️ Đã gỡ {interaction.channel.mention} khỏi danh sách kênh BOT.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ Kênh {interaction.channel.mention} hiện **không nằm** trong danh sách.", ephemeral=True
            )

    @ui.button(label="③ Thêm kênh phụ (kênh này)", style=ButtonStyle.primary, emoji="➕")
    async def btn_add_here(self, interaction: Interaction, button: ui.Button):
        if not await self._is_admin_or_deny(interaction):
            return
        data = load_data()
        ok = add_guild_channel(data, interaction.guild.id, interaction.channel.id, max_channels=5)
        save_data(data)
        if ok:
            await interaction.response.send_message(
                f"➕ Đã **thêm** {interaction.channel.mention} vào danh sách kênh BOT.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "⚠️ Số lượng kênh đã đạt giới hạn. Hãy gỡ bớt trước khi thêm.",
                ephemeral=True
            )

    @ui.button(label="④ Xem kênh đã set", style=ButtonStyle.secondary, emoji="📋")
    async def btn_list(self, interaction: Interaction, button: ui.Button):
        if not await self._is_admin_or_deny(interaction):
            return
        data = load_data()
        allowed = list(get_guild_channels(data, interaction.guild.id))
        if not allowed:
            await interaction.response.send_message(
                "📋 Chưa có kênh nào được chỉ định. Hãy dùng các nút ① hoặc ③.",
                ephemeral=True
            )
            return
        mentions = []
        for cid in allowed:
            ch = interaction.guild.get_channel(int(cid))
            mentions.append(ch.mention if ch else f"`#{cid}`")
        await interaction.response.send_message(
            "📋 **Danh sách kênh BOT:** " + " • ".join(mentions),
            ephemeral=True
        )

@bot.command(name="setbot", aliases=["osetbot"])
@is_admin()
async def cmd_setbot(ctx: commands.Context):
    """
    Hiển thị UI cấu hình kênh cho BOT:
    ① Set DUY NHẤT kênh này
    ② Gỡ kênh này
    ③ Thêm kênh phụ (kênh này)
    ④ Xem kênh đã set
    """
    view = SetBotView(bot)
    note = (
        "⚠️ BOT sử dụng tiền tố `o` hoặc `O`.\n"
        "Hãy chỉ định 1 kênh riêng (hoặc kênh phụ) để tránh trùng với BOT khác.\n"
        "Nhấn các nút bên dưới để cấu hình nhanh."
    )
    await ctx.send(note, view=view)
# ====== Lệnh hệ thống: osetbot / obatdau Kết Thúc ======




if __name__ == "__main__":
    TOKEN = os.environ.get("TU_TIEN_BOT_TOKEN","")
    if not TOKEN:
        print("Vui lòng đặt biến môi trường TU_TIEN_BOT_TOKEN với token bot của bạn.")
    else:
        ensure_data()
bot.run(TOKEN)





# ==== ẢNH (v18_6): Timeout + attach trễ ====
IMAGE_TIMEOUT_SEC = 2.5

async def _attach_image_later(ctx, message, embed, url, filename):
    """Tải ảnh với timeout rồi edit message để gắn ảnh. Lỗi/timeout -> bỏ qua yên lặng."""
    import asyncio
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

def _should_show_images_for(ctx, tag: str) -> bool:
    """Tôn trọng cờ obatanh on/off."""
    try:
        data = load_data()
        conf = data.get("config", {})
        if not conf.get("images_enabled", True):
            return False
    except Exception:
        return True
    return True
# ==== Hết helper ảnh ====


from discord.ui import View, Button
