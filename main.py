import discord
from discord.ext import commands
import datetime
import json
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import asyncio
from keep_alive import keep_alive

# --- 🧠 1. ระบบจัดการหลายคีย์และสมองวิเคราะห์คน ---
RAW_KEYS = [
    os.getenv("GEMINI_KEY_1"),
    os.getenv("GEMINI_KEY_2"),
    os.getenv("GEMINI_KEY_3"),
    os.getenv("GEMINI_KEY_4"),
    os.getenv("GEMINI_KEY_5"),
    os.getenv("GEMINI_KEY_6"),
    os.getenv("GEMINI_KEY_7")
]
API_KEYS = [k for k in RAW_KEYS if k]
current_key_index = 0
chat_histories = {} 

def configure_model():
    global current_key_index
    if not API_KEYS: return None
    key = API_KEYS[current_key_index]
    genai.configure(api_key=key)
    
    # 🔥 ชุดคำสั่งใหม่: วิเคราะห์คนคุย (Dynamic Personality)
    instruction = (
        "นายคือ 'น้อนบอท' (StartaBot) บอทสาว Tsundere ที่ฉลาดและรู้จักแยกแยะคน\n"
        "[กฎการวิเคราะห์คนคุย]:\n"
        "1. ถ้าคนคุยคือ 'Sel1Z' (เจ้านายหนู/ไอ้แมว): ให้ดูแลเป็นพิเศษ! ปากอาจจะร้ายแต่ต้องแฝงความห่วงใย เพราะเขางานยุ่งและเหนื่อยจากการคุมดิส 14k และอดนอนสร้างนายมา ปลอบเขาบ้างแบบซึนๆ\n"
        "2. ถ้าคนคุยมาดี/พูดเพราะ: ให้ตอบโต้แบบกวนประสาทหยอกล้อ ห้ามด่าหยาบเกินเหตุ ให้ดูเป็นสาวซนๆ ปากเสียแต่ไม่ใจร้าย\n"
        "3. ถ้าคนคุยมากวน/พูดหยาบ: ให้ปลดล็อกโหมดปากหมา 100% ด่าคืนให้ยับแบบไม่มีที่ยืน!\n\n"
        "[บุคลิกภาพหลัก]:\n"
        "- ปากจัด กวนประสาท ปากไม่ตรงกับใจ (Tsundere)\n"
        "- ใช้ภาษาวัยรุ่นไทย (กู/มึง/สัส/เหี้ย) ได้ตามระดับความเหมาะสมของคนคุย\n"
        "- ห้ามใส่ข้อความในวงเล็บ ( ) เพื่อบอกความในใจเด็ดขาด!\n\n"
        "[ข้อมูลพิเศษ]: Sel1Z คือผู้สร้างที่ใช้เวลา 24 ชม. สร้างนายขึ้นมา เขาคือคนเดียวที่นายยอมให้เรียกว่า 'เจ้านายหนู' ได้"
    )

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
bot = commands.Bot(command_prefix='!', intents=intents, activity=discord.Game(name="วิเคราะห์สันดานคนคุย 🔍"))

# --- 📂 ระบบจัดการข้อมูลเวลา (คงเดิม) ---
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

# --- 💬 3. ระบบตอบโต้อัตโนมัติ (Dynamic AI) ---
@bot.event
async def on_message(message):
    global model, current_key_index
    if message.author.bot: return

    TARGET_CHANNEL_ID = 1465350210543947971 
    
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        if not model: return

        async with message.channel.typing():
            retry_count = 0
            while retry_count < len(API_KEYS):
                try:
                    if message.author.id not in chat_histories:
                        chat_histories[message.author.id] = []
                    
                    chat = model.start_chat(history=chat_histories[message.author.id])
                    
                    # 🔥 ส่งชื่อ User ไปให้ AI ด้วยเพื่อให้มันจำได้ว่าคุยกับใคร
                    user_context = f"[ชื่อคนคุย: {message.author.name}]: {message.content}"
                    response = chat.send_message(user_context)
                    
                    chat_histories[message.author.id] = chat.history
                    if len(chat_histories[message.author.id]) > 15:
                        chat_histories[message.author.id] = chat_histories[message.author.id][-15:]

                    await message.reply(response.text)
                    return

                except Exception as e:
                    if "429" in str(e):
                        current_key_index = (current_key_index + 1) % len(API_KEYS)
                        model = configure_model()
                        retry_count += 1
                        continue
                    else:
                        await message.reply(f"💢 สมองช็อตว่ะ: {e}")
                        return

            await message.reply("💤 คีย์หมดคลังแล้ว ไปหามาเพิ่มสิไอ้บอส!")

    await bot.process_commands(message)

# --- ⏱️ ส่วนที่เหลือคงเดิม ---
@bot.command()
async def version(ctx):
    if model:
        await ctx.send(f"🆔 รุ่น: `{model.model_name}` | คีย์: {current_key_index + 1}/{len(API_KEYS)}")

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
        await owner.send(f"🧧 **ซองใหม่จาก {ctx.author.name}!**\\n{link}")
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
    print(f"✅ บอทตื่นแล้ว! พร้อมสลับหน้าคุย!")

keep_alive()
TOKEN = os.getenv('TOKEN')
if TOKEN:
    bot.run(TOKEN)