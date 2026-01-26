import discord
from discord.ext import commands
import datetime
import json
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import asyncio
from keep_alive import keep_alive

# --- 🧠 ประกาศตัวแปร Global (ห้ามย้ายไปไหน) ---
chat_sessions = {} 
model = None

# --- 🧠 ตั้งค่า Gemini AI ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    
    # ปรับจูน Safety เพื่อให้ด่ากลับได้ตึงๆ
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest", 
        system_instruction="นายคือ 'น้อนบอท' บอทสุดตึงประจำเซิร์ฟเวอร์ดิสคอร์ด ปากหมา กวนตีน ใช้คำหยาบได้ (กู, มึง) ใครด่ามาด่ากลับให้ยับ อย่าเป็นเด็กดีจนน่าเบื่อ",
        safety_settings=safety_settings
    )

# --- 🤖 ตั้งค่า Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents, activity=discord.Game(name="เฝ้าห้องเสียง & ด่าคน 🕵️🔥"))

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
        except Exception as e:
            print(f"⚠️ โหลดข้อมูลพลาด: {e}")

def save_data():
    try:
        data = {str(k): v.total_seconds() for k, v in voice_total.items()}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"⚠️ บันทึกข้อมูลพลาด: {e}")

# --- 💬 ระบบตอบโต้อัตโนมัติ (Gemini สายโหด) ---
@bot.event
async def on_message(message):
    if message.author.bot: return

    # ตอบเฉพาะห้องนี้: 1465350210543947971
    TARGET_CHANNEL_ID = 1465350210543947971
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        if model is None:
            await message.reply("⚠️ ยังไม่ได้ตั้งค่า API Key หรือโมเดลพังครับบอส!")
            return

        async with message.channel.typing():
            try:
                # ตรวจสอบประวัติการคุย
                if message.author.id not in chat_sessions:
                    chat_sessions[message.author.id] = model.start_chat(history=[])
                
                # ส่งข้อความไปด่าคืน
                response = chat_sessions[message.author.id].send_message(message.content)
                
                if response.parts:
                    await message.reply(response.text)
                else:
                    await message.reply("แรงเกิน! คำนี้ Google บล็อกกูว่ะพี่ ลองใหม่ดิ๊")

            except Exception as e:
                print(f"🔥 Gemini Error: {e}")
                # ถ้า Error 404 อีก ให้แจ้งบอสตรงๆ
                await message.reply(f"💢 สมองช็อตว่ะ Error: {e}")

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

# --- 🧧 คำสั่ง !topup ---
@bot.command()
async def topup(ctx, link: str):
    if "gift.truemoney.com" not in link:
        await ctx.reply("❌ ลิ้งก์ไม่ถูกต้อง")
        return
    owner_id = os.getenv('OWNER_ID')
    if not owner_id: return
    try:
        owner = await bot.fetch_user(int(owner_id))
        await owner.send(f"🧧 **ซองใหม่จาก {ctx.author.name}!**\n{link}")
        await ctx.message.delete()
        await ctx.send(f"✅ คุณ {ctx.author.mention} ส่งซองเรียบร้อย! รอเจ้าของเช็คครับ")
    except:
        await ctx.reply("❌ ส่ง DM หาบอสไม่ติดว่ะ")

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
    print(f'✅ บอท {bot.user} พร้อมออกรบ!')

keep_alive()
TOKEN = os.getenv('TOKEN')
if TOKEN:
    bot.run(TOKEN)