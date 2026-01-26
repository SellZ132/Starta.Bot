import discord
from discord.ext import commands
import datetime
import json
import os
import requests  # <--- ตัวใหม่สำหรับระบบเติมเงิน
from keep_alive import keep_alive

# --- ส่วนตั้งค่าบอท ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 

# กำหนดให้บอทมีสถานะตั้งแต่วินาทีแรกที่เปิด
activity = discord.Game(name="จับผิดคนอู้งาน 🕵️")
bot = commands.Bot(command_prefix='!', intents=intents, activity=activity)

DATA_FILE = "time_data.json"
voice_start = {}
voice_total = {}

# --- ฟังก์ชันโหลด/บันทึก (ระบบจับเวลา) ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            for user_id, seconds in data.items():
                voice_total[int(user_id)] = datetime.timedelta(seconds=seconds)
        print("📂 โหลดข้อมูลเวลาเก่าเรียบร้อย!")

def save_data():
    data = {}
    for user_id, time_value in voice_total.items():
        data[str(user_id)] = time_value.total_seconds()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    print("💾 บันทึกข้อมูลลงไฟล์แล้ว")

# --- ฟังก์ชันแกะซอง TrueMoney (ระบบเติมเงิน) ---
def redeem_gift(url, phone_number):
    try:
        if "v=" in url:
            voucher_id = url.split("v=")[1]
        else:
            return {"status": "error", "message": "❌ ลิ้งก์ไม่ถูกต้อง (ต้องมี v=...)"}

        api_url = f"https://gift.truemoney.com/campaign/vouchers/{voucher_id}/redeem"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }
        payload = {
            "mobile": phone_number,
            "voucher_hash": voucher_id
        }
        
        response = requests.post(api_url, headers=headers, json=payload)
        result = response.json()
        
        if result['status']['code'] == 'SUCCESS':
            amount = result['data']['my_ticket']['amount_baht']
            sender = result['data']['owner_profile']['full_name']
            return {"status": "success", "amount": amount, "sender": sender}
        else:
            return {"status": "error", "message": f"❌ เติมไม่เข้า: {result['status']['message']}"}

    except Exception as e:
        return {"status": "error", "message": f"❌ ระบบขัดข้อง: {str(e)}"}

# --- ตอนบอทเปิด (on_ready) ---
@bot.event
async def on_ready():
    load_data()
    print(f'✅ บอท {bot.user} ตื่นแล้ว! (ระบบจับเวลา + เติมเงิน พร้อม!)')
    
    # เช็คคนตกค้างในห้อง (จับเวลา)
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            for member in channel.members:
                if not member.bot and member.id not in voice_start:
                    voice_start[member.id] = datetime.datetime.now()
                    print(f"🔄 เจอคุณ {member.name} ค้างในสาย -> เริ่มนับเวลาให้ใหม่")

# --- ตอนคนเข้า/ออก (on_voice_state_update) ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return

    # เข้าห้อง
    if before.channel is None and after.channel is not None:
        voice_start[member.id] = datetime.datetime.now()
        print(f"🟢 {member.name} เข้าสาย")

    # ออกห้อง
    elif before.channel is not None and after.channel is None:
        if member.id in voice_start:
            start = voice_start.pop(member.id)
            end = datetime.datetime.now()
            duration = end - start

            if member.id not in voice_total:
                voice_total[member.id] = datetime.timedelta()
            
            voice_total[member.id] += duration
            save_data()
            print(f"💾 {member.name} ออกสาย (เก็บเวลาเพิ่ม {duration})")

# --- คำสั่ง !time ---
@bot.command()
async def time(ctx, member: discord.Member = None):
    if member is None: member = ctx.author
    user_id = member.id
    total = datetime.timedelta()
    if user_id in voice_total:
        total += voice_total[user_id]
    if user_id in voice_start:
        current = datetime.datetime.now() - voice_start[user_id]
        total += current
    total_str = str(total).split('.')[0]
    await ctx.reply(f"⏱️ คุณ {member.name} ออนไลน์รวม: **{total_str}**")

# --- คำสั่ง !tops ---
@bot.command()
async def tops(ctx):
    if not voice_total and not voice_start:
        await ctx.reply("❌ ยังไม่มีข้อมูลใครเลยครับ")
        return
    final_data = voice_total.copy()
    now = datetime.datetime.now()
    for user_id, start_time in voice_start.items():
        current = now - start_time
        if user_id in final_data:
            final_data[user_id] += current
        else:
            final_data[user_id] = current
    sorted_data = sorted(final_data.items(), key=lambda x: x[1].total_seconds(), reverse=True)
    embed = discord.Embed(title="🏆 5 อันดับ เทพเจ้าคนว่างงาน", color=0xFFD700)
    count = 0
    for user_id, time_val in sorted_data:
        member = ctx.guild.get_member(user_id)
        if member:
            time_str = str(time_val).split('.')[0]
            embed.add_field(name=f"#{count+1} {member.name}", value=f"⏱️ {time_str}", inline=False)
            count += 1
            if count >= 5: break
    await ctx.send(embed=embed)

# --- ฟังก์ชันแกะซอง TrueMoney (ฉบับอัปเกรด Debug) ---
def redeem_gift(url, phone_number):
    try:
        # 1. หา Voucher ID
        if "v=" in url:
            voucher_id = url.split("v=")[1]
        else:
            return {"status": "error", "message": "❌ ลิ้งก์ไม่ถูกต้อง (ต้องมี v=...)"}

        # 2. ตั้งค่า Header ให้เนียนขึ้น (เหมือนคนใช้ Chrome)
        api_url = f"https://gift.truemoney.com/campaign/vouchers/{voucher_id}/redeem"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Content-Type": "application/json",
            "Origin": "https://gift.truemoney.com",
            "Referer": "https://gift.truemoney.com/"
        }
        payload = {
            "mobile": phone_number,
            "voucher_hash": voucher_id
        }
        
        # 3. ยิงไปหา TrueMoney
        print(f"กำลังยิงไปที่: {api_url}") # Debug 1
        response = requests.post(api_url, headers=headers, json=payload, timeout=5)
        
        # --- เช็คผลลัพธ์แบบละเอียด ---
        print(f"Status Code: {response.status_code}") # Debug 2
        
        # ถ้า Error ไม่ใช่ 200 (เช่น 403 Forbidden)
        if response.status_code != 200:
            print(f"Response Text: {response.text}") # Debug 3: ปริ้นท์สิ่งที่ TrueMoney ตอบกลับมา
            return {"status": "error", "message": f"❌ TrueMoney ปฏิเสธ ({response.status_code}): บอทอาจจะโดนบล็อก IP"}

        # ถ้าผ่าน ค่อยแปลงเป็น JSON
        try:
            result = response.json()
        except Exception as e:
            print(f"JSON Error: {response.text}") # ดูว่าส่งอะไรมาทำไมแปลงไม่ได้
            return {"status": "error", "message": "❌ อ่านข้อมูลไม่ได้ (TrueMoney ส่ง HTML มา)"}
        
        if result['status']['code'] == 'SUCCESS':
            amount = result['data']['my_ticket']['amount_baht']
            sender = result['data']['owner_profile']['full_name']
            return {"status": "success", "amount": amount, "sender": sender}
        else:
            return {"status": "error", "message": f"❌ เติมไม่เข้า: {result['status']['message']}"}

    except Exception as e:
        print(f"System Error: {str(e)}")
        return {"status": "error", "message": f"❌ ระบบขัดข้อง: {str(e)}"}

# --- เริ่มระบบ ---
keep_alive()
token = os.getenv('TOKEN') 
bot.run(token)