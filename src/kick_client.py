import json
import logging
import time
import requests
import pysher

# Kick's public pusher key
KICK_PUSHER_KEY = '32cbd69e4b950bf97679'
KICK_PUSHER_CLUSTER = 'us2'

logger = logging.getLogger(__name__)

class KickClient:
    def __init__(self, username, on_gift_sub_callback, on_reward_callback=None, on_kicks_callback=None, on_tts_callback=None, tts_allowed_badges=("vip",), on_connection_state_callback=None):
        self.username = username
        self.on_gift_sub_callback = on_gift_sub_callback
        self.on_reward_callback = on_reward_callback
        self.on_kicks_callback = on_kicks_callback
        self.on_tts_callback = on_tts_callback
        self.on_connection_state_callback = on_connection_state_callback
        self.tts_allowed_badges = tts_allowed_badges  # None = anyone, tuple/list = badge required
        self.chatroom_id = None
        self.channel_id = None
        self.pusher = None

    def fetch_chatroom_id(self):
        url = f"https://kick.com/api/v2/channels/{self.username}"
        headers = {
            # Provide a user-agent to avoid basic blocks
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            self.chatroom_id = data.get("chatroom", {}).get("id")
            self.channel_id = data.get("id")
            if not self.chatroom_id:
                raise ValueError("Chatroom ID not found in response")
            if not self.channel_id:
                raise ValueError("Channel ID not found in response")
            logger.info(f"Successfully fetched IDs for {self.username}: channel={self.channel_id}, chatroom={self.chatroom_id}")
        except Exception as e:
            logger.error(f"Failed to fetch chatroom ID: {e}")
            raise

    def connect(self):
        if not self.chatroom_id:
            self.fetch_chatroom_id()

        self.pusher = pysher.Pusher(
            key=KICK_PUSHER_KEY,
            cluster=KICK_PUSHER_CLUSTER,
            secure=True
        )

        self.pusher.connection.bind('pusher:connection_established', self._on_connection_established)
        self.pusher.connection.bind('pusher:error', self._on_error)
        
        logger.info("Connecting to Kick Pusher...")
        self.pusher.connect()

    def _on_connection_established(self, data):
        logger.info("Pusher Connection established!")
        if self.on_connection_state_callback:
            try:
                self.on_connection_state_callback(True)
            except Exception as e:
                logger.error(f"Connection state callback error: {e}")
        chatroom_channel_name = f'chatrooms.{self.chatroom_id}.v2'
        self.chatroom_channel = self.pusher.subscribe(chatroom_channel_name)
        self.chatroom_channel.bind('App\\Events\\ChatMessageEvent', self._on_chat_message)

        chatroom_channel_v1 = f'chatroom_{self.chatroom_id}'
        self.chatroom_channel_v1 = self.pusher.subscribe(chatroom_channel_v1)
        self.chatroom_channel_v1.bind('GiftedSubscriptionsEvent', self._on_gift_sub)
        self.chatroom_channel_v1.bind('RewardRedeemedEvent', self._on_reward_redeemed)

        channel_channel = f'channel_{self.channel_id}'
        self.channel_channel = self.pusher.subscribe(channel_channel)
        self.channel_channel.bind('KicksGifted', self._on_kicks_gifted)

    def _on_error(self, data):
        logger.error(f"Pusher error: {data}")
        if self.on_connection_state_callback:
            try:
                self.on_connection_state_callback(False)
            except Exception as e:
                logger.error(f"Connection state callback error: {e}")

    def _parse_event(self, data):
        return json.loads(data) if isinstance(data, str) else data

    def _on_chat_message(self, data):
        try:
            event_data = self._parse_event(data)
            sender = event_data.get('sender', {})
            username = sender.get('username', 'unknown')
            content = event_data.get('content', '')
            logger.info(f"[chat] {username}: {content}")

            if content.startswith('!tts ') and self.on_tts_callback:
                if self.tts_allowed_badges is None:
                    allowed = True
                else:
                    badges = sender.get('identity', {}).get('badges', [])
                    allowed = any(b.get('type') in self.tts_allowed_badges for b in badges)
                if allowed:
                    tts_text = content[5:].strip()
                    if tts_text:
                        logger.info(f"TTS command from {username}: {tts_text}")
                        self.on_tts_callback(tts_text)
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")

    def _on_kicks_gifted(self, data):
        try:
            event_data = self._parse_event(data)
            username = event_data.get('sender', {}).get('username', 'Someone')
            gift = event_data.get('gift', {})
            gift_name = gift.get('name', 'a Kick')
            amount = gift.get('amount', 1)
            logger.info(f"Kick gifted! User: {username}, Gift: {gift_name} x{amount}")
            if self.on_kicks_callback:
                self.on_kicks_callback(username, gift_name, amount)
        except Exception as e:
            logger.error(f"Error handling KicksGifted event: {e}")

    def _on_reward_redeemed(self, data):
        try:
            event_data = self._parse_event(data)
            username = event_data.get('username', 'Someone')
            reward_title = event_data.get('reward_title', 'Reward')
            logger.info(f"Reward redeemed! User: {username}, Reward: {reward_title}")
            if self.on_reward_callback:
                self.on_reward_callback(username, reward_title)
        except Exception as e:
            logger.error(f"Error handling reward redeemed event: {e}")

    def _on_gift_sub(self, data):
        try:
            event_data = self._parse_event(data)
            gifter_username = event_data.get('gifter_username', 'Someone')
            gifted_usernames = event_data.get('gifted_usernames', [])
            num_subs = len(gifted_usernames)
            logger.info(f"Gift sub event! Gifter: {gifter_username}, Count: {num_subs}")
            if self.on_gift_sub_callback:
                self.on_gift_sub_callback(gifter_username, num_subs)
        except Exception as e:
            logger.error(f"Error handling gift sub event: {e}")
