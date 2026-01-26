import discord
from discord.ext import commands
import datetime
import json
import os
from openai import OpenAI  # เราใช้ตัวนี้คุยกับ Groq ได้เลย
import asyncio
from keep_alive import keep_alive

# --- 🧠 ประกาศตัวแปร Global ---
chat_histories = {}
client = None

# --- 🤖 1. สร้างตัว Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 
bot = commands.Bot(command_prefix='!', intents=intents, activity=discord.Game(name="ด่าคนด้วยความเร็วแสง (Groq) ⚡"))

# --- 🧠 2. ตั้งค่า Groq AI ---
# ไปเอา Key ฟรีที่ https://console.groq.com/keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 

if GROQ_API_KEY:
    # เคล็ดลับ: ใช้ Client ของ OpenAI แต่เปลี่ยน base_url ไปหา Groq
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    print("✅ เชื่อมต่อ Groq Cloud สำเร็จ!")
else:
    print("⚠️ ไม่เจอ GROQ_API_KEY")

# ตั้งค่านิสัยบอท (System Prompt)
SYSTEM_INSTRUCTION = "นายคือ 'น้อนบอท' บอทปากหมาสุดตึง ตอบกวนๆ ด่ามาด่ากลับ ใช้คำหยาบได้เต็มที่ ไม่ต้องสุภาพ เน้นตอบไวและเจ็บแสบ"
# ใช้รุ่น Llama 3.3 ตัวล่าสุด (ฉลาดและฟรี)
MODEL_NAME = "llama-3.3-70b-versatile" 

# --- 🔍 3. คำสั่งเช็คของ ---
@bot.command()
async def version(ctx):
    await ctx.send(f"⚡ บอทตัวนี้รันด้วยสมอง: `{MODEL_NAME}` (บน Groq Cloud เร็วแรงทะลุนรก!)")

DATA_FILE = "time_data.json"
voice_start = {}
voice_total = {}

# --- 📂 ระบบจัดการข้อมูลเวลา (คงเดิม) ---
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

# --- 💬 ระบบตอบโต้อัตโนมัติ (Groq/Llama) ---
@bot.event
async def on_message(message):
    if message.author.bot: return

    # 🔴 อย่าลืมแก้ ID ห้องตรงนี้นะครับ!
    TARGET_CHANNEL_ID = 1465350210543947971 
    
    if message.channel.id == TARGET_CHANNEL_ID and not message.content.startswith('!'):
        if client is None:
            await message.reply("⚠️ ยังไม่ได้ใส่ API Key ของ Groq ครับบอส!")
            return

        async with message.channel.typing():
            try:
                user_id = message.author.id
                
                # 1. เตรียมประวัติการคุย
                if user_id not in chat_histories:
                    chat_histories[user_id] = [
                        {"role": "system", "content": SYSTEM_INSTRUCTION}
                    ]
                
                # 2. เพิ่มข้อความใหม่ของ user
                chat_histories[user_id].append({"role": "user", "content": message.content})
                
                # 3. ตัดประวัติถ้ามันยาวเกิน (ประหยัด Token)
                if len(chat_histories[user_id]) > 12:
                    chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-10:]

                # 4. ส่งให้ Groq ตอบ (เร็วมาก!)
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=chat_histories[user_id],
                    max_tokens=400,
                    temperature=0.8, # ยิ่งสูงยิ่งกวน (0.0 - 2.0)
                )

                reply_text = response.choices[0].message.content
                
                # 5. เก็บคำตอบบอทลงประวัติ
                chat_histories[user_id].append({"role": "assistant", "content": reply_text})

                await message.reply(reply_text)

            except Exception as e:
                # ดัก Error 429 ของ Groq (เผื่อฟลุ๊คเจอ)
                if "429" in str(e):
                    await message.reply("💤 **Groq บอกให้พักก่อน!** (พิมพ์เร็วเกินไปแล้วไอ้ชาย!)")
                else:
                    print(f"🔥 Groq Error: {e}")
                    await message.reply(f"💢 ระบบล่มว่ะ: {e}")

    await bot.process_commands(message)

# --- ⏱️ คำสั่ง !time, !tops, !topup (คงเดิม) ---
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

# --- 🎙️ Voice Events (คงเดิม) ---
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
    print(f"⚡ บอทตื่นแล้ว! สมอง Groq Llama 3: {MODEL_NAME}")
    print(f"✅ บอท {bot.user} พร้อมซิ่ง!")

keep_alive()
TOKEN = os.getenv('TOKEN')
if TOKEN:
    bot.run(TOKEN)