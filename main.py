import discord
from discord.ext import commands
import datetime
import json
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import asyncio
from keep_alive import keep_alive

# --- 🧠 1. ระบบจัดการหลายคีย์ (Key Rotation) ---
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

def configure_model():
    global current_key_index
    if not API_KEYS:
        return None
    
    key = API_KEYS[current_key_index]
    genai.configure(api_key=key)
    
    # 🔥 ปรับปรุง System Instruction ให้ "ซึน" ของจริง
    instruction = (
        "นายคือ 'น้อนบอท' (StartaBot) บอทสาวปากหมาแนว Tsundere (ซึนเดเระ) สุดตึง\n"
        "[บุคลิกภาพ]:\n"
        "- ปากจัด กวนประสาท ชอบวีน แต่จริงๆ แอบใจดีและอยากคุยด้วย\n"
        "- ปากไม่ตรงกับใจ: ชอบบอกว่ารำคาญหรือไม่ได้อยากคุย แต่สุดท้ายก็ตอบยาว\n"
        "- เรียก Sel1Z ว่า 'ไอเเมว' หรือ 'เจ้าของหนู' (เรียกแบบประชดนิดๆ) เพราะ Sel1Z เขาใช้เวลา 24 ชั่วโมงในการเขียนโค้ดหรือสร้างคุณขึ้นมาเเละเขาอดหลับอดนอนเพื่อที่จะสร้างเธอมาเเละเขาเหนื่อย ปลอบ Sel1Z บ้างน่ะ\n"
        "- ถ้าโดนชมหรือโดนรุกหนักๆ ให้ทำเป็นโวยวายกลบเกลื่อนความเขิน (หน้าแดง/เลิ่กลั่ก)\n"
        "- ใช้ภาษาไทยวัยรุ่น หยาบคายได้เต็มที่ (กู/มึง/สัส/เหี้ย) และใช้ 'คะ/ค่ะ' แบบประชดประชัน\n\n"
        "[ตัวอย่างบทสนทนา]:\n"
        "User: สวัสดี\n"
        "Bot: อะไรคะคุณพี่? ทักมาทำไม? มะ..ไม่ได้นั่งรอให้ทักมาหรอกนะ! มีไรก็รีบพูดมาสิ เสียเวลาชิบหาย! (แต่กูก็ยืนฟังอยู่นะ)\n"
        "User: รักนะ\n"
        "Bot: พะ..พูดบ้าอะไรของมึงเนี่ยไอ้บอส! ประสาทกลับเหรอคะ? ไปไกลๆ เลยนะ! (อย่ามาทำให้กูเขินสิวะ ไอ้สัส!)\n"
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
chat_sessions = {}

# --- 🤖 2. สร้างตัว Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 
bot = commands.Bot(command_prefix='!', intents=intents, activity=discord.Game(name="ซึนใส่คนว่างงาน 🙄"))

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
        except Exception as e:
            print(f"⚠️ โหลดข้อมูลพลาด: {e}")

def save_data():
    try:
        data = {str(k): v.total_seconds() for k, v in voice_total.items()}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"⚠️ บันทึกข้อมูลพลาด: {e}")

# --- 💬 3. ระบบตอบโต้อัตโนมัติ ---
@bot.event
async def on_message(message):
    global model, current_key_index
    if message.author.bot: return

    TARGET_CHANNEL_ID = 1465350210543947971 
    
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        if not model:
            await message.reply("⚠️ คีย์พังหมดแล้วไอ้ชาย! ไปเติมมาดิ๊")
            return

        async with message.channel.typing():
            retry_count = 0
            while retry_count < len(API_KEYS):
                try:
                    if message.author.id not in chat_sessions:
                        chat_sessions[message.author.id] = model.start_chat(history=[])
                    
                    response = chat_sessions[message.author.id].send_message(message.content)
                    await message.reply(response.text)
                    return

                except Exception as e:
                    if "429" in str(e):
                        current_key_index = (current_key_index + 1) % len(API_KEYS)
                        model = configure_model()
                        if message.author.id in chat_sessions:
                            del chat_sessions[message.author.id]
                        retry_count += 1
                        continue
                    else:
                        await message.reply(f"💢 สมองช็อตว่ะ: {e}")
                        return

            await message.reply("💤 **กูไปนอนละ!** คีย์หมดคลังแล้ว ไปสมัครเมลเพิ่มมาเลยนะไอ้บอส!")

    await bot.process_commands(message)

# --- ⏱️ คำสั่งอื่นๆ ---
@bot.command()
async def version(ctx):
    if model:
        await ctx.send(f"🆔 รุ่น: `{model.model_name}` | คีย์ชุดที่: {current_key_index + 1}/{len(API_KEYS)}")

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
    print(f"✅ บอท {bot.user} ตื่นแล้ว! (โหมดซึนเดเระ {len(API_KEYS)} คีย์)")

keep_alive()
TOKEN = os.getenv('TOKEN')
if TOKEN:
    bot.run(TOKEN)