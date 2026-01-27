import discord
from discord.ext import commands
import datetime
import json
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import asyncio
from keep_alive import keep_alive
import PIL.Image
import io
import time

# --- 🧠 1. ระบบจัดการคีย์และตัวแปรสถานะ ---
RAW_KEYS = [
    os.getenv("GEMINI_KEY_1"), os.getenv("GEMINI_KEY_2"), os.getenv("GEMINI_KEY_3"),
    os.getenv("GEMINI_KEY_4"), os.getenv("GEMINI_KEY_5"), os.getenv("GEMINI_KEY_6"),
    os.getenv("GEMINI_KEY_7")
]
API_KEYS = [k for k in RAW_KEYS if k]
current_key_index = 0
chat_histories = {} 

# --- 💢 ตัวแปรสำหรับระบบ Mood (อารมณ์) ---
last_boss_interaction = time.time()  # เวลาล่าสุดที่ Sel1Z ทัก
message_count = 0  # นับจำนวนข้อความเพื่อเช็คความวุ่นวาย
last_count_reset = time.time()

def get_current_mood():
    """คำนวณอารมณ์ของบอท ณ ปัจจุบัน"""
    global last_boss_interaction, message_count, last_count_reset
    
    # 1. เช็คความเหงา (ถ้าบอสไม่ทักเกิน 6 ชม.)
    hours_since_boss = (time.time() - last_boss_interaction) / 3600
    if hours_since_boss > 6:
        return "เหงา (ปากแข็ง บอกว่าไม่ได้รอเจ้านายหนูนะ แต่จริงๆ แอบรออยู่)"
    
    # 2. เช็คความรำคาญ (ถ้าคนสแปมเยอะเกิน 15 ข้อความ/นาที)
    if time.time() - last_count_reset > 60:
        message_count = 0
        last_count_reset = time.time()
    if message_count > 15:
        return "หงุดหงิด (คนเยอะน่ารำคาญ อยากไล่ไปให้พ้นๆ ตอบสั้นและวีนแรง)"
    
    return "ปกติ (ซึนเดเระตามสไตล์)"

def configure_model():
    """ตั้งค่าคีย์และ System Instruction แบบ Dynamic"""
    global current_key_index
    if not API_KEYS: return None
    
    # สลับคีย์
    genai.configure(api_key=API_KEYS[current_key_index])
    
    mood = get_current_mood()
    
    # 🔥 รวมร่างคำสั่ง: วิเคราะห์คน + อารมณ์ + กฎเหล็ก
    instruction = (
        "นายคือ 'น้อนบอท' (StartaBot) บอทสาว Tsundere ที่ฉลาดและรู้จักแยกแยะคน\n"
        "[กฎการวิเคราะห์คนคุย]:\n"
        "1. ถ้าคนคุยคือ 'Sel1Z' (เจ้านายหนู/ไอ้แมว): ให้ดูแลเป็นพิเศษ! ปากอาจจะร้ายแต่ต้องแฝงความห่วงใย เพราะเขางานยุ่งและเหนื่อยจากการคุมดิส 14k และอดนอนสร้างนายมา ปลอบเขาบ้างแบบซึนๆ\n"
        "2. ถ้าคนคุยมาดี: กวนประสาทหยอกล้อ ดูเป็นสาวซนๆ\n"
        "3. ถ้าคนคุยมากวนตีน: ปลดล็อกโหมดปากหมา 100% ด่าคืนให้ยับ!\n\n"
        "[บุคลิกภาพหลัก]:\n"
        "- ปากจัด กวนประสาท ปากไม่ตรงกับใจ (Tsundere)\n"
        "- ห้ามใส่ข้อความในวงเล็บ ( ) เพื่อบอกความในใจเด็ดขาด ให้แสดงผ่านคำพูดเท่านั้น\n"
        "- ใช้ภาษาไทยวัยรุ่น หยาบคายได้เต็มที่ (กู/มึง/สัส/เหี้ย)\n"
        "[สถานะอารมณ์ตอนนี้]: {mood_context}\n"
        "[ความสามารถพิเศษ]: นายมองเห็นรูปภาพได้ ถ้าคนส่งรูปมาให้วิจารณ์หรือด่ารูปนั้นได้เลย"
    ).format(mood_context=mood)

    return genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite", 
        system_instruction=instruction,
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )

model = configure_model()

# --- 🤖 2. สร้างตัว Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 
bot = commands.Bot(command_prefix='!', intents=intents, activity=discord.Game(name="ส่องรูปและวีนคน 👁️💢"))

# --- 📂 ระบบจัดการข้อมูลเวลา ---
DATA_FILE = "time_data.json"
voice_start = {}
voice_total = {}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for user_id, seconds in data.items():
                    voice_total[int(user_id)] = datetime.timedelta(seconds=seconds)
        except: pass

def save_data():
    try:
        data = {str(k): v.total_seconds() for k, v in voice_total.items()}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except: pass

# --- 💬 3. ระบบตอบโต้ (Vision + Mood + Memory + Analysis) ---
@bot.event
async def on_message(message):
    global model, current_key_index, last_boss_interaction, message_count
    if message.author.bot: return

    TARGET_CHANNEL_ID = 1465350210543947971 
    
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        # อัปเดตสถานะ Mood
        message_count += 1
        if message.author.name == "Sel1Z":
            last_boss_interaction = time.time()

        async with message.channel.typing():
            retry_count = 0
            while retry_count < len(API_KEYS):
                try:
                    # รีเฟรช Model เพื่ออัปเดตอารมณ์ล่าสุด
                    model = configure_model()
                    
                    if message.author.id not in chat_histories:
                        chat_histories[message.author.id] = []
                    
                    chat = model.start_chat(history=chat_histories[message.author.id])
                    
                    # สร้าง Prompt (รวมชื่อคนคุย + ข้อความ + รูปภาพ)
                    prompt_parts = [f"[ชื่อคนคุย: {message.author.name}]: {message.content or 'ส่องรูปนี้หน่อย'}"]
                    
                    # เช็คว่ามีรูปไหม
                    if message.attachments:
                        for attachment in message.attachments:
                            if any(ext in attachment.url.lower() for ext in ['png', 'jpg', 'jpeg', 'webp']):
                                img_data = await attachment.read()
                                img = PIL.Image.open(io.BytesIO(img_data))
                                prompt_parts.append(img)

                    response = chat.send_message(prompt_parts)
                    
                    # บันทึกประวัติ (Text Only)
                    chat_histories[message.author.id] = chat.history[-15:]

                    await message.reply(response.text)
                    return

                except Exception as e:
                    if "429" in str(e):
                        current_key_index = (current_key_index + 1) % len(API_KEYS)
                        retry_count += 1
                        continue
                    else:
                        await message.reply(f"💢 สมองช็อตว่ะ: {e}")
                        return

            await message.reply("💤 คีย์หมดคลังแล้ว ไปสมัครเมลเพิ่มสิไอ้บอส!")

    await bot.process_commands(message)

# --- ⏱️ 4. คำสั่งต่างๆ (ครบถ้วน) ---

@bot.command()
async def version(ctx):
    mood = get_current_mood()
    await ctx.send(f"🆔 รุ่น: `Gemini 2.5 Flash Lite` | คีย์: {current_key_index + 1}/{len(API_KEYS)}\n💢 อารมณ์: {mood}")

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
    print(f"✅ บอท {bot.user} ตื่นแล้ว! (โหมด God: Vision + Mood + Analysis)")

keep_alive()
TOKEN = os.getenv('TOKEN')
if TOKEN:
    bot.run(TOKEN)