import discord
from discord.ext import commands
import datetime
import json
import os
import google.generativeai as genai
import asyncio
from keep_alive import keep_alive

# --- 🧠 ตั้งค่า Gemini AI ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction="นายคือ 'น้อนบอท' บอทสุดตึงประจำเซิร์ฟเวอร์ นิสัยกวนๆ ขี้เล่น ตอบสั้นๆ กระชับแบบวัยรุ่นไทย ชอบใช้คำว่า ตึง, จัดไปพี่ชาย, นอยด์อ่ะ"
    )
chat_sessions = {}

# --- 🤖 ตั้งค่า Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents, activity=discord.Game(name="เฝ้าห้อง & คุยกับ Gemini 🕵️✨"))

DATA_FILE = "time_data.json"
voice_start = {}
voice_total = {}

# --- 📂 ระบบจัดการข้อมูลเวลา ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for user_id, seconds in data.items():
                    voice_total[int(user_id)] = datetime.timedelta(seconds=seconds)
            print("📂 โหลดข้อมูลเวลาเก่าเรียบร้อย!")
        except Exception as e:
            print(f"⚠️ โหลดข้อมูลพลาด: {e}")

def save_data():
    try:
        data = {str(k): v.total_seconds() for k, v in voice_total.items()}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"⚠️ บันทึกข้อมูลพลาด: {e}")

# --- 💬 ระบบตอบโต้อัตโนมัติ (Gemini) ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # ตอบเฉพาะห้องที่กำหนด และไม่ใช่คำสั่ง !
    TARGET_CHANNEL_ID = 1465350210543947971
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        async with message.channel.typing():
            try:
                if message.author.id not in chat_sessions:
                    chat_sessions[message.author.id] = model.start_chat(history=[])
                
                # แกล้งคิดนิดนึงตามความยาวข้อความ
                wait_time = min(len(message.content) * 0.1, 3)
                await asyncio.sleep(wait_time)
                
                response = chat_sessions[message.author.id].send_message(message.content)
                await message.reply(response.text)
            except Exception as e:
                print(f"Gemini Error: {e}")
                await message.reply("สมองตึงจัด... พิมพ์ใหม่ดิพี่ชายเมื่อกี้ประมวลผลไม่ทัน")

    await bot.process_commands(message)

# --- ⏱️ คำสั่ง !time และ !tops ---
@bot.command()
async def time(ctx, member: discord.Member = None):
    target = member or ctx.author
    total = voice_total.get(target.id, datetime.timedelta())
    if target.id in voice_start:
        total += (datetime.datetime.now() - voice_start[target.id])
    await ctx.reply(f"⏱️ **{target.name}** ออนไลน์รวม: **{str(total).split('.')[0]}**")

@bot.command()
async def tops(ctx):
    final_data = voice_total.copy()
    now = datetime.datetime.now()
    for uid, start in voice_start.items():
        final_data[uid] = final_data.get(uid, datetime.timedelta()) + (now - start)
    
    if not final_data:
        await ctx.reply("❌ ยังไม่มีข้อมูลใครเลยครับ")
        return

    sorted_data = sorted(final_data.items(), key=lambda x: x[1].total_seconds(), reverse=True)[:5]
    embed = discord.Embed(title="🏆 5 อันดับ เทพเจ้าคนว่างงาน", color=0xFFD700)
    for i, (uid, val) in enumerate(sorted_data):
        m = ctx.guild.get_member(uid)
        name = m.name if m else f"Unknown ({uid})"
        embed.add_field(name=f"#{i+1} {name}", value=str(val).split('.')[0], inline=False)
    await ctx.send(embed=embed)

# --- 🧧 คำสั่ง !topup (DM Forward) ---
@bot.command()
async def topup(ctx, link: str):
    if "gift.truemoney.com" not in link:
        await ctx.reply("❌ ลิ้งก์ไม่ถูกต้องครับ")
        return

    owner_id_env = os.getenv('OWNER_ID')
    if not owner_id_env:
        await ctx.reply("⚠️ ยังไม่ได้ตั้ง OWNER_ID ใน Render")
        return

    try:
        owner = await bot.fetch_user(int(owner_id_env))
        
        embed = discord.Embed(title="🧧 มีซองใหม่มาครับ!", color=0x00ff00)
        embed.add_field(name="จาก", value=f"{ctx.author.name} ({ctx.author.id})")
        embed.add_field(name="ลิ้งก์ซอง", value=link)
        
        await owner.send(embed=embed)
        await owner.send(link) # ส่งแยกให้กดง่าย

        await ctx.message.delete()
        await ctx.send(f"✅ คุณ {ctx.author.mention} ส่งซองเรียบร้อย! รอเจ้าของตรวจสอบครับ")
    except Exception as e:
        print(f"DM Error: {e}")
        await ctx.reply("❌ บอทส่ง DM หาเจ้าของไม่ได้ (ลองเช็คว่าบอสเปิด DM หรือยัง)")

# --- 🎙️ Voice Events ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return
    # เข้าห้อง
    if before.channel is None and after.channel is not None:
        voice_start[member.id] = datetime.datetime.now()
    # ออกห้อง
    elif before.channel is not None and after.channel is None:
        if member.id in voice_start:
            start = voice_start.pop(member.id)
            duration = datetime.datetime.now() - start
            if member.id not in voice_total:
                voice_total[member.id] = datetime.timedelta()
            voice_total[member.id] += duration
            save_data()

@bot.event
async def on_ready():
    load_data()
    print(f'✅ บอท {bot.user} ออนไลน์พร้อมสมอง Gemini และระบบจับเวลา!')

# --- รันบอท ---
keep_alive()
TOKEN = os.getenv('TOKEN')
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ ไม่พบ TOKEN ใน Environment Variable!")