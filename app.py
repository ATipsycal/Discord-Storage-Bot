from flask import Flask, request, jsonify, render_template, send_from_directory
import discord
import os
import aiohttp
import asyncio
import threading
import time
import logging
from datetime import datetime
from concurrent.futures import CancelledError
import glob
import argparse

app = Flask(__name__)

BOT_TOKEN = 'YOUR_BOT_TOKEN'
CHANNEL_ID = YOUR_CHANNEL_ID #MUST BE A NUMBER NOT BETWEEN ' '
WEBPAGE_IP = '127.0.0.2'
PORT = '5000'

# Initialize Discord client outside the request handling
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

def stitch_files(directory, *,output_file : str, base_filename : str):
    # Ensure the directory ends with a slash
    if not directory.endswith(os.path.sep):
        directory += os.path.sep

    # Initialize a list to hold the file parts
    parts = []

    # List all files in the directory and filter out the parts
    for filename in os.listdir(directory):
        if filename.startswith(base_filename) and filename != output_file:
            parts.append(filename)

    # Sort the parts by their part number
    parts.sort(key=lambda x: int(x.split('part')[-1]))

    # Open the output file in write-binary mode
    with open(directory + output_file, 'wb') as output:
        # Iterate over each part and append its contents to the output file
        for part in parts:
            with open(directory + part, 'rb') as f:
                output.write(f.read())
    files_to_delete = glob.glob(os.path.join(directory, '*part*'))
    for file_path in files_to_delete:
        try:
            os.remove(file_path)
            print(f"Deleted: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
    print(f"Stitched {len(parts)} parts into {output_file}")

# Create the "downloaded" folder if it doesn't exist
download_folder = os.path.join(os.getcwd(), "downloaded")
if not os.path.exists(download_folder):
    os.makedirs(download_folder)

async def search_message(channel_id: int, *, query: str):
    channel = client.get_channel(channel_id)
    if channel is None:
        channel = await client.fetch_channel(channel_id)

    found_message = None
    async for message in channel.history(limit=400000):
        if query.lower() in message.content.lower() and '!' not in message.content and "found" not in message.content and "Downloaded" not in message.content:
            found_message = message
            break

    if found_message:
        print(f"Message found: {found_message.content} (Sent by: {found_message.author})")
        await download_files_from(channel, found_message, query=query)
    else:
       print(f"No messages found with query: '{query}' (excluding the bot's messages)")

async def download_files_from(channel, starting_message, *, query : str):
    async for message in channel.history(after=starting_message, limit=100000):
        if message.attachments:
            for attachment in message.attachments:
                file_url = attachment.url
                file_name = attachment.filename

                async with aiohttp.ClientSession() as session:
                    async with session.get(file_url) as resp:
                        if resp.status == 200:
                            file_path = os.path.join(download_folder, file_name)
                            with open(file_path, "wb") as f:
                                f.write(await resp.read())
        else:
            modified_query = query.replace(" ", "_")
            stitch_files("downloaded", output_file = query, base_filename = modified_query)
            print("No more files found. Stopping the download process.")
            break

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    search_query = data.get('query')
    channel_id = CHANNEL_ID
    if search_query:
        # Run the asynchronous function in the client's event loop
        asyncio.run_coroutine_threadsafe(search_message(channel_id, query=search_query), client.loop)
        return jsonify({"message": f"Query received: {search_query}"}), 200
    else:
        return jsonify({"error": "No query received"}), 400

lock = asyncio.Lock()

logging.basicConfig(filename='file_upload_failures.log', 
                    level=logging.ERROR,
                    format='%(asctime)s %(message)s')

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

def start_discord_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    @client.event
    async def on_ready():
        print('Discord client is ready.')

    client.run(BOT_TOKEN)  # Replace with your token

async def compare_and_update(file):
        async with lock:
            channel = client.get_channel(CHANNEL_ID)
            global cleaned_filename_copy
            cleaned_filename = '.'.join(file.filename.split('.')[:-1])
            if cleaned_filename != cleaned_filename_copy:
                await channel.send(cleaned_filename)
            cleaned_filename_copy = cleaned_filename

# Run Discord client in a background thread
threading.Thread(target=start_discord_bot, daemon=True).start()

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    # Ensure the Discord client is ready before attempting to send
    if not client.is_closed():
        try:
            future = asyncio.run_coroutine_threadsafe(send_file_to_discord(file), client.loop)
            result = future.result()  # Wait for the coroutine to finish and return its result
            return jsonify({'message': 'File uploaded successfully!'})
        except CancelledError:
            return jsonify({'error': 'Task was cancelled due to an error.'}), 500
        except Exception as e:
            print(f"Error during upload: {e}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Discord client is closed.'}), 500

cleaned_filename_copy = "sagsagfsdghfsfdsfsdf"

async def send_file_to_discord(file):
    channel = client.get_channel(CHANNEL_ID)  # Replace with your channel ID
    retries = 5  # Set retry attempts
    wait_time = 5  # Wait time between retries in seconds
    await compare_and_update(file)

    for attempt in range(retries):
        try:
            # Send the file to Discord
            message = await channel.send(file=discord.File(file.stream, filename=file.filename))
            print(f"File {file.filename} uploaded successfully on attempt {attempt + 1}")
            return message
        except discord.errors.HTTPException as e:
            # Handle Discord API errors (e.g., rate limiting, 520 errors)
            error_message = f"Error uploading file: {e}. Attempt {attempt + 1}/{retries}"
            print(error_message)
            logging.error(f"Failed to upload file: {file.filename}, Error: {e}, Attempt: {attempt + 1}/{retries}")
            if attempt < retries - 1:
                time.sleep(wait_time)  # Wait before retrying
            else:
                raise
        except Exception as e:
            error_message = f"Unexpected error: {e}. Attempt {attempt + 1}/{retries}"
            print(error_message)
            logging.error(f"Unexpected failure for file: {file.filename}, Error: {e}, Attempt: {attempt + 1}/{retries}")
            if attempt < retries - 1:
                time.sleep(wait_time)  # Wait before retrying
            else:
                raise

if __name__ == '__main__':
    app.run(port = PORT, host = WEBPAGE_IP)