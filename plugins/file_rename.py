from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.ffmpeg import fix_thumb, take_screen_shot
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import jishubotz
from asyncio import sleep
from PIL import Image
import os, time, re, random, asyncio


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name  
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sorry, this bot doesn't support uploading files bigger than 2GB.")

    try:
        await message.reply_text(
            text=f"**Please enter a new filename...**\n\n**Old File Name:** `{filename}`",
            reply_to_message_id=message.id,  
            reply_markup=ForceReply(True)
        )
        await sleep(30)
    except FloodWait as e:
        await sleep(e.value)
        await message.reply_text(
            text=f"**Please enter a new filename...**\n\n**Old File Name:** `{filename}`",
            reply_to_message_id=message.id,  
            reply_markup=ForceReply(True)
        )
    except:
        pass


@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message
    if (reply_message.reply_markup) and isinstance(reply_message.reply_markup, ForceReply):
        new_name = message.text 
        await message.delete() 
        msg = await client.get_messages(message.chat.id, reply_message.id)
        file = msg.reply_to_message
        if not file:
            return await message.reply_text("Failed to retrieve the file. Please try again.")
        
        media = getattr(file, file.media.value)
        if not "." in new_name:
            extn = media.file_name.rsplit('.', 1)[-1] if "." in media.file_name else "mkv"
            new_name = new_name + "." + extn
        await reply_message.delete()

        original_file_path = f"downloads/{message.from_user.id}/{media.file_name}"
        new_file_path = f"downloads/{message.from_user.id}/{new_name}"
        
        # Download the file
        await client.download_media(file, original_file_path)

        # Metadata change command
        cmd = f'''ffmpeg -i "{original_file_path}" -map 0 -c:s copy -c:a copy -c:v copy \
        -metadata title="{new_name}" \
        -metadata author="@AniMovieRulz" \
        -metadata:s:s title="@AniMovieRulz" \
        -metadata:s:a title="@AniMovieRulz" \
        -metadata:s:v title="@AniMovieRulz" "{new_file_path}" '''

        # Try to run ffmpeg command
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        if stderr.decode():
            await message.reply_text(f"Error during metadata update: {stderr.decode()}\nProceeding with renaming only.")
            # Fallback to renaming only
            os.rename(original_file_path, new_file_path)

        # Clean up original file if not renamed by fallback
        if os.path.exists(original_file_path):
            os.remove(original_file_path)

        # Continue with the process (upload, thumbnail creation, etc.)
        duration = 0
        try:
            parser = createParser(new_file_path)
            metadata = extractMetadata(parser)
            if metadata.has("duration"):
                duration = metadata.get('duration').seconds
            parser.close()   
        except:
            pass
        
        ph_path = None
        user_id = int(message.chat.id)
        c_caption = await jishubotz.get_caption(message.chat.id)
        c_thumb = await jishubotz.get_thumbnail(message.chat.id)
        media = getattr(file, file.media.value)

        if c_caption:
            try:
                caption = c_caption.format(filename=new_name, filesize=humanbytes(media.file_size), duration=convert(duration))
            except Exception as e:
                return await message.reply_text(text=f"Your Caption Error: {e}")             
        else:
            caption = f"**{new_name}**"
 
        if (media.thumbs or c_thumb):
            if c_thumb:
                ph_path = await client.download_media(c_thumb)
                width, height, ph_path = await fix_thumb(ph_path)
            else:
                try:
                    ph_path_ = await take_screen_shot(new_file_path, os.path.dirname(os.path.abspath(new_file_path)), random.randint(0, duration - 1))
                    width, height, ph_path = await fix_thumb(ph_path_)
                except Exception as e:
                    ph_path = None
                    print(e)

        # Sending output type selection message
        button = [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]]
        if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
            button.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
        elif file.media == MessageMediaType.AUDIO:
            button.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])

        await client.send_message(
            message.chat.id,
            text=f"**Select The Output File Type**\n\n**File Name:** `{new_name}`",
            reply_to_message_id=file.id,
            reply_markup=InlineKeyboardMarkup(button)
        )


@Client.on_callback_query(filters.regex("upload"))
async def doc(bot, update):    
    new_name = update.message.text.split(":-")[1].strip()
    file_path = f"downloads/{update.from_user.id}/{new_name}"

    ms = await update.message.edit("`Trying to upload...`")
    media = getattr(update.message.reply_to_message, update.message.reply_to_message.media.value)
    c_caption = await jishubotz.get_caption(update.message.chat.id)
    c_thumb = await jishubotz.get_thumbnail(update.message.chat.id)
    _bool_metadata = await jishubotz.get_metadata(update.message.chat.id)

    caption = c_caption.format(filename=new_name, filesize=humanbytes(media.file_size), duration=convert(duration)) if c_caption else f"**{new_name}**"
    ph_path = c_thumb if c_thumb else None

    if ph_path:
        ph_path = await bot.download_media(c_thumb)
        width, height, ph_path = await fix_thumb(ph_path)

    try:
        if update.data == "upload_document":
            await bot.send_document(
                update.message.chat.id,
                document=file_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("`Upload Started...`", ms, time.time())
            )

        elif update.data == "upload_video":
            await bot.send_video(
                update.message.chat.id,
                video=file_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("`Upload Started...`", ms, time.time())
            )

        elif update.data == "upload_audio":
            await bot.send_audio(
                update.message.chat.id,
                audio=file_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("`Upload Started...`", ms, time.time())
            )

    except Exception as e:
        return await ms.edit(f"**Error:** `{e}`")

    finally:
        os.remove(file_path)
        if ph_path:
            os.remove(ph_path)

    await ms.delete()
	
