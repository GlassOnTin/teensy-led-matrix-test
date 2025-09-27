#include "Effects.h"
#include <math.h>

RainbowEffect::RainbowEffect(uint8_t speed) : hue_(0), speed_(speed) {}

void RainbowEffect::init(LEDMatrix& matrix) {
    hue_ = 0;
}

void RainbowEffect::update(LEDMatrix& matrix) {
    for (int y = 0; y < matrix.getHeight(); y++) {
        for (int x = 0; x < matrix.getWidth(); x++) {
            uint8_t pixelHue = hue_ + (x * 256 / matrix.getWidth());
            matrix.setPixel(x, y, CHSV(pixelHue, 255, 255));
        }
    }
    hue_ += speed_;
    matrix.show();
}

PlasmaEffect::PlasmaEffect() : time_(0) {}

void PlasmaEffect::init(LEDMatrix& matrix) {
    time_ = 0;
}

void PlasmaEffect::update(LEDMatrix& matrix) {
    for (int y = 0; y < matrix.getHeight(); y++) {
        for (int x = 0; x < matrix.getWidth(); x++) {
            uint8_t value = inoise8(x * 30, y * 30, time_);
            uint8_t hue = value + (time_ >> 2);
            // Boost brightness for better visibility at low brightness settings
            // Map value from 0-255 to 128-255 range for better visibility
            uint8_t brightness = 128 + (value >> 1);
            matrix.setPixel(x, y, CHSV(hue, 255, brightness));
        }
    }
    time_ += 10;
    matrix.show();
}

FireEffect::FireEffect() : heat_(nullptr), width_(0), height_(0) {}

FireEffect::~FireEffect() {
    delete[] heat_;
}

void FireEffect::init(LEDMatrix& matrix) {
    width_ = matrix.getWidth();
    height_ = matrix.getHeight();
    delete[] heat_;
    heat_ = new uint8_t[width_ * height_];
    memset(heat_, 0, width_ * height_);
}

void FireEffect::update(LEDMatrix& matrix) {
    for (int x = 0; x < width_; x++) {
        // Cool down every cell a little
        for (int y = 0; y < height_; y++) {
            int idx = y * width_ + x;
            int cooling = random(0, ((COOLING * 10) / height_) + 2);
            heat_[idx] = (heat_[idx] > cooling) ? heat_[idx] - cooling : 0;
        }
        
        // Heat from each cell drifts up and diffuses slightly
        // In LED matrix coordinates: y=0 is TOP, y=height-1 is BOTTOM
        // Heat rises: from bottom (high y) to top (low y)
        for (int y = 0; y < height_ - 1; y++) {
            int idx = y * width_ + x;
            int below = (y + 1) * width_ + x;
            int below2 = (y + 2 < height_) ? (y + 2) * width_ + x : below;
            
            // Pull heat from below with diffusion
            int newHeat = (heat_[below] + heat_[below] + heat_[below2]) / 3;
            
            // Add some lateral diffusion for more realistic flames
            if (x > 0 && x < width_ - 1) {
                newHeat = (newHeat * 3 + heat_[below - 1] + heat_[below + 1]) / 5;
            }
            
            heat_[idx] = newHeat;
        }
        
        // Randomly ignite new sparks at the bottom
        if (random8() < SPARKING) {
            int y = height_ - 1 - random8(2);  // Bottom 2 rows
            int idx = y * width_ + x;
            heat_[idx] = qadd8(heat_[idx], random8(160, 255));
        }
    }
    
    for (int y = 0; y < height_; y++) {
        for (int x = 0; x < width_; x++) {
            int idx = y * width_ + x;
            uint8_t temperature = heat_[idx];
            
            // Custom fire palette with blue tips at the cool end
            CRGB color;
            if (temperature < 20) {
                // Black (0-20) - tops of flames fade to nothing
                color = CRGB::Black;
            } else if (temperature < 50) {
                // Black to blue tips (20-50) - cool flame tips
                uint8_t t = map(temperature, 20, 50, 0, 100);
                color = CRGB(0, 0, t);
            } else if (temperature < 90) {
                // Blue to dark red (50-90) - transition from tips
                uint8_t blue = map(temperature, 50, 90, 100, 0);
                uint8_t red = map(temperature, 50, 90, 0, 100);
                color = CRGB(red, 0, blue);
            } else if (temperature < 150) {
                // Dark red to bright red (90-150)
                uint8_t t = map(temperature, 90, 150, 100, 255);
                color = CRGB(t, 0, 0);
            } else if (temperature < 200) {
                // Red to orange (150-200)
                uint8_t t = map(temperature, 150, 200, 0, 128);
                color = CRGB(255, t, 0);
            } else if (temperature < 240) {
                // Orange to yellow (200-240)
                uint8_t t = map(temperature, 200, 240, 128, 255);
                color = CRGB(255, t, 0);
            } else {
                // Yellow to white (240-255) - hottest part at source
                uint8_t t = map(temperature, 240, 255, 0, 200);
                color = CRGB(255, 255, t);
            }
            
            // Flip the display vertically when rendering
            matrix.setPixel(x, height_ - 1 - y, color);
        }
    }
    matrix.show();
}

StarfieldEffect::StarfieldEffect(int numStars) : numStars_(numStars), speed_(0.5f) {
    stars_ = new Star[numStars_];
}

StarfieldEffect::~StarfieldEffect() {
    delete[] stars_;
}

void StarfieldEffect::init(LEDMatrix& matrix) {
    for (int i = 0; i < numStars_; i++) {
        stars_[i].x = random(0, matrix.getWidth() * 10) / 10.0f;
        stars_[i].y = random(0, matrix.getHeight() * 10) / 10.0f;
        stars_[i].z = random(10, 100) / 10.0f;
        stars_[i].brightness = 0;
    }
}

void StarfieldEffect::update(LEDMatrix& matrix) {
    matrix.clear();
    
    for (int i = 0; i < numStars_; i++) {
        stars_[i].z -= speed_;
        
        if (stars_[i].z <= 0) {
            stars_[i].x = random(0, matrix.getWidth() * 10) / 10.0f;
            stars_[i].y = random(0, matrix.getHeight() * 10) / 10.0f;
            stars_[i].z = 10.0f;
        }
        
        int x = (int)((stars_[i].x - matrix.getWidth() / 2) * (10 / stars_[i].z) + matrix.getWidth() / 2);
        int y = (int)((stars_[i].y - matrix.getHeight() / 2) * (10 / stars_[i].z) + matrix.getHeight() / 2);
        
        if (x >= 0 && x < matrix.getWidth() && y >= 0 && y < matrix.getHeight()) {
            uint8_t brightness = 255 - (stars_[i].z * 25);
            matrix.setPixel(x, y, CRGB(brightness, brightness, brightness));
        }
    }
    matrix.show();
}

WaveEffect::WaveEffect() : phase_(0), amplitude_(3), frequency_(0.3f), hue_(0) {}

void WaveEffect::init(LEDMatrix& matrix) {
    phase_ = 0;
    hue_ = 0;
}

void WaveEffect::update(LEDMatrix& matrix) {
    matrix.clear();
    
    for (int x = 0; x < matrix.getWidth(); x++) {
        float y = sin(x * frequency_ + phase_) * amplitude_ + matrix.getHeight() / 2;
        
        for (int dy = -2; dy <= 2; dy++) {
            int pixelY = (int)y + dy;
            if (pixelY >= 0 && pixelY < matrix.getHeight()) {
                uint8_t brightness = 255 - abs(dy) * 50;
                matrix.setPixel(x, pixelY, CHSV(hue_ + x * 4, 255, brightness));
            }
        }
    }
    
    phase_ += 0.2f;
    hue_ += 2;
    matrix.show();
}

MatrixRainEffect::MatrixRainEffect(int numDrops) : numDrops_(numDrops) {
    drops_ = new Drop[numDrops_];
}

MatrixRainEffect::~MatrixRainEffect() {
    delete[] drops_;
}

void MatrixRainEffect::init(LEDMatrix& matrix) {
    for (int i = 0; i < numDrops_; i++) {
        initDrop(drops_[i], matrix);
        drops_[i].y = random(0, matrix.getHeight());
    }
}

void MatrixRainEffect::initDrop(Drop& drop, LEDMatrix& matrix) {
    drop.x = random(0, matrix.getWidth());
    drop.y = matrix.getHeight() + random(5, 20);  // Start below the bottom
    drop.speed = random(10, 30) / 10.0f;
    drop.length = random(3, 8);
    drop.hue = 96;
}

void MatrixRainEffect::update(LEDMatrix& matrix) {
    matrix.clear();
    
    for (int i = 0; i < numDrops_; i++) {
        drops_[i].y -= drops_[i].speed;  // Move upward in screen coordinates (which appears as falling)
        
        if (drops_[i].y + drops_[i].length < 0) {  // Completely off top
            initDrop(drops_[i], matrix);
        }
        
        for (int j = 0; j < drops_[i].length; j++) {
            int y = (int)(drops_[i].y + j);  // Trail extends upward
            if (y >= 0 && y < matrix.getHeight()) {
                uint8_t brightness = 255 - (j * 255 / drops_[i].length);
                matrix.setPixel(drops_[i].x, y, CHSV(drops_[i].hue, 255 - j * 20, brightness));
            }
        }
    }
    matrix.show();
}