import discord
from discord.ext import commands
import datetime
import json
import os
from keep_alive import keep_alive

# --- ตั้งค่าพื้นฐาน ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True 

activity = discord.Game(name="เฝ้าห้องเสียง & รอรับซอง 🕵️🧧")
bot = commands.Bot(command_prefix='!', intents=intents, activity=activity)

DATA_FILE = "time_data.json"
voice_start = {}
voice_total = {}

# --- 📂 ส่วนจัดการข้อมูล (จับเวลา) ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for user_id, seconds in data.items():
                    voice_total[int(user_id)] = datetime.timedelta(seconds=seconds)
            print("📂 โหลดข้อมูลเวลาเก่าเรียบร้อย!")
        except:
            print("⚠️ ไฟล์ข้อมูลว่างเปล่าหรือผิดพลาด")

def save_data():
    data = {str(k): v.total_seconds() for k, v in voice_total.items()}
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- 🤖 Events ---
@bot.event
async def on_ready():
    load_data()
    print(f'✅ บอท {bot.user} ออนไลน์พร้อมระบบ Full Option!')
    
    # เช็คคนตกค้างในห้อง
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            for member in channel.members:
                if not member.bot and member.id not in voice_start:
                    voice_start[member.id] = datetime.datetime.now()

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return

    # 🟢 เข้าห้องเสียง
    if before.channel is None and after.channel is not None:
        voice_start[member.id] = datetime.datetime.now()
        print(f"🟢 {member.name} เข้าสาย")

    # 🔴 ออกจากห้องเสียง
    elif before.channel is not None and after.channel is None:
        if member.id in voice_start:
            start = voice_start.pop(member.id)
            duration = datetime.datetime.now() - start
            
            if member.id not in voice_total:
                voice_total[member.id] = datetime.timedelta()
            
            voice_total[member.id] += duration
            save_data()
            print(f"💾 {member.name} ออกสาย (เก็บเวลาเพิ่ม {duration})")

# --- ⏱️ คำสั่งระบบจับเวลา ---
@bot.command()
async def time(ctx, member: discord.Member = None):
    target = member or ctx.author
    total = voice_total.get(target.id, datetime.timedelta())
    
    # ถ้ายังอยู่ในสาย ให้บวกเวลาปัจจุบันเข้าไปด้วย
    if target.id in voice_start:
        current_session = datetime.datetime.now() - voice_start[target.id]
        total += current_session
        
    total_str = str(total).split('.')[0] # ตัดเศษวินาทีออก
    await ctx.reply(f"⏱️ คุณ **{target.name}** ออนไลน์รวมทั้งหมด: **{total_str}**")

@bot.command()
async def tops(ctx):
    if not voice_total and not voice_start:
        await ctx.reply("❌ ยังไม่มีข้อมูลใครเลยครับ")
        return

    # รวมเวลาทั้งเก่าและใหม่
    final_data = voice_total.copy()
    now = datetime.datetime.now()
    for uid, start_time in voice_start.items():
        current = now - start_time
        final_data[uid] = final_data.get(uid, datetime.timedelta()) + current

    # เรียงลำดับคนว่างงาน (Top 5)
    sorted_data = sorted(final_data.items(), key=lambda x: x[1].total_seconds(), reverse=True)[:5]

    embed = discord.Embed(title="🏆 5 อันดับ เทพเจ้าคนว่างงาน", color=0xFFD700)
    for i, (user_id, time_val) in enumerate(sorted_data):
        member = ctx.guild.get_member(user_id)
        name = member.name if member else f"User ID: {user_id}"
        time_str = str(time_val).split('.')[0]
        embed.add_field(name=f"#{i+1} {name}", value=f"⏱️ {time_str}", inline=False)

    await ctx.send(embed=embed)

# --- 🧧 คำสั่งระบบรับซอง (DM Forwarding) ---
@bot.command()
async def topup(ctx, link: str):
    if "gift.truemoney.com" not in link:
        await ctx.reply("❌ ลิ้งก์ไม่ถูกต้องครับพี่ชาย")
        return

    # ดึงไอดีจาก "ตู้เซฟ" ใน Render
    owner_id_env = os.getenv('OWNER_ID')
    
    if not owner_id_env:
        await ctx.reply("⚠️ เจ้าของบอทยังไม่ได้ตั้งค่า OWNER_ID ใน Render!")
        return
    
    try:
        owner_id = int(owner_id_env)
        owner = await bot.fetch_user(owner_id)
        
        # ส่งลิ้งก์เข้า DM ของเจ้าของทันที
        embed = discord.Embed(title="💰 มีคนส่งซองของขวัญมาครับ!", color=0x00ff00)
        embed.add_field(name="ผู้ส่ง", value=f"{ctx.author.mention}", inline=False)
        embed.add_field(name="ลิ้งก์ซอง", value=link, inline=False)
        embed.set_footer(text="รีบกดรับก่อนซองหมดอายุนะ!")
        
        await owner.send(embed=embed)
        await owner.send(link) # ส่งแยกเพื่อให้กดง่ายในมือถือ

        # ลบข้อความในห้อง (กันคนอื่นแย่งกด)
        await ctx.message.delete()
        await ctx.send(f"✅ คุณ {ctx.author.mention} ส่งซองเรียบร้อย! รอเจ้าของตรวจสอบครับ")

    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("❌ บอท DM หาเจ้าของไม่ได้ (ลองเช็คว่าเจ้าของเปิด DM หรือยัง)")

# --- 🚀 เริ่มระบบ ---
keep_alive()
token = os.getenv('TOKEN') 
bot.run(token)