#!/usr/bin/env python3
"""
LED Matrix Fireworks Display
Beautiful fireworks with realistic physics and various effects
"""

import time
import numpy as np
import random
import math
import argparse
import sys
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from serial_connection import TeensyConnection

class FireworkType(Enum):
    ROCKET = 1
    CHRYSANTHEMUM = 2
    WILLOW = 3
    FOUNTAIN = 4
    ROMAN_CANDLE = 5
    CASCADE = 6
    SPARKLER = 7

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: Tuple[int, int, int]
    life: float
    max_life: float
    trail: bool = False
    gravity: float = 0.15
    drag: float = 0.02
    sparkle: bool = False
    fade_type: str = "linear"

class Firework:
    def __init__(self, x: float, y: float, firework_type: FireworkType):
        self.type = firework_type
        self.particles: List[Particle] = []
        self.x = x
        self.y = y
        self.exploded = False
        self.age = 0
        
        # Create initial rocket or fountain
        if firework_type in [FireworkType.ROCKET, FireworkType.CHRYSANTHEMUM, FireworkType.WILLOW]:
            # Launch rocket upward with colorful trail
            trail_colors = [(255, 100, 50), (100, 255, 100), (100, 150, 255), (255, 50, 200)]
            self.rocket = Particle(
                x=x, y=y,
                vx=random.uniform(-0.5, 0.5),
                vy=random.uniform(-4.5, -3.5),
                color=random.choice(trail_colors),
                life=1.0,
                max_life=1.0,
                trail=True,
                gravity=0.12
            )
        elif firework_type == FireworkType.FOUNTAIN:
            self.create_fountain()
        elif firework_type == FireworkType.CASCADE:
            self.create_cascade()
        elif firework_type == FireworkType.SPARKLER:
            self.create_sparkler()
        else:
            self.exploded = True
            self.create_explosion()
    
    def create_explosion(self):
        """Create explosion particles based on firework type"""
        colors = [
            (200, 40, 40),    # Red (reduced intensity)
            (40, 200, 40),    # Green (reduced intensity)
            (40, 120, 200),   # Blue (reduced intensity)
            (200, 160, 0),    # Gold (reduced intensity)
            (200, 80, 0),     # Orange (reduced intensity)
            (200, 0, 160),    # Hot Pink (reduced intensity)
            (140, 0, 200),    # Purple (reduced intensity)
            (0, 200, 160),    # Aqua (reduced intensity)
            (200, 0, 80),     # Deep Red (reduced intensity)
            (80, 200, 0),     # Lime (reduced intensity)
        ]
        
        if self.type == FireworkType.CHRYSANTHEMUM:
            # Perfect sphere explosion with mixed colors
            base_color = random.choice(colors)
            accent_color = random.choice(colors)
            num_particles = random.randint(15, 25)  # Even smaller for less intensity
            for i in range(num_particles):
                angle = (2 * math.pi * i) / num_particles
                speed = random.uniform(0.8, 1.5)  # Reduced speed for smaller spread
                # Mix colors for variety
                if random.random() < 0.3:
                    color = accent_color
                else:
                    color = base_color
                self.particles.append(Particle(
                    x=self.rocket.x, y=self.rocket.y,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    color=color,
                    life=1.0,
                    max_life=1.0,
                    sparkle=random.random() < 0.3,
                    gravity=0.08,
                    drag=0.03
                ))
        
        elif self.type == FireworkType.WILLOW:
            # Falling trails with colorful streaks
            color_choices = [(180, 80, 40), (80, 180, 80), (180, 40, 120), (40, 120, 180)]
            color = random.choice(color_choices)
            num_particles = random.randint(20, 30)  # Reduced particles
            for i in range(num_particles):
                angle = (2 * math.pi * i) / num_particles
                speed = random.uniform(1.0, 1.8)
                self.particles.append(Particle(
                    x=self.rocket.x, y=self.rocket.y,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed * 0.5,  # More horizontal
                    color=color,
                    life=1.5,
                    max_life=1.5,
                    trail=True,
                    gravity=0.12,
                    drag=0.015,
                    fade_type="slow"
                ))
        
        elif self.type == FireworkType.ROCKET:
            # Multi-color burst with vibrant colors
            num_colors = random.randint(2, 4)  # Fewer colors
            chosen_colors = random.sample(colors, num_colors)
            particles_per_color = 6  # Even fewer particles per color
            
            for color in chosen_colors:
                for i in range(particles_per_color):
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(0.8, 1.8)  # Reduced spread
                    self.particles.append(Particle(
                        x=self.rocket.x, y=self.rocket.y,
                        vx=math.cos(angle) * speed,
                        vy=math.sin(angle) * speed,
                        color=color,
                        life=random.uniform(0.8, 1.2),
                        max_life=1.0,
                        sparkle=random.random() < 0.4
                    ))
    
    def create_fountain(self):
        """Create continuous fountain particles"""
        colors = [(255, 100, 0), (255, 0, 100), (100, 100, 255), (0, 255, 100), (255, 255, 0)]
        for _ in range(5):
            angle = random.uniform(-0.3, 0.3) - math.pi/2  # Mostly upward
            speed = random.uniform(2.0, 3.5)
            self.particles.append(Particle(
                x=self.x + random.uniform(-2, 2),
                y=self.y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                color=random.choice(colors),
                life=random.uniform(0.8, 1.2),
                max_life=1.0,
                sparkle=True,
                gravity=0.2
            ))
    
    def create_cascade(self):
        """Create waterfall-like cascade effect"""
        colors = [(100, 150, 255), (150, 200, 255), (200, 220, 255)]
        for i in range(8):
            self.particles.append(Particle(
                x=self.x + random.uniform(-8, 8),
                y=self.y,
                vx=random.uniform(-0.2, 0.2),
                vy=random.uniform(0.5, 1.5),  # Falling down
                color=random.choice(colors),
                life=random.uniform(1.5, 2.0),
                max_life=2.0,
                trail=True,
                gravity=-0.05,  # Negative gravity for falling effect
                drag=0.08,
                fade_type="slow"
            ))
    
    def create_sparkler(self):
        """Create handheld sparkler effect"""
        sparkler_colors = [(255, 200, 100), (255, 100, 255), (100, 255, 255), (255, 255, 100)]
        for _ in range(3):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.5, 1.5)
            self.particles.append(Particle(
                x=self.x,
                y=self.y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                color=random.choice(sparkler_colors),
                life=random.uniform(0.3, 0.6),
                max_life=0.6,
                sparkle=True,
                gravity=0.1,
                drag=0.05
            ))
    
    def update(self, dt: float) -> bool:
        """Update firework physics, return False when complete"""
        self.age += dt
        
        # Update rocket if not exploded
        if hasattr(self, 'rocket') and not self.exploded:
            self.rocket.vy += self.rocket.gravity
            self.rocket.vx *= (1 - self.rocket.drag)
            self.rocket.vy *= (1 - self.rocket.drag)
            self.rocket.x += self.rocket.vx
            self.rocket.y += self.rocket.vy
            
            # Explode at apex or after timeout
            if self.rocket.vy > 0 or self.rocket.y < 2:
                self.exploded = True
                self.create_explosion()
                return True
        
        # Continuous effects
        if self.type == FireworkType.FOUNTAIN and self.age < 3.0:
            if random.random() < 0.8:
                self.create_fountain()
        elif self.type == FireworkType.CASCADE and self.age < 2.5:
            if random.random() < 0.6:
                self.create_cascade()
        elif self.type == FireworkType.SPARKLER and self.age < 4.0:
            if random.random() < 0.9:
                self.create_sparkler()
        
        # Update particles
        alive_particles = []
        for p in self.particles:
            # Physics update
            p.vy += p.gravity * dt * 60
            p.vx *= (1 - p.drag)
            p.vy *= (1 - p.drag)
            p.x += p.vx * dt * 60
            p.y += p.vy * dt * 60
            
            # Life update
            p.life -= dt
            
            if p.life > 0:
                alive_particles.append(p)
        
        self.particles = alive_particles
        
        # Check if firework is complete
        if self.exploded and len(self.particles) == 0:
            if self.type not in [FireworkType.FOUNTAIN, FireworkType.CASCADE, FireworkType.SPARKLER]:
                return False
            elif self.age > 4.0:
                return False
        
        return True

class FireworksDisplay:
    def __init__(self, port: Optional[str] = None, test_mode: bool = False):
        self.width = 64
        self.height = 16
        self.test_mode = test_mode
        self.port = port or '/dev/ttyACM0'
        self.serial_conn = None
        self.fireworks: List[Firework] = []
        self.frame_buffer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.trail_buffer = np.zeros((self.height, self.width, 3), dtype=np.float32)
        self.last_launch = 0
        self.launch_delay = 0.5
        
        if not test_mode:
            self.connect_serial()
    
    def connect_serial(self):
        """Connect to Teensy over serial with safe handling"""
        self.serial_conn = TeensyConnection(port=self.port)
        if not self.serial_conn.connect(mode='s'):
            print("Running in test mode")
            self.test_mode = True
    
    def launch_firework(self):
        """Launch a new firework"""
        firework_types = [
            (FireworkType.ROCKET, 0.3),
            (FireworkType.CHRYSANTHEMUM, 0.25),
            (FireworkType.WILLOW, 0.2),
            (FireworkType.FOUNTAIN, 0.1),
            (FireworkType.CASCADE, 0.08),
            (FireworkType.SPARKLER, 0.07),
        ]
        
        # Choose type based on weights
        rand = random.random()
        cumulative = 0
        chosen_type = FireworkType.ROCKET
        
        for fw_type, weight in firework_types:
            cumulative += weight
            if rand < cumulative:
                chosen_type = fw_type
                break
        
        # Launch position
        if chosen_type in [FireworkType.FOUNTAIN, FireworkType.SPARKLER]:
            x = random.uniform(10, self.width - 10)
            y = self.height - 1  # Ground level
        elif chosen_type == FireworkType.CASCADE:
            x = random.uniform(20, self.width - 20)
            y = random.uniform(2, 5)  # Low cascade
        else:
            x = random.uniform(15, self.width - 15)
            y = self.height - 1  # Launch from ground
        
        self.fireworks.append(Firework(x, y, chosen_type))
    
    def render_particle(self, p: Particle, fade: float = 1.0):
        """Render a particle to the frame buffer"""
        # Calculate position with proper orientation (Y-axis inverted)
        x = int(p.x)
        y = self.height - 1 - int(p.y)  # Invert Y for proper display
        
        if 0 <= x < self.width and 0 <= y < self.height:
            # Apply life-based fading
            if p.fade_type == "slow":
                alpha = min(1.0, p.life / p.max_life) ** 0.5
            else:
                alpha = p.life / p.max_life
            
            alpha *= fade
            
            # Sparkle effect
            if p.sparkle and random.random() < 0.7:
                alpha *= random.uniform(0.3, 1.0)
            
            # Apply color with alpha
            color = np.array(p.color) * alpha
            
            # Softer additive blending to prevent white oversaturation
            existing = self.frame_buffer[y, x].astype(np.float32)
            # Use weighted average to prevent pure white buildup
            blend_factor = 0.6  # Reduced from 0.8
            self.frame_buffer[y, x] = np.clip(
                existing * (1 - blend_factor * alpha) + color * blend_factor,
                0, 255
            ).astype(np.uint8)
            
            # Add to trail buffer if particle has trails
            if p.trail:
                self.trail_buffer[y, x] += color * 0.3
    
    def update_and_render(self, dt: float):
        """Update physics and render frame"""
        # Fade trail buffer more aggressively to reduce lingering effects
        self.trail_buffer *= 0.88
        
        # Clear frame buffer
        self.frame_buffer = np.clip(self.trail_buffer, 0, 255).astype(np.uint8)
        
        # Update fireworks
        active_fireworks = []
        for fw in self.fireworks:
            if fw.update(dt):
                active_fireworks.append(fw)
                
                # Render rocket trail
                if hasattr(fw, 'rocket') and not fw.exploded:
                    self.render_particle(fw.rocket)
                
                # Render particles
                for p in fw.particles:
                    self.render_particle(p)
        
        self.fireworks = active_fireworks
        
        # Launch new fireworks
        current_time = time.time()
        if current_time - self.last_launch > self.launch_delay:
            if len(self.fireworks) < 4:  # Reduce concurrent fireworks for less chaos
                self.launch_firework()
                self.last_launch = current_time
                self.launch_delay = random.uniform(0.5, 2.0)  # Slightly longer delays
                
                # Less frequent multiple launches
                if random.random() < 0.15:
                    self.launch_firework()
    
    def send_frame(self):
        """Send frame to LED matrix via serial with timeout protection"""
        if self.test_mode:
            self.print_frame()
            return
        
        if self.serial_conn:
            # Send frame with automatic retry
            frame_data = bytes([0xFF, 0xFE, 0xFD]) + self.frame_buffer.flatten().tobytes()
            if not self.serial_conn.write_frame(frame_data):
                # Skip frame on error but continue running
                pass
    
    def print_frame(self):
        """Print ASCII representation for testing"""
        print("\033[H\033[J")  # Clear screen
        print("🎆 LED Matrix Fireworks Display 🎆")
        print("=" * 66)
        
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                pixel = self.frame_buffer[y, x]
                brightness = np.mean(pixel)
                
                if brightness > 200:
                    row += "●"
                elif brightness > 150:
                    row += "◉"
                elif brightness > 100:
                    row += "○"
                elif brightness > 50:
                    row += "∘"
                elif brightness > 20:
                    row += "·"
                else:
                    row += " "
            print(f"|{row}|")
        
        print("=" * 66)
        print(f"Active fireworks: {len(self.fireworks)}")
        print("Press Ctrl+C to exit")
    
    def run(self):
        """Main display loop"""
        print("Starting fireworks display!")
        print("Press Ctrl+C to exit")
        
        last_time = time.time()
        frame_count = 0
        fps_time = time.time()
        
        try:
            while True:
                current_time = time.time()
                dt = current_time - last_time
                last_time = current_time
                
                # Update and render
                self.update_and_render(dt)
                self.send_frame()
                
                # FPS counter
                frame_count += 1
                if current_time - fps_time >= 1.0:
                    fps = frame_count / (current_time - fps_time)
                    if not self.test_mode:
                        print(f"\rFPS: {fps:.1f}", end="")
                    frame_count = 0
                    fps_time = current_time
                
                # Target 30 FPS
                sleep_time = max(0, (1/30) - dt)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            print("\n\nFireworks show ended!")
        finally:
            if self.serial_conn:
                self.serial_conn.close()

def main():
    parser = argparse.ArgumentParser(description='LED Matrix Fireworks Display')
    parser.add_argument('--port', type=str, default=None,
                        help='Serial port for Teensy (auto-detect if not specified)')
    parser.add_argument('--test-mode', action='store_true',
                        help='Run without hardware for testing')
    
    args = parser.parse_args()
    
    display = FireworksDisplay(port=args.port, test_mode=args.test_mode)
    display.run()

if __name__ == '__main__':
    main()