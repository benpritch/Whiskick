import json
import os
import sys
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageSequence

# Add driver to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'vendor', 'Whisplay', 'Driver')))

try:
    from WhisPlay import WhisPlayBoard
except ImportError:
    print("Warning: WhisPlay driver not found or could not be loaded. Are you running on the device?")
    WhisPlayBoard = None


KICK_GREEN = (83, 252, 24)
ALERT_DURATION_S = 20.0

# Layout used when a GIF is enabled for an alert.
GIF_BOX_TOP = 50
GIF_BOX_W = 240
GIF_BOX_H = 160
GIF_TEXT_USER_Y = 218
GIF_TEXT_SUB_Y = 250


class DisplayManager:
    def __init__(self):
        self.board = None

        # Assets + config directories
        self.assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
        self.config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'alerts.json')
        self.alert_config = self._load_alert_config()

        if WhisPlayBoard is not None:
            self.board = WhisPlayBoard()

            # Show a boot splash screen so the user knows the driver is working
            print("Showing boot splash screen...")
            self.board.set_backlight(100)
            self.board.set_rgb(0, 0, 255) # Blue LED on boot

            img_data = self._generate_alert_image("System", "Starting Up")
            if img_data:
                self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, img_data)

            time.sleep(2)
            self.board.set_rgb(0, 0, 0)

            # Turn the screen OFF initially since there are no alerts (from user requirement)
            self.board.set_backlight(0)
            self.board.fill_screen(0x0000) # Black screen

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trigger_alert(self, gifter_username, count=1):
        """Show the gift sub alert."""
        if not self.board:
            print(f"[MOCK DISPLAY] Displaying Alert: {gifter_username} gifted {count} subs!")
            return

        print(f"Triggering alert for {gifter_username}...")

        self.board.fill_screen(0x0000)
        self.board.set_backlight(100)
        self._flash_leds()

        subtitle = f"gifted {count} sub{'s' if count != 1 else ''}!"
        if not self._try_play_gif_alert('gift_sub', 'GIFTED SUB!', gifter_username, subtitle):
            img_data = self._generate_alert_image(gifter_username, count)
            if img_data:
                self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, img_data)
            self._wait_for_dismiss()

        self.board.set_backlight(0)

    def trigger_reward_alert(self, username, reward_title):
        if not self.board:
            print(f"[MOCK DISPLAY] Reward Alert: {username} redeemed '{reward_title}'")
            return

        self.board.fill_screen(0x0000)
        self.board.set_backlight(100)
        self._flash_leds()

        if not self._try_play_gif_alert('reward', 'REWARD REDEEMED!', username, reward_title):
            img_data = self._generate_reward_image(username, reward_title)
            if img_data:
                self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, img_data)
            self._wait_for_dismiss()

        self.board.set_backlight(0)

    def trigger_kicks_alert(self, username, gift_name, amount):
        if not self.board:
            print(f"[MOCK DISPLAY] Kicks Alert: {username} gifted {gift_name} x{amount}")
            return

        self.board.fill_screen(0x0000)
        self.board.set_backlight(100)
        self._flash_leds()

        subtitle = f"{gift_name} x{amount}" if amount > 1 else gift_name
        if not self._try_play_gif_alert('kicks', 'KICK GIFTED!', username, subtitle):
            img_data = self._generate_kicks_image(username, gift_name, amount)
            if img_data:
                self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, img_data)
            self._wait_for_dismiss()

        self.board.set_backlight(0)

    def cleanup(self):
        if self.board:
            self.board.cleanup()

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _load_alert_config(self):
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                print(f"Warning: {self.config_path} is not a JSON object; ignoring.")
                return {}
            return data
        except Exception as e:
            print(f"Warning: failed to parse {self.config_path}: {e}")
            return {}

    # ------------------------------------------------------------------
    # LEDs / input
    # ------------------------------------------------------------------

    def _flash_leds(self):
        if not self.board:
            return
        color_sequence = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 0, 255),
        ]
        for r, g, b in color_sequence:
            self.board.set_rgb(r, g, b)
            time.sleep(0.2)
        self.board.set_rgb(0, 0, 0)

    def _wait_for_dismiss(self):
        """Block for ALERT_DURATION_S or until the button is pressed."""
        for _ in range(int(ALERT_DURATION_S * 10)):
            if self.board.button_pressed():
                while self.board.button_pressed():
                    time.sleep(0.1)
                return
            time.sleep(0.1)

    # ------------------------------------------------------------------
    # Shared drawing helpers
    # ------------------------------------------------------------------

    def _load_fonts(self):
        try:
            pixel_font_path = os.path.join(self.assets_dir, 'pixel.ttf')
            font_title = ImageFont.truetype(pixel_font_path, 20)
            font_sub = ImageFont.truetype(pixel_font_path, 14)
            font_big = ImageFont.truetype(pixel_font_path, 24)
        except IOError:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_big = ImageFont.load_default()
        return font_title, font_sub, font_big

    def _load_background(self):
        screen_width = self.board.LCD_WIDTH
        screen_height = self.board.LCD_HEIGHT
        bg_path = os.path.join(self.assets_dir, 'background.jpg')
        if os.path.exists(bg_path):
            try:
                return Image.open(bg_path).convert('RGB').resize((screen_width, screen_height))
            except Exception as e:
                print(f"Failed to load background.jpg: {e}")
        return Image.new('RGB', (screen_width, screen_height), color=(20, 20, 25))

    @staticmethod
    def _draw_text_with_shadow(draw, position, text, font, fill_color, shadow_color="black"):
        x, y = position
        draw.text((x + 2, y + 2), text, fill=shadow_color, font=font)
        draw.text((x, y), text, fill=fill_color, font=font)

    @staticmethod
    def _text_width(draw, text, font):
        try:
            left, _, right, _ = draw.textbbox((0, 0), text, font=font)
            return right - left
        except AttributeError:
            w, _ = draw.textsize(text, font=font)
            return w

    def _center_x(self, draw, text, font):
        return (self.board.LCD_WIDTH - self._text_width(draw, text, font)) / 2

    def _fit_and_shrink(self, draw, text, initial_font, max_width, min_size=8):
        pixel_font_path = os.path.join(self.assets_dir, 'pixel.ttf')
        font = initial_font
        size = getattr(initial_font, 'size', 24) or 24
        while True:
            if self._text_width(draw, text, font) <= max_width or size <= min_size:
                return font
            size -= 2
            try:
                font = ImageFont.truetype(pixel_font_path, size)
            except IOError:
                return font

    @staticmethod
    def _pil_to_rgb565_bytes(img):
        if img.mode != 'RGB':
            img = img.convert('RGB')
        arr = np.asarray(img, dtype=np.uint16)
        r = (arr[:, :, 0] & 0xF8) << 8
        g = (arr[:, :, 1] & 0xFC) << 3
        b = arr[:, :, 2] >> 3
        return (r | g | b).astype('>u2').tobytes()

    @staticmethod
    def _scale_to_fit(img, max_w, max_h):
        ratio = min(max_w / img.width, max_h / img.height)
        new_w = max(1, int(img.width * ratio))
        new_h = max(1, int(img.height * ratio))
        return img.resize((new_w, new_h), Image.LANCZOS)

    # ------------------------------------------------------------------
    # Static (non-GIF) renderers — one per alert type
    # ------------------------------------------------------------------

    def _generate_alert_image(self, username, count):
        """Gift sub alert, static layout."""
        if not self.board:
            return None

        img = self._load_background()
        draw = ImageDraw.Draw(img)
        font_title, font_sub, font_big = self._load_fonts()

        header = "GIFTED SUB!"
        self._draw_text_with_shadow(draw, (self._center_x(draw, header, font_title), 8),
                                    header, font_title, "white")

        user_font = self._fit_and_shrink(draw, username, font_big, self.board.LCD_WIDTH - 20)
        self._draw_text_with_shadow(draw, (self._center_x(draw, username, user_font), 100),
                                    username, user_font, KICK_GREEN)

        subtitle = (
            "is online!" if count == "Starting Up"
            else f"gifted {count} sub{'s' if count != 1 else ''}!"
        )
        self._draw_text_with_shadow(draw, (self._center_x(draw, subtitle, font_sub), 160),
                                    subtitle, font_sub, "white")

        return self._pil_to_rgb565_bytes(img)

    def _generate_reward_image(self, username, reward_title):
        if not self.board:
            return None

        img = self._load_background()
        draw = ImageDraw.Draw(img)
        font_title, font_sub, font_big = self._load_fonts()

        header = "REWARD REDEEMED!"
        self._draw_text_with_shadow(draw, (self._center_x(draw, header, font_title), 8),
                                    header, font_title, "white")

        user_font = self._fit_and_shrink(draw, username, font_big, self.board.LCD_WIDTH - 20)
        self._draw_text_with_shadow(draw, (self._center_x(draw, username, user_font), 100),
                                    username, user_font, KICK_GREEN)

        self._draw_text_with_shadow(draw, (self._center_x(draw, reward_title, font_sub), 160),
                                    reward_title, font_sub, "white")

        return self._pil_to_rgb565_bytes(img)

    def _generate_kicks_image(self, username, gift_name, amount):
        if not self.board:
            return None

        img = self._load_background()
        draw = ImageDraw.Draw(img)
        font_title, font_sub, font_big = self._load_fonts()

        header = "KICK GIFTED!"
        self._draw_text_with_shadow(draw, (self._center_x(draw, header, font_title), 8),
                                    header, font_title, "white")

        user_font = self._fit_and_shrink(draw, username, font_big, self.board.LCD_WIDTH - 20)
        self._draw_text_with_shadow(draw, (self._center_x(draw, username, user_font), 100),
                                    username, user_font, KICK_GREEN)

        subtitle = f"{gift_name} x{amount}" if amount > 1 else gift_name
        self._draw_text_with_shadow(draw, (self._center_x(draw, subtitle, font_sub), 160),
                                    subtitle, font_sub, "white")

        return self._pil_to_rgb565_bytes(img)

    # ------------------------------------------------------------------
    # GIF-based animated alert path
    # ------------------------------------------------------------------

    def _try_play_gif_alert(self, alert_type, header, username, subtitle):
        """If config enables a GIF for this alert type, preload frames and run the animation.
        Returns True if the animated alert played, False if the caller should use the static path."""
        cfg = self.alert_config.get(alert_type) or {}
        gif_filename = cfg.get('gif')
        if not gif_filename:
            return False

        gif_path = os.path.join(self.assets_dir, gif_filename)
        if not os.path.exists(gif_path):
            print(f"Warning: GIF {gif_path} not found; falling back to static alert.")
            return False

        try:
            frames = self._preload_animated_frames(gif_path, header, username, subtitle)
        except Exception as e:
            print(f"Failed to preload GIF {gif_filename}: {e}; falling back to static alert.")
            return False

        if not frames:
            return False

        self._run_animation_loop(frames)
        return True

    def _preload_animated_frames(self, gif_path, header, username, subtitle):
        """Render every GIF frame with text baked in. Returns list of (rgb565_bytes, duration_ms)."""
        screen_w = self.board.LCD_WIDTH
        screen_h = self.board.LCD_HEIGHT

        font_title, font_sub, _font_big = self._load_fonts()
        try:
            pixel_font_path = os.path.join(self.assets_dir, 'pixel.ttf')
            font_user = ImageFont.truetype(pixel_font_path, 20)
        except IOError:
            font_user = font_title

        bg = self._load_background()

        gif = Image.open(gif_path)
        frames = []
        for raw_frame in ImageSequence.Iterator(gif):
            duration_ms = raw_frame.info.get('duration', 100) or 100
            # Convert to RGBA so transparent GIFs composite cleanly.
            frame_rgba = raw_frame.convert('RGBA')
            scaled = self._scale_to_fit(frame_rgba, GIF_BOX_W, GIF_BOX_H)

            img = bg.copy()
            sx = (screen_w - scaled.width) // 2
            sy = GIF_BOX_TOP + (GIF_BOX_H - scaled.height) // 2
            img.paste(scaled, (sx, sy), scaled)

            draw = ImageDraw.Draw(img)
            self._draw_text_with_shadow(draw, (self._center_x(draw, header, font_title), 8),
                                        header, font_title, "white")

            user_font = self._fit_and_shrink(draw, username, font_user, screen_w - 20)
            self._draw_text_with_shadow(draw, (self._center_x(draw, username, user_font), GIF_TEXT_USER_Y),
                                        username, user_font, KICK_GREEN)

            self._draw_text_with_shadow(draw, (self._center_x(draw, subtitle, font_sub), GIF_TEXT_SUB_Y),
                                        subtitle, font_sub, "white")

            frames.append((self._pil_to_rgb565_bytes(img), duration_ms))

        return frames

    def _run_animation_loop(self, frames):
        """Play frames in a loop until ALERT_DURATION_S elapses or the button is pressed."""
        W = self.board.LCD_WIDTH
        H = self.board.LCD_HEIGHT
        deadline = time.monotonic() + ALERT_DURATION_S
        i = 0
        while time.monotonic() < deadline:
            frame_bytes, frame_ms = frames[i % len(frames)]
            self.board.draw_image(0, 0, W, H, frame_bytes)

            frame_end = time.monotonic() + frame_ms / 1000.0
            while time.monotonic() < min(frame_end, deadline):
                if self.board.button_pressed():
                    while self.board.button_pressed():
                        time.sleep(0.1)
                    return
                time.sleep(0.02)
            i += 1
