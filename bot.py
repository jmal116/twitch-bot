import asyncio
import json
import os
import random
import re
import sys
import time
import webbrowser
from collections import namedtuple
from datetime import datetime, timedelta
from multiprocessing import Process, Value
from pathlib import Path
import shutil
import glob

import keyboard
import playsound
import pyttsx3
import requests
import websockets

TTS_REWARD_ID = '259c7354-82f7-4d5b-90c7-d85a1434ddac'
BAN_REWARD_ID = '7cda13cb-d15d-4652-89ac-a492b39d42a9'
QUACK_ID = 'e0f41bbb-7c09-4767-91e3-f586438ee411'
BIG_QUACK_ID = '5e12b9ef-b5ae-448f-ac11-3caa5607531b'
GOT_EM_ID = "76f82a23-63a6-4799-906c-0d1cd6c1df3e"
WHOMSTDVE_ID = "9b42cebf-0958-416b-b712-5749326231eb"
GROUND_REWARD_ID = "3bf0310b-4182-4673-9977-c1531650cc49"
VINE_BOOM_REWARD_ID = "5e9adf48-6df6-4e02-8e39-fe9e7535e7c4"
CHRISTMAS_ID = "4a10ec1c-8c3f-42cb-bd6f-20bda8b37d3e"
ADD_EXP_ID = 'c8432ff9-3675-425d-85e5-1a867a39c861'
REMOVE_EXP_ID = '986d744d-5a72-407f-8952-4aa809718a1e'

MINECRAFT_GAME_ID = '27471'

EXP_FILE_NAME = Path("E:\SteamLibrary\steamapps\common\Ori DE\ExpNames.txt")
STARTING_EXP_FILE_NAME = Path('current_exp_names.txt')
CHATLOG_FOLDER = Path('chatlogs')
TTS_FOLDER = Path('tts_sounds')
BANS_FOLDER = Path('bans')
BAN_FILE = str(BANS_FOLDER / 'bans.txt')

ChatMessage = namedtuple('ChatMessage', ['user', 'message', 'command'])

class Bot:

    def __init__(self, chatlog_file, restream_link=None):
        self.client_id = 'lil5xkerbfl7lsj2pk1qhvgsi8fro4'
        self.client_secret = 'm33z33z1d60n67n2kev7iw54foo6db'
        self.pubsub_connection = None
        self.eventsub_id = None
        self.chat_connection = None
        self.conor_chat = None
        self.next_ping = datetime.now()
        self.tts = pyttsx3.init()
        self.tts.setProperty('volume', 1.5)
        self.tts.setProperty('rate', 150)
        self.num_tts_redemptions = 0
        self.num_tts_read = Value('i', 0)
        self.is_speaking = Value('b', False)
        self.tts_process = None
        self.next_reminder = datetime.now()
        self.chatlog_file = chatlog_file
        self.bot_chatlog_name = '####JMAL116_CHATBOT####'
        if restream_link is not None:
            self.do_reminder = True
            self.restream_link = restream_link
        else:
            self.do_reminder = False
            self.restream_link = None

        self.relic_emotes = [
            'CoolCat'
            ,'jmal11HideBash'
            ,'jmal11DustyStick'
            ,'jmal11GG'
            ,'PizzaTime'
            ,'Lechonk'
            ,'MrDestructoid'
            ,'BOP'
            ,'TwitchSings'
            ,'PixelBob'
            ,'PopCorn'
            ,'TheIlluminati'
            ,'DoritosChip'
            ,'OhMyDog'
            ,'SSSsss'
        ]


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
            headers=self._format_api_headers(),
            params={
                'login': 'jmal116'
            }
        ).json()['data'][0]['id']
        print('Successfully fetched channel id')

        # print('Paste code for the chatbot account:\n')
        # self.chatbot_token, _ = self.get_user_tokens()
        print('Paste code for the main channel:\n')
        self.user_token, self.refresh_token = self.get_user_tokens()
        self.chatbot_token = self.user_token

    def _format_api_headers(self, use_auth=False):
        default = {
            'Client-Id': self.client_id,
            'Authorization': f'Bearer {self.user_token if use_auth else self.app_access_token}',
            'Content-Type': 'application/json'
        }
        return default

    def get_user_tokens(self):
        webbrowser.open(r'https://id.twitch.tv/oauth2/authorize?client_id=lil5xkerbfl7lsj2pk1qhvgsi8fro4&response_type=code&redirect_uri=http%3A%2F%2Flocalhost&force_verify=false&scope=channel:read:redemptions%20channel:moderate%20chat:edit%20chat:read%20moderator:manage:banned_users%20channel:manage:redemptions')
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
        self.pubsub_connection = await websockets.client.connect('wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds=600')
        message = json.loads(await self.pubsub_connection.recv())
        self.eventsub_id = message['payload']['session']['id']
        event_response = requests.post('https://api.twitch.tv/helix/eventsub/subscriptions',
            headers=self._format_api_headers(use_auth=True),
            data=json.dumps({
                'type': 'channel.channel_points_custom_reward_redemption.add',
                'version': 1,
                'condition': {'broadcaster_user_id': self.channel_id},
                'transport': {
                    'method': 'websocket',
                    'session_id': self.eventsub_id
                }
            })
        ).json()
        # print(event_response)
        print('event sub connection established')

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

    async def connect_conor(self):
        self.conor_chat = await websockets.client.connect('wss://irc-ws.chat.twitch.tv:443')
        if self.conor_chat.open:
            print('conor connection established.')
            await self.send_irc(f'PASS oauth:{self.user_token}', self.conor_chat)
            await self.recieve_irc(self.conor_chat)
            await self.send_irc('NICK jmal116', self.conor_chat)
            await self.recieve_irc(self.conor_chat)
            await self.send_irc('JOIN #wespr_', self.conor_chat)

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
            message_type = message['metadata']['message_type']
            if message_type == 'session_reconnect':
                print('pubsub reconnect message recieved, doing it')
                old_conn = self.pubsub_connection
                new_url = message['payload']['session']['reconnect_url']
                self.pubsub_connection = await websockets.client.connect(new_url)
                message = json.loads(await self.pubsub_connection.recv())
                self.eventsub_id = message['payload']['session']['id']
                old_conn.close()
            if message_type == 'notification':
                # print(message)
                await self.process_redemption(message)
        except asyncio.exceptions.TimeoutError:
            return
        except websockets.exceptions.ConnectionClosed:
            print('Connection with pubsub server closed, retrying')
            await self.connect_pubsub()

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
                self.log_chat_message(parsed)
                if parsed.command:
                    await self.process_chat_command(parsed)
                else: 
                    await self.process_plain_chat(parsed)
                
        except asyncio.exceptions.TimeoutError:
            return
        except websockets.exceptions.ConnectionClosed:
            print('Connection with IRC server closed, retrying')
            await self.connect_chatbot()
            await self.connect_command()

    async def send_chat_message(self, message):
        self.log_chat_message(ChatMessage(self.bot_chatlog_name, message, False))
        await self.send_irc(f'PRIVMSG #jmal116 :{message}', self.chat_connection)

    async def send_conor_message(self, message):
        await self.send_irc(f'PRIVMSG #wespr_ :{message}', self.conor_chat)

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
        if self.do_reminder:
            return
        cmd = message.command
        if cmd == 'thonk':
            await self.send_chat_message('⠀⠰⡿⠿⠛⠛⠻⠿⣷')
            await self.send_chat_message('⠀⠀⠀⠀⠀⠀⣀⣄⡀⠀⠀⠀⠀⢀⣀⣀⣤⣄⣀⡀')
            await self.send_chat_message('⠀⠀⠀⠀⠀⢸⣿⣿⣷⠀⠀⠀⠀⠛⠛⣿⣿⣿⡛⠿⠷')
            await self.send_chat_message('⠀⠀⠀⠀⠀⠘⠿⠿⠋⠀⠀⠀⠀⠀⠀⣿⣿⣿⠇')
            await self.send_chat_message('⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠁')
            await self.send_chat_message('⠀⠀⠀⠀⣿⣷⣄⠀⢶⣶⣷⣶⣶⣤⣀')
            await self.send_chat_message('⠀⠀⠀⠀⣿⣿⣿⠀⠀⠀⠀⠀⠈⠙⠻⠗')
            await self.send_chat_message('⠀⠀⠀⣰⣿⣿⣿⠀⠀⠀⠀⢀⣀⣠⣤⣴⣶⡄')
            await self.send_chat_message('⠀⣠⣾⣿⣿⣿⣥⣶⣶⣿⣿⣿⣿⣿⠿⠿⠛⠃')
            await self.send_chat_message('⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄')
            await self.send_chat_message('⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡁')
            await self.send_chat_message('⠈⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠁')
            await self.send_chat_message('⠀⠀⠛⢿⣿⣿⣿⣿⣿⣿⡿⠟')
            await self.send_chat_message('⠀⠀⠀⠀⠀⠉⠉⠉')
        elif cmd == 'seed':
            await self.send_current_seed()
        elif cmd == 'relic':
            await self.send_relic_get_chat()
        else:
            responses = {
                'furnace': r'https://www.twitch.tv/videos/452470158',
                'youtube': r'Youtube: https://www.youtube.com/@jmal116    Twitter: https://twitter.com/jmal116',
                'twitter': r'Youtube: https://www.youtube.com/@jmal116    Twitter: https://twitter.com/jmal116',
                'socials': r'Youtube: https://www.youtube.com/@jmal116    Twitter: https://twitter.com/jmal116',
                'worstseed': r'https://orirando.com/?param_id=5142336589791232', # Required logical progression: cjump + climb + glide + stomp + sunstone -> clean water in L2 -> base in swamp swim -> WV MS7, with 8 available mapstones. Notable mapstones include vanilla SS, forlorn escape, LGLS, VLS, DG underwater energy door 
                'badseeds': r'https://orirando.com/?param_id=5142336589791232' r'https://orirando.com/?param_id=5113274911686656 https://orirando.com/?param_id=6260102851985408 https://orirando.com/?param_id=5120055155097600'
            }
            to_send = responses.get(cmd, None)
            if to_send is not None:
                await self.send_chat_message(to_send)

    async def send_relic_get_chat(self):
        chosen = random.choice(self.relic_emotes)
        composed = f' {chosen} '.join('RELICGET')
        await self.send_chat_message(f'{chosen} {composed} {chosen}')

    async def send_current_seed(self):
        with open('./current_seed.txt') as file:
            url = file.readline()
        await self.send_chat_message(url)

    async def process_plain_chat(self, message: ChatMessage):
        if self.should_auto_ban(message):
            self.log_chat_message(ChatMessage(self.bot_chatlog_name, f'AUTO BANNING {message.user}', False))
            await self.ban_user(message.user, should_unban=False)
            return
        if self.do_reminder:
            return
        if "so brave" in message.message.lower():
            await self.send_chat_message('So soggy!')
        if "bad water" in message.message.lower():
            await self.send_chat_message('Sad water!')
        if self.is_relic_chat(message):
            await self.send_relic_get_chat()

    def should_auto_ban(self, message: ChatMessage):
        if 'boostprox.online' in message.message.replace(' ', ''): return True
        if 'streamboo.live' in message.message.replace(' ', ''): return True
        if 'streamboo.com' in message.message.replace(' ', ''): return True
        try:
            is_unicode = not all(ord(c) < 128 for c in message.message)
            return ('.com' in message.message or '.ru' in message.message or '.net' in message.message) and is_unicode
        except Exception as e:
            self.log_error_message(f'{e.__class__} deciding to ban a user, you should look at that')
    
    def log_chat_message(self, message: ChatMessage):
        try:
            with open(self.chatlog_file, 'a', encoding='utf-8') as file:
                file.write(f'{datetime.now().strftime("%H:%M:%S")} {message.user}: {message.message}\n')
        except:
            with open(self.chatlog_file, 'a', encoding='utf-8') as file:
                file.write(f'{datetime.now().strftime("%H:%M:%S")} ERROR LOGGING MESSAGE\n')

    def log_error_message(self, message: str):
        with open(self.chatlog_file, 'a', encoding='utf-8') as file:
            file.write(f'{datetime.now().strftime("%H:%M:%S")} ERROR!!!! {message}\n')

    def is_relic_chat(self, message: ChatMessage):
        chosen = None
        for emote in self.relic_emotes:
            if emote in message.message:
                chosen = emote
                break
        if chosen is None:
            return False
        
        reduced: str = message.message.replace(chosen, '')
        reduced = reduced.replace(' ', '')
        return reduced.upper() == 'RELICGET'

    def throw_on_ground(self):
        game_id =  requests.get('https://api.twitch.tv/helix/channels',
            headers=self._format_api_headers(),
            params={
                'broadcaster_id': self.channel_id
            }
        ).json()['data'][0]['game_id']
        Process(target=throw_on_ground_helper, args=(game_id == MINECRAFT_GAME_ID,)).start()

    def add_exp_name(self, name):
        with open(STARTING_EXP_FILE_NAME, 'a') as file:
            file.write(f'{name}\n') 
        shutil.copyfile(STARTING_EXP_FILE_NAME, EXP_FILE_NAME)

    async def remove_exp_name(self, name: str, redemption_id, username):
        name_comp = name.upper().strip()
        with open(STARTING_EXP_FILE_NAME, 'r') as file:
            lines = file.readlines()
        lines_comp = [line.upper().strip() for line in lines]
        if name_comp in lines_comp:
            with open(STARTING_EXP_FILE_NAME, 'w') as file:
                for line, line_comp in zip(lines, lines_comp):
                    if name_comp != line_comp:
                        file.write(line)
            shutil.copyfile(STARTING_EXP_FILE_NAME, EXP_FILE_NAME)
            is_complete = True
        else:
            is_complete = False

        resp = requests.patch(r'https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions',          
            headers=self._format_api_headers(use_auth=True),
            params={
                'broadcaster_id': self.channel_id,
                'id': redemption_id,
                'reward_id': REMOVE_EXP_ID
            },
            json= {
                'status': 'FULFILLED' if is_complete else 'CANCELED'
            }
        )
        # print(resp.json())
        if not is_complete:
            await self.send_chat_message(f'@{username} that experience name isn\'t in the list!')

    async def process_redemption(self, response):
        if self.do_reminder:
            return
        event = response['payload']['event']
        reward_id = event['reward']['id']
        user_id = event['user_id']
        username = event['user_name']
        if reward_id == TTS_REWARD_ID:
            text = event['user_input']
            self.tts.save_to_file(f'{username} has redeemed Text to Speech, saying {text}', f'{str(TTS_FOLDER)}\\tts-{self.num_tts_redemptions}.wav')
            self.tts.runAndWait()
            self.num_tts_redemptions += 1
        elif reward_id == QUACK_ID:
            play_sound_effect('quack')
        elif reward_id == BIG_QUACK_ID:
            play_sound_effect('many_quack')
        elif reward_id == GOT_EM_ID:
            play_sound_effect('gotem')
        elif reward_id == WHOMSTDVE_ID:
            play_sound_effect('whomstdve')
        elif reward_id == BAN_REWARD_ID:
            await self.ban_user(username, user_id)
            play_sound_effect('coffin_dance')
        elif reward_id == GROUND_REWARD_ID:
            self.throw_on_ground()
        elif reward_id == VINE_BOOM_REWARD_ID:
            Process(target=random_vine_boom, args=(random.randint(60, 5*60),)).start()
        elif reward_id == CHRISTMAS_ID:
            if random.choice([1, 0]) == 1:
                play_sound_effect('defy_gravity')
            else:
                play_sound_effect('mariah_carey')
        elif reward_id == ADD_EXP_ID:
            self.add_exp_name(event['user_input'])
        elif reward_id == REMOVE_EXP_ID:
            await self.remove_exp_name(event['user_input'], event['id'], username)
        
    def tts_sound_check(self):
        files = os.listdir(str(TTS_FOLDER))
        if files and not self.is_speaking.value:
            self.is_speaking.value = True
            self.tts_process = Process(target=play_next_tts, args=(self.num_tts_read, self.is_speaking))
            self.tts_process.start()
            
    async def ban_user(self, username, user_id=None, should_unban=True):
        reasons = [
            '@{username} has chosen death. Good riddance. ¯\_(ツ)_/¯',
            '@{username} girlbossed too close to the sun',
            'Was it really worth it, @{username}?',
            '@{username} played stupid games and won stupid prizes',
            '@{username} failed the FitnessGram™ Pacer Test',
        ]
        reason = random.choice(reasons).format(username=username)
        if should_unban: await self.send_chat_message(reason)

        if user_id is None:
            user_id = requests.get('https://api.twitch.tv/helix/users',
                headers=self._format_api_headers(),
                params={
                    'login': username
                }
            ).json()['data'][0]['id']
        # print(f'username: {username}, user_id: {user_id}')

        resp = requests.post(r'https://api.twitch.tv/helix/moderation/bans',          
            headers=self._format_api_headers(use_auth=True),
            params={
                'broadcaster_id': self.channel_id,
                'moderator_id': self.channel_id
            },
            json= {
                'data': {
                    'user_id': user_id,
                    'reason': reason
                }
            }
        )
        # print(resp.json())
        if should_unban:
            with open(BAN_FILE, 'a') as file:
                file.write(f'{user_id}\n')

    async def unban_users(self):
        with open(BAN_FILE) as file:
            for user_id in file:
                user_id = user_id.strip()
                resp = requests.delete(r'https://api.twitch.tv/helix/moderation/bans',
                    headers=self._format_api_headers(use_auth=True),
                    params={
                        'broadcaster_id': self.channel_id,
                        'moderator_id': self.channel_id,
                        'user_id': user_id
                    }
                )
        os.remove(BAN_FILE)
        with open(BAN_FILE, 'w') as _:
            pass

    async def check_reminder(self):
        if self.do_reminder and self.next_reminder < datetime.now():
            await self.send_chat_message(rf"This game is part of the doubles tournament. I'm not reading chat, have my mic turned off, and have disabled all channel rewards and chatbot features. Watch the race with commentary: {self.restream_link}")
            self.next_reminder = datetime.now() + timedelta(minutes=5)


    async def loop(self):
        while True:
            await self.receive_pubsub()
            await self.recieve_irc(self.command_connection)
            await self.recieve_irc(self.conor_chat)
            await self.recieve_irc(self.chat_connection, True)
            await self.check_reminder()
            self.tts_sound_check()

def throw_on_ground_helper(throw):
    play_sound_effect('ground')
    if throw:
        time.sleep(1.2)
        keyboard.send('t')

def random_vine_boom(delay):
    time.sleep(delay)
    play_sound_effect('vine_boom')

def play_sound_effect(filename):
    sound_file = f'sound_effects\\{filename}.wav'
    Process(target=playsound.playsound, args=(sound_file,)).start()

def play_next_tts(num_tts_read, is_speaking):
    next_file = f'{str(TTS_FOLDER)}\\tts-{num_tts_read.value}.wav'
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

def fuck_with_conor(bot: Bot):
    # pool = [
    #     'uwu',
    #     '🤔',
    #     '( ´･･)ﾉ(._.`)',
    #     '(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧',
    #     '(⌐■_■)',
    #     '( •_•)>⌐■-■',
    #     '( ͡°( ͡° ͜ʖ( ͡° ͜ʖ ͡°)ʖ ͡°) ͡°)',
    #     '¯\_(ツ)_/¯',
    #     '¯\_( ͡° ͜ʖ ͡°)_/¯',
    #     "What the fuck did you just fucking say about me, you little bitch? I'll have you know I graduated top of my class in the Navy Seals, and I've been involved in numerous secret raids on Al-Quaeda, and I have over 300 confirmed kills. I am trained in gorilla warfare and I'm the top sniper in the entire US armed forces. You are nothing to me but just another target. I will wipe you the fuck out with precision the likes of which has never been seen before on this Earth, mark my fucking words. You thi",
    #     'The FitnessGram™ Pacer Test is a multistage aerobic capacity test that progressively gets more difficult as it continues. The 20 meter pacer test will begin in 30 seconds. Line up at the start. The running speed starts slowly, but gets faster each minute after you hear this signal. [beep] A single lap should be completed each time you hear this sound. [ding] Remember to run in a straight line, and run as long as possible. The second time you fail to complete a lap before the sound, your test is over. The test will begin on the word start. On your mark, get ready, start.',
    #     'O-oooooooooo AAAAE-A-A-I-A-U- JO-oooooooooooo AAE-O-A-A-U-U-A- E-eee-ee-eee AAAAE-A-E-I-E-A-JO-ooo-oo-oo-oo EEEEO-A-AAA-AAAA',
    #     "I'm the Scatman Ski-bi dibby dib yo da dub dub Yo da dub dub Ski-bi dibby dib yo da dub dub Yo da dub dub (I'm the Scatman) Ski-bi dibby dib yo da dub dub Yo da dub dub Ski-bi dibby dib yo da dub dub Yo da dub dub Ba-da-ba-da-ba-be bop bop bodda bope Bop ba bodda bope Be bop ba bodda bope Bop ba bodda Ba-da-ba-da-ba-be bop ba bodda bope Bop ba bodda bope Be bop ba bodda bope Bop ba bodda bope Ski-bi dibby dib yo da dub dub",
    #     'Good luck on your rando!',
    #     'jmal11HideBashS',
    # ]
    # choice = random.choice(pool)
    # asyncio.run(bot.send_conor_message(choice[:500]))
    # asyncio.run(bot.send_chat_message(f'Sending message to wespr_: {choice}'[:500]))
    asyncio.run(bot.send_chat_message(r'https://www.tsa.gov/travel/security-screening/whatcanibring/items/live-lobster'))

async def main():
    if len(sys.argv) == 1:
        link = None
    else:
        link = sys.argv[1]

    # chatlog maintenance
    now_obj = datetime.now()
    now = now_obj.strftime('%Y%m%d%H%M%S')
    prefix_len = len(str(CHATLOG_FOLDER)) + 1
    for file in glob.glob(str(CHATLOG_FOLDER / '*.txt')):
        log_date = file[prefix_len : prefix_len + 14]
        log_date = datetime.strptime(log_date, '%Y%m%d%H%M%S')
        if (now_obj - log_date).days > 14:
            os.remove(file)
    chatlog_file = f'chatlogs\\{now}.txt'
    if not os.path.isfile(chatlog_file):
        with open(chatlog_file, 'w') as _:
            pass

    # sanity check
    if not EXP_FILE_NAME.exists():
        raise Exception('ExpNames file not found, make sure directory didn\'t change through some unknown black magic')
    shutil.copyfile(STARTING_EXP_FILE_NAME, EXP_FILE_NAME)

    # The real stuff
    client = Bot(chatlog_file=chatlog_file, restream_link=link)
    keyboard.add_hotkey('ctrl+alt+1', lambda: keyboard_break(client))
    keyboard.add_hotkey('ctrl+alt+backspace', lambda: fuck_with_conor(client))
    await client.connect_pubsub()
    await client.connect_chatbot()
    await client.connect_command()
    await client.connect_conor()
    await client.unban_users()
    await client.loop()

if __name__ == "__main__":
    if not os.path.isdir(str(TTS_FOLDER)):
        os.mkdir(str(TTS_FOLDER))
    if not os.path.isdir(str(BANS_FOLDER)):
        os.mkdir(str(BANS_FOLDER))
    if not os.path.isdir(str(CHATLOG_FOLDER)):
        os.mkdir(str(CHATLOG_FOLDER))
    if not os.path.isfile(BAN_FILE):
        with open(BAN_FILE, 'w') as _:
            pass
    for name in os.listdir(str(TTS_FOLDER)):
        os.remove(str(TTS_FOLDER / name))
    asyncio.run(main())
