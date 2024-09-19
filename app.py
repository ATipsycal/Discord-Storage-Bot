from flask import Flask, request, jsonify, render_template, send_from_directory
from cryptography.fernet import Fernet
from werkzeug.datastructures import FileStorage
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
import csv
import io



if not os.path.isfile("encryptionkey.key"):

    key = Fernet.generate_key()
 
    # Write key in a file - !!! DON'T LOSE THE KEY OR THE FILES CAN'T BE DECRYPTED !!!
    with open('encryptionkey.key', 'wb') as filekey:
        filekey.write(key)



app = Flask(__name__)

BOT_TOKEN = '' #Replace with your bot token
CHANNEL_ID =  #Replace with your channel ID
WEBPAGE_IP = '127.0.0.2'
PORT = '5000'
csv_file_path = 'message_cache.csv'
NEW_MESSAGE_FETCH_WAIT_TIME = 10

checkbox_state = 0

# Initialize Discord client
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

def encryptfile(path : str):
    with open('encryptionkey.key', 'rb') as filekey:
        key = filekey.read()

    fernet = Fernet(key)

    with open(path, 'rb') as file:
        original = file.read()

    encrypted = fernet.encrypt(original)

    with open(path, 'wb') as encrypted_file:
        encrypted_file.write(encrypted)

def decryptfiles(filen):
    # Read the encryption key from the file
    with open('encryptionkey.key', 'rb') as filekey:
        key = filekey.read()

    fernet = Fernet(key)

    with open(download_folder + "/" + filen, 'rb') as enc_file:
        encrypted = enc_file.read()

    # Decrypt the file content
    decrypted = fernet.decrypt(encrypted)

    # Write the decrypted content back to the file
    with open(download_folder + "/" + filen, 'wb') as dec_file:
        dec_file.write(decrypted)

    print("Decryption successful!")

def search_csv_file(search_text, exclude_keywords, input_file=csv_file_path):
    matching_message_and_user_ids = []  # List to store matching message IDs and line numbers

    with open(input_file, mode='r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        found = False
        # Iterate through each row in the CSV file
        for line_number, row in enumerate(reader, start=1):
            # Extract the first 3 columns: message_id, timestamp, user id, content
            message_id = row[0]
            timestamp = datetime.fromisoformat(row[1])
            user_id = row[2]
            content = row[3] if len(row) > 3 else ""  # Avoid errors if content is missing

            # Check if the message contains the search text and doesn't contain any exclude keywords
            if search_text in content and not any(keyword in content for keyword in exclude_keywords):        
                # Add the matching message ID and line number to the list
                if not found:
                    matching_message_and_user_ids.append((message_id, timestamp, user_id, content, line_number))
                    found = True
    return matching_message_and_user_ids

def search_csv_for_message(query):
    results = []
    # Open the CSV file and search for the query in the last column
    with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            # Assuming the content is in the last column of each row
            content = row[3]
            if query.lower() in content.lower():
                results.append(content)
    return results

def get_last_timestamp_from_csv(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            # Get the last row in the CSV
            last_row = None
            for last_row in csv_reader:
                pass

            if last_row:
                # Extract timestamp and convert to datetime object
                last_timestamp_str = last_row[1]
                return datetime.fromisoformat(last_timestamp_str)
            else:
                # No previous entries, return None
                return None
    except FileNotFoundError:
        # If the file doesn't exist, assume it's the first run
        return None

async def periodic_message_fetch():
    while True:
        try:
            channel = client.get_channel(CHANNEL_ID)
            if channel is None:
                print(f"Could not access the channel with ID {CHANNEL_ID}")
                await asyncio.sleep(5)
                continue
            last_timestamp = get_last_timestamp_from_csv(csv_file_path)
            messages = []
            if last_timestamp is None:
                print("No previous messages found in CSV. Fetching all messages.")
                async for message in channel.history(limit=1, oldest_first=True):
                    msg_id = message.id
                    timestamp = message.created_at
                    user_id = message.author.id
                    content = message.content.replace('\n', ' ') if message.content else 'Attachment'
                    messages.append(f'{msg_id},{timestamp},{user_id},{content}')
                with open(csv_file_path, 'a', encoding='utf-8', newline='') as file:
                    csv_writer = csv.writer(file)
                    for msg in messages:
                        csv_writer.writerow(msg.split(','))
            last_timestamp = get_last_timestamp_from_csv(csv_file_path)
            print(f"Last timestamp from CSV: {last_timestamp}")

            messages = []
            if last_timestamp:
                async for message in channel.history(limit=None, after=last_timestamp):
                    msg_id = message.id
                    timestamp = message.created_at
                    user_id = message.author.id
                    content = message.content.replace('\n', ' ') if message.content else 'Attachment'
                    messages.append(f'{msg_id},{timestamp},{user_id},{content}')

            with open(csv_file_path, 'a', encoding='utf-8', newline='') as file:
                csv_writer = csv.writer(file)
                for msg in messages:
                    csv_writer.writerow(msg.split(','))

            print(f"New messages after {last_timestamp} have been saved to {csv_file_path}")
        except Exception as e:
            print(f"Error in periodic fetch: {e}")
        await asyncio.sleep(NEW_MESSAGE_FETCH_WAIT_TIME)  # Wait for NEW_MESSAGE_FETCH_WAIT_TIME seconds before fetching again


def stitch_files(directory, *,output_file : str, base_filename : str):
    # Ensure the directory ends with a slash
    if ".encrypted" in output_file:
        output_file.replace(".encrypted", "")
    if not directory.endswith(os.path.sep):
        directory += os.path.sep

    parts = []

    # List all files in the directory and filter out the parts
    for filename in os.listdir(directory):
        if filename.startswith(base_filename) and filename != output_file:
            parts.append(filename)

    # Sort the parts by their part number
    parts.sort(key=lambda x: int(x.split('part')[-1]))

    with open(directory + output_file, 'wb') as output:
        # Iterate over each part and append contents to output file
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

    encrypted_files = glob.glob(os.path.join(download_folder, "*.encrypted"))

    for file in encrypted_files:
        new_name = file.replace(".encrypted", "")

    os.rename(file, new_name)

    print(f"Stitched {len(parts)} parts into {output_file}")

# Create the "downloaded" folder if it doesn't exist
download_folder = os.path.join(os.getcwd(), "downloaded")
if not os.path.exists(download_folder):
    os.makedirs(download_folder)

async def search_message(*, query: str):
    exclude_keywords = []
    matching_message = search_csv_file(query, exclude_keywords)
    channel = client.get_channel(CHANNEL_ID)
    if matching_message:
        found_message_id = matching_message[0][0]
    if found_message_id:
        print(f"Message found: {matching_message[0][3]} (Sent by: {matching_message[0][2]})")
        timestamp= matching_message[0][1]
        await download_files_from(channel, timestamp, query=query)
    else:
       print(f"No messages found with query: '{query}'")

async def download_files_from(channel, starting_message, *, query : str):
    async for message in channel.history(limit=None, after=starting_message):
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
            modified_query = query.replace(" ", "_").replace("(","").replace(")","")
            if ".encrypted" in file_path:
                decryptfiles(file_name)
            stitch_files(download_folder, output_file = query, base_filename = modified_query)
            print("No more files found. Stopping the download process.")
            break

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query')
    if query:
        results = search_csv_for_message(query)
        return render_template('index.html', results=results, query=query)
    return render_template('index.html', results=[], query='')

@app.route('/store_click', methods=['POST'])
def store_click():
    global clicked_message
    clicked_message = request.json.get('clicked_message')
    print(f"Clicked message stored: {clicked_message}")
    if clicked_message:
        asyncio.run_coroutine_threadsafe(search_message(query=clicked_message), client.loop)
    return jsonify({'status': 'success', 'message': 'Message stored successfully'})

@app.route('/submit_checkbox', methods=['POST'])
def submit_checkbox():
    global checkbox_state 
    checkbox_state = int(request.form.get('checkbox1'))
    
    # Log or process the checkbox state
    if checkbox_state == 1 :
        print("Encryption is enabled")
    else:
        print("Encryption is disabled")

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
        print(f'Logged in as {client.user}')
        client.loop.create_task(periodic_message_fetch())

    loop.run_until_complete(client.start(BOT_TOKEN))

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
    print(f"Checkbox state: {checkbox_state}")

    # Access the uploaded file
    file = request.files['file']
    # If the checkbox is checked (1), encrypt the file
    if checkbox_state == 1:
        filepath = os.path.join(download_folder, file.filename)
    # Save the file to the file system
        file.save(filepath)
        file.seek(0)
        print("Encrypting the file...")
        encryptfile(filepath)

        # Read the encrypted file into memory
        with open(filepath, 'rb') as file_stream:
            file_data = file_stream.read()

        # Use io.BytesIO to keep the encrypted file in memory
        memory_file = io.BytesIO(file_data)

        # Create a new FileStorage object from the in-memory encrypted file
        file = FileStorage(
            stream=memory_file,
            filename=file.filename
        )
        file.seek(0)
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


cleaned_filename_copy = "sagsagfsdghfsfdsfsdfbgfruihhoibrojivefojbjcdbjscjbikorioighobvjefvbjk"

async def send_file_to_discord(file):
    channel = client.get_channel(CHANNEL_ID)
    retries = 5  # Set retry attempts
    wait_time = 5  # Wait time between retries in seconds
    await compare_and_update(file)

    for attempt in range(retries):
        try:
            # Send the file to Discord
            message = await channel.send(file=discord.File(file.stream, filename=file.filename))
            print(f"File {file.filename} uploaded successfully on attempt {attempt + 1}")
            files_to_delete = glob.glob(os.path.join(download_folder, '*encrypted*'))
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
            return message
        except discord.errors.HTTPException as e:
            # Handle Discord API errors
            error_message = f"Error uploading file: {e}. Attempt {attempt + 1}/{retries}"
            print(error_message)
            logging.error(f"Failed to upload file: {file.filename}, Error: {e}, Attempt: {attempt + 1}/{retries}")
            if attempt < retries - 1:
                time.sleep(wait_time)
            else:
                raise
        except Exception as e:
            error_message = f"Unexpected error: {e}. Attempt {attempt + 1}/{retries}"
            print(error_message)
            logging.error(f"Unexpected failure for file: {file.filename}, Error: {e}, Attempt: {attempt + 1}/{retries}")
            if attempt < retries - 1:
                time.sleep(wait_time)
            else:
                raise

if __name__ == '__main__':
    app.run(port = PORT, host = WEBPAGE_IP)