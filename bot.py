import asyncio
import uuid
import json
import random
from datetime import datetime, timedelta
import webbrowser

import websockets
import requests
import keyboard

class Bot:

    def __init__(self):
        self.client_id = 'lil5xkerbfl7lsj2pk1qhvgsi8fro4'
        self.client_secret = 'm33z33z1d60n67n2kev7iw54foo6db'
        self.connection = None
        self.should_exit = False
        self.next_ping = datetime.now()

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

        # list of topics to subscribe to
        self.topics = [f"channel-points-channel-v1.{self.channel_id}"]

    async def connect(self):
        '''
           Connecting to webSocket server
           websockets.client.connect returns a WebSocketClientProtocol, which is used to send and receive messages
        '''
        self.connection = await websockets.client.connect('wss://pubsub-edge.twitch.tv')
        if self.connection.open:
            print('Connection stablished. Client correcly connected')
            # Send greeting
            message = {"type": "LISTEN", "nonce": str(self.generate_nonce()), "data":{"topics": self.topics, "auth_token": self.user_token}}
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

    async def loop(self):
        while not self.should_exit:
            await self.heartbeat()
            await self.receiveMessage()


def keyboard_break(bot):
    print('Exiting')
    bot.should_exit = True

async def main():
    client = Bot()
    keyboard.add_hotkey('ctrl+alt+1', lambda: keyboard_break(client))
    await client.connect()
    await client.loop()

if __name__ == "__main__":
    asyncio.run(main())