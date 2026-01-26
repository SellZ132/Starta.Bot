import discord
from discord.ext import commands
import datetime
import json
import os
import requests
from keep_alive import keep_alive

# --- ส่วนตั้งค่าบอท ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 

activity = discord.Game(name="จับผิดคนอู้งาน 🕵️")
bot = commands.Bot(command_prefix='!', intents=intents, activity=activity)

DATA_FILE = "time_data.json"
voice_start = {}
voice_total = {}

# --- ฟังก์ชันระบบจับเวลา ---
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

# --- ฟังก์ชันแกะซอง TrueMoney (ฉบับสมบูรณ์) ---
def redeem_gift(url, phone_number):
    try:
        if "v=" in url:
            voucher_id = url.split("v=")[1].split("&")[0].strip()
        else:
            return {"status": "error", "message": "❌ ลิ้งก์ไม่ถูกต้อง (ต้องมี v=...)"}

        api_url = f"https://gift.truemoney.com/campaign/vouchers/{voucher_id}/redeem"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Content-Type": "application/json",
            "Origin": "https://gift.truemoney.com",
            "Referer": "https://gift.truemoney.com/"
        }
        payload = {"mobile": phone_number, "voucher_hash": voucher_id}
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=5)
        
        if response.status_code != 200:
            return {"status": "error", "message": f"❌ TrueMoney ปฏิเสธ (Code {response.status_code})"}

        result = response.json()
        if result['status']['code'] == 'SUCCESS':
            amount = result['data']['my_ticket']['amount_baht']
            sender = result['data']['owner_profile']['full_name']
            return {"status": "success", "amount": amount, "sender": sender}
        else:
            return {"status": "error", "message": f"❌ {result['status']['message']}"}
    except Exception as e:
        return {"status": "error", "message": "❌ ระบบขัดข้อง"}

# --- Commands ---
@bot.event
async def on_ready():
    load_data()
    print(f'✅ บอท {bot.user} พร้อมลุย! (จับเวลา + เติมเงิน)')

# (รวมคำสั่ง !time และ !tops ไว้ที่นี่ตามปกติ...)

@bot.command()
async def topup(ctx, link: str):
    await ctx.reply("⏳ กำลังตรวจสอบซอง... รอแป๊บ")
    
    # ดึงเบอร์จาก Render Environment
    my_phone = os.getenv('PHONE') 
    
    if not my_phone:
        await ctx.reply("⚠️ เจ้าของบอทยังไม่ได้ตั้งค่าเบอร์รับเงิน!")
        return

    result = redeem_gift(link, my_phone)
    
    if result['status'] == 'success':
        amount = float(result['amount'])
        await ctx.reply(f"✅ **เติมเงินสำเร็จ!**\n💰 ได้รับ: `{amount}` บาท จากคุณ {result['sender']}")
        
        # แจกยศ VIP อัตโนมัติถ้าเติมเงิน (ตัวอย่าง)
        role = discord.utils.get(ctx.guild.roles, name="VIP")
        if role: await ctx.author.add_roles(role)
    else:
        await ctx.reply(result['message'])

# --- เริ่มระบบ ---
keep_alive()
token = os.getenv('TOKEN') 
bot.run(token)