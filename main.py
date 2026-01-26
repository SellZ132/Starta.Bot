import discord
from discord.ext import commands
import datetime
import json
import os
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
d@bot.command()
async def topup(ctx, link: str):
    # 1. ตรวจสอบเบื้องต้นว่าเป็นลิ้งก์ซองไหม
    if "gift.truemoney.com" not in link:
        await ctx.reply("❌ ลิ้งก์ไม่ถูกต้องครับ")
        return

    # 2. ตั้งค่าไอดีของคุณ (เอาไอดีของคุณใส่ตรงนี้)
    OWNER_ID = 1039199055923904562  # <--- ⚠️ เปลี่ยนเป็น ID Discord ของน้องจริงๆ

    try:
        # 3. ดึงข้อมูล User ของเรา
        owner = await bot.fetch_user(OWNER_ID)
        
        # 4. ส่งข้อความหาเราใน DM
        embed = discord.Embed(title="💰 มีคนส่งซองของขวัญมาครับ!", color=0x00ff00)
        embed.add_field(name="จากคุณ", value=f"{ctx.author.name} (ID: {ctx.author.id})", inline=False)
        embed.add_field(name="ลิ้งก์ซอง", value=link, inline=False)
        embed.set_footer(text="รีบกดรับก่อนซองหมดอายุนะพี่ชาย!")
        
        await owner.send(embed=embed)
        await owner.send(link) # ส่งลิ้งก์แยกอีกรอบเพื่อให้กดง่ายๆ ในมือถือ

        # 5. ลบข้อความต้นฉบับในห้องแชท (เพื่อไม่ให้คนอื่นเห็นลิ้งก์)
        await ctx.message.delete()

        # 6. ตอบกลับลูกค้าในห้องแชท
        await ctx.send(f"✅ คุณ {ctx.author.mention} ส่งซองสำเร็จแล้ว! โปรดรอเจ้าของตรวจสอบและดำเนินการครับ")

    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("❌ บอทไม่สามารถส่ง DM หาเจ้าของได้ (อาจจะไม่ได้เปิด DM ไว้)")

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