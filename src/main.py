import os
import sys
import time
import logging
import queue
from dotenv import load_dotenv

from kick_client import KickClient
from display_manager import DisplayManager
from logger import setup_logging
from tts_player import TTSPlayer

logger = logging.getLogger('WhisplayKickApp')

def main():
    load_dotenv()
    setup_logging()
    # Called again after connect so pysher's loggers (created during connect) are also silenced
    
    username = os.getenv("KICK_USERNAME")
    if not username or username == "your_kick_username_here":
        logger.error("Please set KICK_USERNAME in your .env file")
        sys.exit(1)
        
    logger.info(f"Starting Whisplay Kick Alerter for user: {username}")
    
    display_manager = DisplayManager()
    tts_player = TTSPlayer()
    alert_queue = queue.Queue()
    reward_queue = queue.Queue()
    tts_queue = queue.Queue()

    def on_gift_sub(gifter_username, count):
        logger.info(f"Queuing alert: {gifter_username} gifted {count} subs!")
        alert_queue.put((gifter_username, count))

    def on_reward_redeemed(username, reward_title):
        logger.info(f"Queuing reward alert: {username} redeemed {reward_title}")
        reward_queue.put((username, reward_title))

    kicks_queue = queue.Queue()

    def on_kicks_gifted(username, gift_name, amount):
        logger.info(f"Queuing kicks alert: {username} gifted {gift_name} x{amount}")
        kicks_queue.put((username, gift_name, amount))

    def on_tts_command(text):
        logger.info(f"Queuing TTS: {text}")
        tts_queue.put(text)

    client = KickClient(username, on_gift_sub, on_reward_callback=on_reward_redeemed, on_kicks_callback=on_kicks_gifted, on_tts_callback=on_tts_command)
    
    try:
        client.connect()
        setup_logging()
        logger.info("Application is running. Waiting for events...")
        
        last_button_state = False
        
        while True:
            # Poll hardware button for simulation test directly
            if display_manager.board:
                current_button_state = display_manager.board.button_pressed()
                if current_button_state and not last_button_state:
                    logger.info("Hardware button pressed! Simulating a gift sub alert.")
                    alert_queue.put(("TestUser", 5))
                last_button_state = current_button_state

            # Process any queued alerts
            try:
                gifter, count = alert_queue.get_nowait()
                logger.info(f"Processing alert: {gifter} gifted {count} subs!")
                display_manager.trigger_alert(gifter, count)
                if display_manager.board:
                    last_button_state = display_manager.board.button_pressed()
                alert_queue.task_done()
            except queue.Empty:
                pass

            try:
                username, reward_title = reward_queue.get_nowait()
                logger.info(f"Processing reward alert: {username} redeemed {reward_title}")
                display_manager.trigger_reward_alert(username, reward_title)
                if display_manager.board:
                    last_button_state = display_manager.board.button_pressed()
                reward_queue.task_done()
            except queue.Empty:
                pass

            try:
                username, gift_name, amount = kicks_queue.get_nowait()
                logger.info(f"Processing kicks alert: {username} gifted {gift_name} x{amount}")
                display_manager.trigger_kicks_alert(username, gift_name, amount)
                if display_manager.board:
                    last_button_state = display_manager.board.button_pressed()
                kicks_queue.task_done()
            except queue.Empty:
                pass

            try:
                tts_text = tts_queue.get_nowait()
                logger.info(f"Processing TTS: {tts_text}")
                tts_player.speak_async(tts_text)
                tts_queue.task_done()
            except queue.Empty:
                pass

            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        display_manager.cleanup()

if __name__ == "__main__":
    main()
