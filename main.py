import discord
from discord.ext import commands
import datetime
import json
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import asyncio
from keep_alive import keep_alive

# --- 🧠 ตั้งค่า Gemini AI ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
model = None
chat_sessions = {} # <--- ต้องมีบรรทัดนี้!

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction="นายคือ 'น้อนบอท' บอทปากหมาสุดตึงประจำเซิร์ฟเวอร์ นิสัยกวนๆ ขี้เล่น ตอบกระชับแบบวัยรุ่นไทย ใช้คำหยาบได้เต็มที่ (กู, มึง, ไอ้...) ใครด่ามาด่ากลับให้ตึง!",
        safety_settings={
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
    )

# --- 🤖 ตั้งค่า Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents, activity=discord.Game(name="เฝ้าห้อง & ด่าคน 🕵️🔥"))

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
            print("📂 โหลดข้อมูลเวลาเรียบร้อย!")
        except: pass

def save_data():
    try:
        data = {str(k): v.total_seconds() for k, v in voice_total.items()}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except: pass

# --- 💬 ระบบตอบโต้อัตโนมัติ (Gemini) ---
@bot.event
async def on_message(message):
    if message.author.bot: return

    TARGET_CHANNEL_ID = 1465350210543947971
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        if model is None:
            await message.reply("⚠️ บอส! ลืมใส่ API Key ใน Render หรือเปล่า?")
            return

        async with message.channel.typing():
            try:
                if message.author.id not in chat_sessions:
                    chat_sessions[message.author.id] = model.start_chat(history=[])
                
                await asyncio.sleep(1) # แกล้งคิด
                response = chat_sessions[message.author.id].send_message(message.content)
                await message.reply(response.text)
            except Exception as e:
                print(f"Gemini Error: {e}")
                await message.reply(f"💢 สมองช็อตเพราะ: {e}")

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
        await ctx.reply("❌ ยังไม่มีข้อมูลใครเลย")
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
        await ctx.reply("❌ ลิ้งก์ไม่ถูกต้อง")
        return

    owner_id_env = os.getenv('OWNER_ID')
    if not owner_id_env:
        await ctx.reply("⚠️ ยังไม่ได้ตั้ง OWNER_ID ใน Render")
        return

    try:
        owner = await bot.fetch_user(int(owner_id_env))
        embed = discord.Embed(title="🧧 มีซองใหม่มา!", color=0x00ff00)
        embed.add_field(name="จาก", value=f"{ctx.author.name}")
        embed.add_field(name="ลิ้งก์", value=link)
        await owner.send(embed=embed)
        await owner.send(link)
        await ctx.message.delete()
        await ctx.send(f"✅ คุณ {ctx.author.mention} ส่งซองสำเร็จ! รอเจ้าของเช็คครับ")
    except:
        await ctx.reply("❌ บอทส่ง DM หาบอสไม่ได้")

# --- 🎙️ Voice Events ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return
    if before.channel is None and after.channel is not None:
        voice_start[member.id] = datetime.datetime.now()
    elif before.channel is not None and after.channel is None:
        if member.id in voice_start:
            start = voice_start.pop(member.id)
            duration = datetime.datetime.now() - start
            if member.id not in voice_total: voice_total[member.id] = datetime.timedelta()
            voice_total[member.id] += duration
            save_data()

@bot.event
async def on_ready():
    load_data()
    print(f'✅ บอท {bot.user} ออนไลน์พร้อมด่าคนแล้ว!')

keep_alive()
TOKEN = os.getenv('TOKEN')
if TOKEN:
    bot.run(TOKEN)