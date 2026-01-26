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

activity = discord.Game(name="รอส่งซองให้บอส 🧧")
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
    data = {str(k): v.total_seconds() for k, v in voice_total.items()}
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- คำสั่ง !topup (ระบบส่งลิ้งก์เข้า DM) ---
@bot.command()
async def topup(ctx, link: str):
    if "gift.truemoney.com" not in link:
        await ctx.reply("❌ ลิ้งก์ไม่ถูกต้องครับ")
        return

    # ดึง ID จากตู้เซฟ (Environment Variable)
    # ต้องครอบด้วย int() เพราะข้อมูลจากตู้เซฟจะเป็นข้อความเสมอ
    owner_id_env = os.getenv('OWNER_ID')
    
    if not owner_id_env:
        await ctx.reply("⚠️ เจ้าของบอทยังไม่ได้ตั้งค่า OWNER_ID ในตู้เซฟ!")
        return
    
    owner_id = int(owner_id_env)

    try:
        owner = await bot.fetch_user(owner_id)
        
        # ส่งข้อความหาเราใน DM
        embed = discord.Embed(title="💰 มีคนส่งซองของขวัญมาครับ!", color=0x00ff00)
        embed.add_field(name="จาก", value=f"{ctx.author.name} (ID: {ctx.author.id})", inline=False)
        embed.add_field(name="ลิ้งก์ซอง", value=link, inline=False)
        embed.set_footer(text="รีบกดรับก่อนซองหมดอายุนะพี่ชาย!")
        
        await owner.send(embed=embed)
        await owner.send(link) # ส่งแยกเพื่อให้กดง่าย

        # ลบข้อความต้นฉบับ
        await ctx.message.delete()
        await ctx.send(f"✅ คุณ {ctx.author.mention} ส่งซองสำเร็จแล้ว! รอเจ้าของตรวจสอบครับ")

    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("❌ บอทไม่สามารถส่ง DM หาเจ้าของได้ (โปรดเช็คการตั้งค่า DM)")

# --- Events ---
@bot.event
async def on_ready():
    load_data()
    print(f'✅ บอท {bot.user} ตื่นแล้ว! (โหมด DM Forwarding)')

# --- ระบบจับเวลา (ใส่ต่อจากนี้ได้เลย) ---
# [เพิ่มคำสั่ง !time และ !tops ของเดิมน้องลงไปตรงนี้ได้เลยครับ]

keep_alive()
token = os.getenv('TOKEN') 
bot.run(token)