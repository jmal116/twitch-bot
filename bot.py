import asyncio
import uuid
import json
import random
from datetime import datetime, timedelta
import webbrowser
import os
from multiprocessing import Process, Value
from collections import namedtuple
import re

import websockets
import requests
import keyboard
import pyttsx3
import playsound

TTS_REWARD_ID = '259c7354-82f7-4d5b-90c7-d85a1434ddac'
BAN_REWARD_ID = '7cda13cb-d15d-4652-89ac-a492b39d42a9'
QUACK_ID = 'e0f41bbb-7c09-4767-91e3-f586438ee411'
BIG_QUACK_ID = '5e12b9ef-b5ae-448f-ac11-3caa5607531b'

BAN_FILE = 'bans\\bans.txt'

ChatMessage = namedtuple('ChatMessage', ['user', 'message', 'command'])

class Bot:

    def __init__(self):
        self.client_id = 'lil5xkerbfl7lsj2pk1qhvgsi8fro4'
        self.client_secret = 'm33z33z1d60n67n2kev7iw54foo6db'
        self.pubsub_connection = None
        self.chat_connection = None
        self.next_ping = datetime.now()
        self.tts = pyttsx3.init()
        self.tts.setProperty('rate', 150)
        self.num_tts_redemptions = 0
        self.num_tts_read = Value('i', 0)
        self.is_speaking = Value('b', False)
        self.tts_process = None


        #Get an app access token
        self.app_access_token = requests.post('https://id.twitch.tv/oauth2/token',
        params={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }).json()['access_token']
        print('Successfully acquired app access token')

        #verify channel id
        self.channel_id = requests.get('https://api.twitch.tv/helix/users',
        headers={
            'Client-Id': self.client_id,
            'Authorization': f'Bearer {self.app_access_token}'
        },
        params={
            'login': 'jmal116'
        }).json()['data'][0]['id']
        print('Successfully fetched channel id')

        # print('Paste code for the chatbot account:\n')
        # self.chatbot_token, _ = self.get_user_tokens()
        print('Paste code for the main channel:\n')
        self.user_token, self.refresh_token = self.get_user_tokens()
        self.chatbot_token = self.user_token

    def get_user_tokens(self):
        webbrowser.open(r'https://id.twitch.tv/oauth2/authorize?client_id=lil5xkerbfl7lsj2pk1qhvgsi8fro4&response_type=code&redirect_uri=http%3A%2F%2Flocalhost&force_verify=false&scope=channel:read:redemptions%20channel:moderate%20chat:edit%20chat:read')
        temp_code = input()
        resp = requests.post('https://id.twitch.tv/oauth2/token',
        params={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': temp_code,
            'redirect_uri': 'http://localhost'
        }).json()
        return resp['access_token'], resp['refresh_token']

    async def connect_pubsub(self):
        '''
           Connecting to webSocket server
           websockets.client.connect returns a WebSocketClientProtocol, which is used to send and receive messages
        '''
        topics = [f"channel-points-channel-v1.{self.channel_id}"]
        self.pubsub_connection = await websockets.client.connect('wss://pubsub-edge.twitch.tv')
        if self.pubsub_connection.open:
            print('Pubsub connection established. Client correcly connected')
            # Send greeting
            message = {"type": "LISTEN", "nonce": str(self.generate_nonce()), "data":{"topics": topics, "auth_token": self.user_token}}
            await self.send_pubsub(message)

    async def connect_chatbot(self):
        self.chat_connection = await websockets.client.connect('wss://irc-ws.chat.twitch.tv:443')
        if self.chat_connection.open:
            print('chatbot connection established.')
            await self.send_irc(f'PASS oauth:{self.chatbot_token}', self.chat_connection)
            await self.recieve_irc(self.chat_connection)
            await self.send_irc('NICK therealmrspancakes', self.chat_connection)
            await self.recieve_irc(self.chat_connection)
            await self.send_irc('JOIN #jmal116', self.chat_connection)

    async def connect_command(self):
        self.command_connection = await websockets.client.connect('wss://irc-ws.chat.twitch.tv:443')
        if self.command_connection.open:
            print('command connection established.')
            await self.send_irc(f'PASS oauth:{self.user_token}', self.command_connection)
            await self.recieve_irc(self.command_connection)
            await self.send_irc('NICK jmal116', self.command_connection)
            await self.recieve_irc(self.command_connection)
            await self.send_irc('JOIN #jmal116', self.command_connection)

    def generate_nonce(self):
        '''Generate pseudo-random number and seconds since epoch (UTC).'''
        nonce = uuid.uuid1()
        oauth_nonce = nonce.hex
        return oauth_nonce

    async def refresh_pubsub(self):
        resp = requests.post('https://id.twitch.tv/oauth2/token--data-urlencode',
        params={
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }).json()
        self.refresh_token = resp['refresh_token']
        self.user_token = resp['access_token']

    async def send_pubsub(self, message):
        '''Sending message to webSocket server'''
        json_message = json.dumps(message)
        # print(f'Sending to pubsub: {message}')
        try:
            await self.pubsub_connection.send(json_message)
        except websockets.exceptions.ConnectionClosed:
            print('Connection with pubsub closed, retrying')
            await self.connect_pubsub()
        

    async def receive_pubsub(self):
        '''Receiving all server messages and handling them'''
        try:
            message = json.loads(await asyncio.wait_for(self.pubsub_connection.recv(), 1/60))
            # print(f'Received message from pubsub: {message}')
            if message['type'] == 'RECONNECT':
                print('pubsub reconnect message recieved, doing it')
                self.pubsub_connection.close()
                await self.connect_pubsub()
            if message['type'] == 'MESSAGE':
                print(message)
                await self.process_redemption(json.loads(message['data']['message']))
        except asyncio.exceptions.TimeoutError:
            return
        except websockets.exceptions.ConnectionClosed:
            print('Connection with pubsub server closed, retrying')
            await self.connect_pubsub()

    async def heartbeat_pubsub(self):
        '''
        Sending heartbeat to server every 3 minutes
        Ping - pong messages to verify/keep connection is alive
        '''
        if self.next_ping < datetime.now():
            data_set = {"type": "PING"}
            await self.send_pubsub(data_set)
            self.next_ping = datetime.now() + timedelta(seconds=180 + random.randint(1, 5))

    async def send_irc(self, message, connection):
        # print(f'< {message}')
        try:
            await connection.send(f'{message}')
        except websockets.exceptions.ConnectionClosed:
            print('Connection with IRC server closed, retrying')
            await self.connect_chatbot()
            await self.connect_command()

    async def recieve_irc(self, connection, parse_message=False):
        try:
            message = await asyncio.wait_for(connection.recv(), 1/60)
            message = message.strip()
            # print(f'> {message}')
            if message[:4] == 'PING':
                await self.send_irc('PONG', connection)
            elif parse_message:
                parsed = self.parse_chat(message)
                if not parsed:
                    # this shouldn't ever happen, but it probably will at some point because I put ~2 minutes of thought into this solution
                    return
                if parsed.command:
                    await self.process_chat_command(parsed)
                
        except asyncio.exceptions.TimeoutError:
            return
        except websockets.exceptions.ConnectionClosed:
            print('Connection with IRC server closed, retrying')
            await self.connect_chatbot()
            await self.connect_command()

    async def send_chat_message(self, message):
        await self.send_irc(f'PRIVMSG #jmal116 :{message}', self.chat_connection)

    async def send_command(self, cmd):
        await self.send_irc(f'PRIVMSG #jmal116 :{cmd}', self.command_connection)

    def parse_chat(self, msg):
        result = re.match(r'^:(.*?)!\1@\1.tmi.twitch.tv PRIVMSG #jmal116 :(.*?)$', msg)
        if result:
            user = result[1]
            message = result[2]
            command = (re.match(r'!([^\W]*)', message) or {1: None})[1]
            return ChatMessage(user, message, command)
        return None

    async def process_chat_command(self, message):
        cmd = message.command
        if cmd == 'thonk':
            await self.send_chat_message('⠀⠰⡿⠿⠛⠛⠻⠿⣷')
            await self.send_chat_message('⠀⠀⠀⠀⠀⠀⣀⣄⡀⠀⠀⠀⠀⢀⣀⣀⣤⣄⣀⡀')
            await self.send_chat_message('⠀⠀⠀⠀⠀⢸⣿⣿⣷⠀⠀⠀⠀⠛⠛⣿⣿⣿⡛⠿⠷')
            await self.send_chat_message('⠀⠀⠀⠀⠀⠘⠿⠿⠋⠀⠀⠀⠀⠀⠀⣿⣿⣿⠇')
            await self.send_chat_message('⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠁')
            await self.send_chat_message('')
            await self.send_chat_message('⠀⠀⠀⠀⣿⣷⣄⠀⢶⣶⣷⣶⣶⣤⣀')
            await self.send_chat_message('⠀⠀⠀⠀⣿⣿⣿⠀⠀⠀⠀⠀⠈⠙⠻⠗')
            await self.send_chat_message('⠀⠀⠀⣰⣿⣿⣿⠀⠀⠀⠀⢀⣀⣠⣤⣴⣶⡄')
            await self.send_chat_message('⠀⣠⣾⣿⣿⣿⣥⣶⣶⣿⣿⣿⣿⣿⠿⠿⠛⠃')
            await self.send_chat_message('⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄')
            await self.send_chat_message('⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡁')
            await self.send_chat_message('⠈⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠁')
            await self.send_chat_message('⠀⠀⠛⢿⣿⣿⣿⣿⣿⣿⡿⠟')
            await self.send_chat_message('⠀⠀⠀⠀⠀⠉⠉⠉')

    async def process_redemption(self, response):
        reward_id = response['data']['redemption']['reward']['id']
        username = response['data']['redemption']['user']['display_name']
        if reward_id == TTS_REWARD_ID:
            text = response['data']['redemption']['user_input']
            self.tts.save_to_file(f'{username} has redeemed Text to Speech, saying {text}', f'tts_sounds\\tts-{self.num_tts_redemptions}.wav')
            self.tts.runAndWait()
            self.num_tts_redemptions += 1
        elif reward_id == QUACK_ID:
            play_sound_effect('quack')
        elif reward_id == BIG_QUACK_ID:
            play_sound_effect('many_quack')
        elif reward_id == BAN_REWARD_ID:
            await self.ban_user(username)
        
    def tts_sound_check(self):
        files = os.listdir('tts_sounds')
        if files and not self.is_speaking.value:
            self.is_speaking.value = True
            self.tts_process = Process(target=play_next_tts, args=(self.num_tts_read, self.is_speaking))
            self.tts_process.start()
            
    async def ban_user(self, username):
        await self.send_chat_message(f'@{username} has chosen death. Good riddance.')
        await self.send_command(f'/ban {username}')
        with open(BAN_FILE, 'a') as file:
            file.write(f'{username}\n')

    async def unban_users(self):
        with open(BAN_FILE) as file:
            for username in file:
                await self.send_command(f'/unban {username}')
        os.remove(BAN_FILE)
        with open(BAN_FILE, 'w') as _:
            pass


    async def loop(self):
        while True:
            await self.heartbeat_pubsub()
            await self.receive_pubsub()
            await self.recieve_irc(self.command_connection)
            await self.recieve_irc(self.chat_connection, True)
            self.tts_sound_check()

def play_sound_effect(filename):
    sound_file = f'sound_effects\\{filename}.wav'
    Process(target=playsound.playsound, args=(sound_file,)).start()

def play_next_tts(num_tts_read, is_speaking):
    next_file = f'tts_sounds\\tts-{num_tts_read.value}.wav'
    while is_speaking.value:
        try:
            playsound.playsound(next_file)
            num_tts_read.value += 1
            is_speaking.value = False
            return
        except playsound.PlaysoundException:
            continue

def keyboard_break(bot):
    print('Skipping')
    try:
        bot.sound_process.terminate()
        bot.num_tts_read.value += 1
        bot.is_speaking.value = False
    except Exception:
        print('Nothing to skipo')

async def main():
    client = Bot()
    keyboard.add_hotkey('ctrl+alt+1', lambda: keyboard_break(client))
    await client.connect_pubsub()
    await client.connect_chatbot()
    await client.connect_command()
    await client.unban_users()
    await client.loop()

if __name__ == "__main__":
    if not os.path.isdir('tts_sounds'):
        os.mkdir('tts_sounds')
    if not os.path.isdir('bans'):
        os.mkdir('bans')
    if not os.path.isfile(BAN_FILE):
        with open(BAN_FILE, 'w') as _:
            pass
    for name in os.listdir('tts_sounds'):
        os.remove(f'tts_sounds\\{name}')
    asyncio.run(main())