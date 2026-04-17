import os
import sys
import time
from PIL import Image, ImageDraw, ImageFont

# Add driver to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'vendor', 'Whisplay', 'Driver')))

try:
    from WhisPlay import WhisPlayBoard
except ImportError:
    print("Warning: WhisPlay driver not found or could not be loaded. Are you running on the device?")
    WhisPlayBoard = None

class DisplayManager:
    def __init__(self):
        self.board = None
        
        # Assets directory
        self.assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
        
        if WhisPlayBoard is not None:
            self.board = WhisPlayBoard()
            
            # Show a boot splash screen so the user knows the driver is working
            print("Showing boot splash screen...")
            self.board.set_backlight(100)
            self.board.set_rgb(0, 0, 255) # Blue LED on boot
            
            # Create a simple "Starting" text
            img_data = self._generate_alert_image("System", "Starting Up")
            if img_data:
                self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, img_data)
                
            time.sleep(2)
            self.board.set_rgb(0, 0, 0)
            
            # Turn the screen OFF initially since there are no alerts (from user requirement)
            self.board.set_backlight(0)
            self.board.fill_screen(0x0000) # Black screen

    def trigger_alert(self, gifter_username, count=1):
        """Show the gift sub alert."""
        if not self.board:
            print(f"[MOCK DISPLAY] Displaying Alert: {gifter_username} gifted {count} subs!")
            return

        print(f"Triggering alert for {gifter_username}...")

        # 1. Clear old content before turning on backlight
        self.board.fill_screen(0x0000)
        self.board.set_backlight(100)
        
        # 2. Flash LEDs
        self._flash_leds()
        
        # 3. Create dynamic image with gifter text
        img_data = self._generate_alert_image(gifter_username, count)
        if img_data:
            self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, img_data)
        
        # Let it display for up to 20 seconds, or until button is pressed
        for _ in range(200): # 20 seconds / 0.1s
            if self.board.button_pressed():
                # Button pressed to dismiss!
                # Wait for button to be released to avoid triggering a new test alert
                while self.board.button_pressed():
                    time.sleep(0.1)
                break
            time.sleep(0.1)
        
        # 4. Turn off screen again
        self.board.set_backlight(0)

    def _flash_leds(self):
        if not self.board:
            return
        # Sequence of flashing colors: Red -> Green -> Blue
        color_sequence = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 0, 255)
        ]
        for r, g, b in color_sequence:
            self.board.set_rgb(r, g, b)
            time.sleep(0.2)
        # Turn off LEDs
        self.board.set_rgb(0, 0, 0)

    def _generate_alert_image(self, username, count):
        """Generates an image with the gifter's name and converts it to RGB565."""
        if not self.board:
            return None
            
        screen_width = self.board.LCD_WIDTH
        screen_height = self.board.LCD_HEIGHT
        
        # Create base image
        bg_path = os.path.join(self.assets_dir, 'background.jpg')
        if os.path.exists(bg_path):
            try:
                bg_img = Image.open(bg_path).convert('RGB')
                img = bg_img.resize((screen_width, screen_height))
            except Exception as e:
                print(f"Failed to load background.jpg: {e}")
                img = Image.new('RGB', (screen_width, screen_height), color=(20, 20, 25))
        else:
            img = Image.new('RGB', (screen_width, screen_height), color=(20, 20, 25))
            
        draw = ImageDraw.Draw(img)
        
        kick_green = (83, 252, 24)
        
        # Use the downloaded Pixel Font!
        try:
            pixel_font_path = os.path.join(self.assets_dir, 'pixel.ttf')
            font_title = ImageFont.truetype(pixel_font_path, 20)
            font_sub = ImageFont.truetype(pixel_font_path, 14)
            font_big = ImageFont.truetype(pixel_font_path, 24)
        except IOError:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_big = ImageFont.load_default()

        # Text rendering (simple centering)
        text_top = "GIFTED SUB!"
        
        # Helper to draw text with shadow
        def draw_text_with_shadow(position, text, font, fill_color, shadow_color="black"):
            x, y = position
            # Draw shadow
            draw.text((x+2, y+2), text, fill=shadow_color, font=font)
            # Draw text
            draw.text((x, y), text, fill=fill_color, font=font)
        
        # PIL 9.5.0+ textbbox
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text_top, font=font_title)
            w = right - left
        except AttributeError:
            w, h = draw.textsize(text_top, font=font_title)
        
        draw_text_with_shadow(((screen_width - w) / 2, 8), text_top, font_title, "white")
        
        # Shrink username font if it exceeds screen width
        text_user = username
        actual_font = font_big
        current_size = 24
        
        while True:
            try:
                left, top, right, bottom = draw.textbbox((0, 0), text_user, font=actual_font)
                w = right - left
            except AttributeError:
                w, h = draw.textsize(text_user, font=actual_font)
                
            if w <= screen_width - 20 or current_size <= 8:
                break
                
            current_size -= 2
            try:
                pixel_font_path = os.path.join(self.assets_dir, 'pixel.ttf')
                actual_font = ImageFont.truetype(pixel_font_path, current_size)
            except IOError:
                break # default font fallback can't shrink
            
        draw_text_with_shadow(((screen_width - w) / 2, 100), text_user, actual_font, kick_green)
        
        text_count = f"gifted {count} sub{'s' if count != 1 else ''}!" if count != "Starting Up" else "is online!"
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text_count, font=font_sub)
            w = right - left
        except AttributeError:
            w, h = draw.textsize(text_count, font=font_sub)
            
        draw_text_with_shadow(((screen_width - w) / 2, 160), text_count, font_sub, "white")

        # Convert Image to RGB565 Array
        pixel_data = []
        for y in range(screen_height):
            for x in range(screen_width):
                r, g, b = img.getpixel((x, y))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])
                
        return pixel_data

    def trigger_reward_alert(self, username, reward_title):
        if not self.board:
            print(f"[MOCK DISPLAY] Reward Alert: {username} redeemed '{reward_title}'")
            return

        self.board.fill_screen(0x0000)
        self.board.set_backlight(100)
        self._flash_leds()

        img_data = self._generate_reward_image(username, reward_title)
        if img_data:
            self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, img_data)

        for _ in range(200):
            if self.board.button_pressed():
                while self.board.button_pressed():
                    time.sleep(0.1)
                break
            time.sleep(0.1)

        self.board.set_backlight(0)

    def _generate_reward_image(self, username, reward_title):
        if not self.board:
            return None

        screen_width = self.board.LCD_WIDTH
        screen_height = self.board.LCD_HEIGHT

        bg_path = os.path.join(self.assets_dir, 'background.jpg')
        if os.path.exists(bg_path):
            try:
                bg_img = Image.open(bg_path).convert('RGB')
                img = bg_img.resize((screen_width, screen_height))
            except Exception:
                img = Image.new('RGB', (screen_width, screen_height), color=(20, 20, 25))
        else:
            img = Image.new('RGB', (screen_width, screen_height), color=(20, 20, 25))

        draw = ImageDraw.Draw(img)
        kick_green = (83, 252, 24)

        try:
            pixel_font_path = os.path.join(self.assets_dir, 'pixel.ttf')
            font_title = ImageFont.truetype(pixel_font_path, 20)
            font_sub = ImageFont.truetype(pixel_font_path, 14)
            font_big = ImageFont.truetype(pixel_font_path, 24)
        except IOError:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_big = ImageFont.load_default()

        def draw_text_with_shadow(position, text, font, fill_color, shadow_color="black"):
            x, y = position
            draw.text((x+2, y+2), text, fill=shadow_color, font=font)
            draw.text((x, y), text, fill=fill_color, font=font)

        def centered_x(text, font):
            try:
                left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
                return (screen_width - (right - left)) / 2
            except AttributeError:
                w, h = draw.textsize(text, font=font)
                return (screen_width - w) / 2

        header = "REWARD REDEEMED!"
        draw_text_with_shadow((centered_x(header, font_title), 8), header, font_title, "white")

        # Shrink username if needed
        actual_font = font_big
        current_size = 24
        while True:
            try:
                left, _, right, _ = draw.textbbox((0, 0), username, font=actual_font)
                w = right - left
            except AttributeError:
                w, _ = draw.textsize(username, font=actual_font)
            if w <= screen_width - 20 or current_size <= 8:
                break
            current_size -= 2
            try:
                actual_font = ImageFont.truetype(pixel_font_path, current_size)
            except IOError:
                break

        try:
            left, _, right, _ = draw.textbbox((0, 0), username, font=actual_font)
            w = right - left
        except AttributeError:
            w, _ = draw.textsize(username, font=actual_font)
        draw_text_with_shadow(((screen_width - w) / 2, 100), username, actual_font, kick_green)

        draw_text_with_shadow((centered_x(reward_title, font_sub), 160), reward_title, font_sub, "white")

        pixel_data = []
        for y in range(screen_height):
            for x in range(screen_width):
                r, g, b = img.getpixel((x, y))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])
        return pixel_data

    def trigger_kicks_alert(self, username, gift_name, amount):
        if not self.board:
            print(f"[MOCK DISPLAY] Kicks Alert: {username} gifted {gift_name} x{amount}")
            return

        self.board.fill_screen(0x0000)
        self.board.set_backlight(100)
        self._flash_leds()

        img_data = self._generate_kicks_image(username, gift_name, amount)
        if img_data:
            self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, img_data)

        for _ in range(200):
            if self.board.button_pressed():
                while self.board.button_pressed():
                    time.sleep(0.1)
                break
            time.sleep(0.1)

        self.board.set_backlight(0)

    def _generate_kicks_image(self, username, gift_name, amount):
        if not self.board:
            return None

        screen_width = self.board.LCD_WIDTH
        screen_height = self.board.LCD_HEIGHT

        bg_path = os.path.join(self.assets_dir, 'background.jpg')
        if os.path.exists(bg_path):
            try:
                bg_img = Image.open(bg_path).convert('RGB')
                img = bg_img.resize((screen_width, screen_height))
            except Exception:
                img = Image.new('RGB', (screen_width, screen_height), color=(20, 20, 25))
        else:
            img = Image.new('RGB', (screen_width, screen_height), color=(20, 20, 25))

        draw = ImageDraw.Draw(img)
        kick_green = (83, 252, 24)

        try:
            pixel_font_path = os.path.join(self.assets_dir, 'pixel.ttf')
            font_title = ImageFont.truetype(pixel_font_path, 20)
            font_sub = ImageFont.truetype(pixel_font_path, 14)
            font_big = ImageFont.truetype(pixel_font_path, 24)
        except IOError:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_big = ImageFont.load_default()

        def draw_text_with_shadow(position, text, font, fill_color, shadow_color="black"):
            x, y = position
            draw.text((x+2, y+2), text, fill=shadow_color, font=font)
            draw.text((x, y), text, fill=fill_color, font=font)

        def centered_x(text, font):
            try:
                left, _, right, _ = draw.textbbox((0, 0), text, font=font)
                return (screen_width - (right - left)) / 2
            except AttributeError:
                w, _ = draw.textsize(text, font=font)
                return (screen_width - w) / 2

        header = "KICK GIFTED!"
        draw_text_with_shadow((centered_x(header, font_title), 8), header, font_title, "white")

        actual_font = font_big
        current_size = 24
        while True:
            try:
                left, _, right, _ = draw.textbbox((0, 0), username, font=actual_font)
                w = right - left
            except AttributeError:
                w, _ = draw.textsize(username, font=actual_font)
            if w <= screen_width - 20 or current_size <= 8:
                break
            current_size -= 2
            try:
                actual_font = ImageFont.truetype(pixel_font_path, current_size)
            except IOError:
                break

        try:
            left, _, right, _ = draw.textbbox((0, 0), username, font=actual_font)
            w = right - left
        except AttributeError:
            w, _ = draw.textsize(username, font=actual_font)
        draw_text_with_shadow(((screen_width - w) / 2, 100), username, actual_font, kick_green)

        subtitle = f"{gift_name} x{amount}" if amount > 1 else gift_name
        draw_text_with_shadow((centered_x(subtitle, font_sub), 160), subtitle, font_sub, "white")

        pixel_data = []
        for y in range(screen_height):
            for x in range(screen_width):
                r, g, b = img.getpixel((x, y))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])
        return pixel_data

    def cleanup(self):
        if self.board:
            self.board.cleanup()
