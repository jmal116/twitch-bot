import websockets
import asyncio
import uuid
import json
import requests
import random

class Bot:

    def __init__(self):
        self.client_id = 'lil5xkerbfl7lsj2pk1qhvgsi8fro4'
        self.client_secret = 'm33z33z1d60n67n2kev7iw54foo6db'
        self.connection = None

        self.auth_token = requests.post('https://id.twitch.tv/oauth2/token',
        params={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }).json()['access_token']
        print('Successfully acquired app access token')

        self.channel_id = requests.get('https://api.twitch.tv/helix/users',
        headers={
            'Client-Id': self.client_id,
            'Authorization': f'Bearer {self.auth_token}'
        },
        params={
            'login': 'jmal116'
        }).json()['data'][0]['id']
        print('Successfully fetched channel id')
        
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
            message = {"type": "LISTEN", "nonce": str(self.generate_nonce()), "data":{"topics": self.topics, "auth_token": self.auth_token}}
            json_message = json.dumps(message)
            await self.sendMessage(json_message)

    def generate_nonce(self):
        '''Generate pseudo-random number and seconds since epoch (UTC).'''
        nonce = uuid.uuid1()
        oauth_nonce = nonce.hex
        return oauth_nonce

    async def sendMessage(self, message):
        '''Sending message to webSocket server'''
        await self.connection.send(message)

    async def receiveMessage(self):
        '''Receiving all server messages and handling them'''
        while True:
            try:
                message = await self.connection.recv()
                print('Received message from server: ' + str(message))
            except websockets.exceptions.ConnectionClosed:
                print('Connection with server closed')
                break

    async def heartbeat(self):
        '''
        Sending heartbeat to server every 1 minutes
        Ping - pong messages to verify/keep connection is alive
        '''
        data_set = {"type": "PING"}
        json_request = json.dumps(data_set)
        while True:
            try:
                await self.connection.send(json_request)
                jitter = random.randint(1, 5)
                await asyncio.sleep(60 + jitter)
            except websockets.exceptions.ConnectionClosed:
                print('Connection with server closed')
                break

if __name__ == "__main__":
    client = Bot()
    loop = asyncio.get_event_loop()
    # Start connection and get client connection protocol
    loop.run_until_complete(client.connect())
    # Start listener and heartbeat
    tasks = [
        asyncio.ensure_future(client.heartbeat()),
        asyncio.ensure_future(client.receiveMessage()),
    ]

    loop.run_until_complete(asyncio.wait(tasks))