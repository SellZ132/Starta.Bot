import discord
from discord.ext import commands
import datetime
import json
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold # เพิ่มอันนี้เข้ามา
import asyncio
from keep_alive import keep_alive

# --- 🧠 ตั้งค่า Gemini AI ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    # ถ้าพัง บรรทัดนี้จะไปโผล่ใน Logs ของ Render
    print("❌ ERROR: หากุญแจ GEMINI_API_KEY ไม่เจอในตู้เซฟ Render!")
    model = None 
else:
    genai.configure(api_key=GEMINI_KEY)
    # นิยาม model ให้ชัดเจน
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction="นายคือ 'น้อนบอท' บอทปากหมาสุดตึง ตอบกวนๆ ด่ามาด่ากลับ ใช้คำหยาบได้",
        safety_settings={
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
        }
    )

# --- 💬 ส่วน on_message (ฉบับนักสืบหา Error) ---
@bot.event
async def on_message(message):
    if message.author.bot: return

    TARGET_CHANNEL_ID = 1465350210543947971
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        if model is None:
            await message.reply("⚠️ บอสลืมใส่ API Key ให้ผมครับ ผมเลยยังไม่มีสมอง!")
            return

        async with message.channel.typing():
            try:
                # ตรวจสอบ session
                if message.author.id not in chat_sessions:
                    chat_sessions[message.author.id] = model.start_chat(history=[])
                
                # ส่งข้อความ
                response = chat_sessions[message.author.id].send_message(message.content)
                
                # เช็คว่ามีคำตอบกลับมาไหม
                if response and response.candidates and response.candidates[0].content.parts:
                    await message.reply(response.text)
                else:
                    await message.reply("😶 เอ่อ... เหมือนคำนี้จะโดน Google บล็อกว่ะพี่ ลองคำอื่นดิ๊!")
                    
            except Exception as e:
                # --- จุดสำคัญ: ให้บอทบอกเลยว่า Error คืออะไร ---
                error_msg = str(e)
                print(f"🔥 Gemini Error: {error_msg}") 
                
                if "401" in error_msg or "API_KEY_INVALID" in error_msg:
                    await message.reply("🔑 **[API Error]** พี่ชาย! API Key มันใช้ไม่ได้ ไปเช็คใน Google AI Studio ด่วน!")
                elif "429" in error_msg:
                    await message.reply("⏳ **[Quota Error]** ใจเย็นพี่ คนพิมพ์เยอะเกิน สมอง Gemini รับไม่ทันแล้ว!")
                else:
                    await message.reply(f"💢 **พังเฉย!** Error คือ: `{error_msg}`")

# --- 🤖 ตั้งค่า Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents, activity=discord.Game(name="เฝ้าห้อง & ด่าคน 🕵️🔥"))

DATA_FILE = "time_data.json"
voice_start = {}
voice_total = {}

# --- 📂 ระบบจัดการข้อมูลเวลา (เหมือนเดิม) ---
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

# --- 💬 ระบบตอบโต้อัตโนมัติ (Gemini สายโหด) ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    TARGET_CHANNEL_ID = 1465350210543947971
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        async with message.channel.typing():
            try:
                if message.author.id not in chat_sessions:
                    chat_sessions[message.author.id] = model.start_chat(history=[])
                
                # ส่งข้อความไปประมวลผล
                response = chat_sessions[message.author.id].send_message(message.content)
                
                # เช็คว่ามีคำตอบกลับมาไหม (เผื่อโดนระบบใหญ่ของ Google บล็อกจริงๆ)
                if response.parts:
                    await message.reply(response.text)
                else:
                    await message.reply("โหพี่ คำนี้มันแรงจนกูไปไม่เป็นเลยว่ะ (โดนระบบใหญ่ดีด) ลองคำอื่นดิ๊!")

            except Exception as e:
                print(f"Gemini Error: {e}")
                # ถ้าพังบ่อยๆ ให้ลองเช็ค Logs ใน Render นะครับ
                await message.reply("สมองช็อตแป๊บ... พิมพ์ใหม่ดิ๊เมื่อกี้มึนๆ")

    await bot.process_commands(message)

# --- ⏱️ คำสั่งเช็คเวลา ---
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

# --- 🧧 คำสั่ง !topup ---
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
        embed.add_field(name="จาก", value=f"{ctx.author.name}")
        embed.add_field(name="ลิ้งก์ซอง", value=link)
        await owner.send(embed=embed)
        await owner.send(link)
        await ctx.message.delete()
        await ctx.send(f"✅ คุณ {ctx.author.mention} ส่งซองเรียบร้อย! รอเจ้าของเช็คครับ")
    except Exception as e:
        await ctx.reply("❌ บอทส่ง DM หาบอสไม่ได้ว่ะพี่")

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
    print(f'✅ บอท {bot.user} ออนไลน์พร้อมสมอง Gemini สายโหด!')

keep_alive()
TOKEN = os.getenv('TOKEN')
if TOKEN:
    bot.run(TOKEN)