import asyncio
import uuid
import json
import random
from datetime import datetime, timedelta
import webbrowser
import os
from multiprocessing import Process, Value

import websockets
import requests
import keyboard
import pyttsx3
import playsound

TTS_REWARD_ID = '259c7354-82f7-4d5b-90c7-d85a1434ddac'
BAN_REWARD_ID = '7cda13cb-d15d-4652-89ac-a492b39d42a9'

class Bot:

    def __init__(self):
        self.client_id = 'lil5xkerbfl7lsj2pk1qhvgsi8fro4'
        self.client_secret = 'm33z33z1d60n67n2kev7iw54foo6db'
        self.connection = None
        self.next_ping = datetime.now()
        self.tts = pyttsx3.init()
        self.tts.setProperty('rate', 150)
        self.num_tts_redemptions = 0
        self.num_tts_read = Value('i', 0)
        self.is_speaking = Value('b', False)
        self.sound_process = None

        #Get an app access token
        self.auth_token = requests.post('https://id.twitch.tv/oauth2/token',
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
            'Authorization': f'Bearer {self.auth_token}'
        },
        params={
            'login': 'jmal116'
        }).json()['data'][0]['id']
        print('Successfully fetched channel id')

        #Get authorization code from user
        print('Paste code from the URL you were redirected to:\n')
        webbrowser.open(r'https://id.twitch.tv/oauth2/authorize?client_id=lil5xkerbfl7lsj2pk1qhvgsi8fro4&response_type=code&redirect_uri=http%3A%2F%2Flocalhost&scope=channel:read:redemptions')
        temp_code = input()

        resp = requests.post('https://id.twitch.tv/oauth2/token',
        params={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': temp_code,
            'redirect_uri': 'http://localhost'
        }).json()
        self.user_token = resp['access_token']
        self.refresh_token = resp['refresh_token']

    async def connect(self):
        '''
           Connecting to webSocket server
           websockets.client.connect returns a WebSocketClientProtocol, which is used to send and receive messages
        '''
        topics = [f"channel-points-channel-v1.{self.channel_id}"]
        self.connection = await websockets.client.connect('wss://pubsub-edge.twitch.tv')
        if self.connection.open:
            print('Connection stablished. Client correcly connected')
            # Send greeting
            message = {"type": "LISTEN", "nonce": str(self.generate_nonce()), "data":{"topics": topics, "auth_token": self.user_token}}
            await self.sendMessage(message)

    def generate_nonce(self):
        '''Generate pseudo-random number and seconds since epoch (UTC).'''
        nonce = uuid.uuid1()
        oauth_nonce = nonce.hex
        return oauth_nonce

    async def refresh(self):
        resp = requests.post('https://id.twitch.tv/oauth2/token--data-urlencode',
        params={
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }).json()
        self.refresh_token = resp['refresh_token']
        self.user_token = resp['access_token']

    async def sendMessage(self, message):
        '''Sending message to webSocket server'''
        json_message = json.dumps(message)
        print(f'Sending to server: {message}')
        try:
            await self.connection.send(json_message)
        except websockets.exceptions.ConnectionClosed:
            print('Connection with server closed, retrying')
            await self.connect()
        

    async def receiveMessage(self):
        '''Receiving all server messages and handling them'''
        try:
            message = json.loads(await asyncio.wait_for(self.connection.recv(), 1))
            print(f'Received message from server: {message}')
            if message['type'] == 'RECONNECT':
                print('Reconnect message recieved, doing it')
                self.connection.close()
                await self.connect()
            if message['type'] == 'MESSAGE':
                self.process_redemption(json.loads(message['data']['message']))
        except asyncio.exceptions.TimeoutError:
            return
        except websockets.exceptions.ConnectionClosed:
            print('Connection with server closed, retrying')
            await self.connect()
            return

    async def heartbeat(self):
        '''
        Sending heartbeat to server every 1 minutes
        Ping - pong messages to verify/keep connection is alive
        '''
        if self.next_ping < datetime.now():
            data_set = {"type": "PING"}
            await self.sendMessage(data_set)
            self.next_ping = datetime.now() + timedelta(seconds=60 + random.randint(1, 5))

    def process_redemption(self, response):
        if response['data']['redemption']['reward']['id'] == TTS_REWARD_ID:
            username = response['data']['redemption']['user']['display_name']
            text = response['data']['redemption']['user_input']
            self.tts.save_to_file(f'{username} has redeemed Text to Speech, saying {text}', f'tts_sounds\\tts-{self.num_tts_redemptions}.wav')
            self.tts.runAndWait()
            self.num_tts_redemptions += 1
        #TODO bans
        
    def sound_check(self):
        files = os.listdir('tts_sounds')
        if files and not self.is_speaking.value:
            self.is_speaking.value = True
            self.sound_process = Process(target=play_next_sound, args=(self.num_tts_read, self.is_speaking))
            self.sound_process.start()

    async def loop(self):
        while True:
            await self.heartbeat()
            await self.receiveMessage()
            self.sound_check()

def play_next_sound(num_tts_read, is_speaking):
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
    await client.connect()
    await client.loop()

if __name__ == "__main__":
    for name in os.listdir('tts_sounds'):
        os.remove(f'tts_sounds\\{name}')
    asyncio.run(main())