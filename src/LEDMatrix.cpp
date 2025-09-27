#include "LEDMatrix.h"

LEDMatrix::LEDMatrix(const Config& config) : config_(config) {
    for (int i = 0; i < 4; i++) {
        panels_[i] = new CRGB[LEDS_PER_PANEL];
    }
}

LEDMatrix::~LEDMatrix() {
    for (int i = 0; i < 4; i++) {
        delete[] panels_[i];
    }
}

void LEDMatrix::begin() {
    FastLED.addLeds<WS2812B, 1, GRB>(panels_[BOTTOM_LEFT], LEDS_PER_PANEL);
    FastLED.addLeds<WS2812B, 2, GRB>(panels_[BOTTOM_RIGHT], LEDS_PER_PANEL);
    FastLED.addLeds<WS2812B, 3, GRB>(panels_[TOP_LEFT], LEDS_PER_PANEL);
    FastLED.addLeds<WS2812B, 4, GRB>(panels_[TOP_RIGHT], LEDS_PER_PANEL);
    
    FastLED.setBrightness(config_.brightness);
    FastLED.setMaxPowerInVoltsAndMilliamps(5, 1500); // Limit power for safety
    clear();
    show();
    
    // Debug output
    Serial.print("Brightness set to: ");
    Serial.println(config_.brightness);
}

void LEDMatrix::clear() {
    for (int i = 0; i < 4; i++) {
        memset(panels_[i], 0, LEDS_PER_PANEL * sizeof(CRGB));
    }
}

void LEDMatrix::show() {
    // Ensure brightness is still applied
    FastLED.setBrightness(config_.brightness);
    FastLED.show();
}

void LEDMatrix::setBrightness(uint8_t brightness) {
    config_.brightness = brightness;
    FastLED.setBrightness(brightness);
}

void LEDMatrix::setPixel(int x, int y, CRGB color) {
    // Apply brightness scaling directly to the color
    color.nscale8(config_.brightness);
    drawPixel(x, y, color);
}

void LEDMatrix::setPixel(int x, int y, uint8_t r, uint8_t g, uint8_t b) {
    CRGB color(r, g, b);
    // Apply brightness scaling directly to the color
    color.nscale8(config_.brightness);
    drawPixel(x, y, color);
}

void LEDMatrix::drawPixel(int x, int y, CRGB color) {
    if (x < 0 || x >= MATRIX_WIDTH || y < 0 || y >= MATRIX_HEIGHT) return;
    
    if (config_.skip_first_column && x == 0) return;
    
    if (config_.invert_display) {
        y = MATRIX_HEIGHT - 1 - y;
    }
    
    int panelX = x / PANEL_WIDTH;
    int panelY = y / PANEL_HEIGHT;
    
    int localX = x % PANEL_WIDTH;
    int localY = y % PANEL_HEIGHT;
    
    int pixelIdx = getPixelIndex(localX, localY);
    int panelIdx = getPanelIndex(panelX, panelY);
    
    if (panelIdx >= 0 && panelIdx < 4) {
        panels_[panelIdx][pixelIdx] = color;
    }
}

CRGB LEDMatrix::getPixel(int x, int y) const {
    if (x < 0 || x >= MATRIX_WIDTH || y < 0 || y >= MATRIX_HEIGHT) {
        return CRGB::Black;
    }
    
    if (config_.invert_display) {
        y = MATRIX_HEIGHT - 1 - y;
    }
    
    int panelX = x / PANEL_WIDTH;
    int panelY = y / PANEL_HEIGHT;
    
    int localX = x % PANEL_WIDTH;
    int localY = y % PANEL_HEIGHT;
    
    int pixelIdx = getPixelIndex(localX, localY);
    int panelIdx = getPanelIndex(panelX, panelY);
    
    if (panelIdx >= 0 && panelIdx < 4) {
        return panels_[panelIdx][pixelIdx];
    }
    
    return CRGB::Black;
}

int LEDMatrix::getPanelIndex(int panelX, int panelY) const {
    if (panelY == 0) {
        return panelX == 0 ? TOP_LEFT : TOP_RIGHT;
    } else {
        return panelX == 0 ? BOTTOM_LEFT : BOTTOM_RIGHT;
    }
}

int LEDMatrix::getPixelIndex(int localX, int localY) const {
    if (localX % 2 == 0) {
        return localX * PANEL_HEIGHT + localY;
    } else {
        return localX * PANEL_HEIGHT + (PANEL_HEIGHT - 1 - localY);
    }
}

void LEDMatrix::fillScreen(CRGB color) {
    for (int y = 0; y < MATRIX_HEIGHT; y++) {
        for (int x = 0; x < MATRIX_WIDTH; x++) {
            setPixel(x, y, color);
        }
    }
}

void LEDMatrix::drawLine(int x0, int y0, int x1, int y1, CRGB color) {
    int dx = abs(x1 - x0);
    int dy = abs(y1 - y0);
    int sx = x0 < x1 ? 1 : -1;
    int sy = y0 < y1 ? 1 : -1;
    int err = dx - dy;
    
    while (true) {
        setPixel(x0, y0, color);
        
        if (x0 == x1 && y0 == y1) break;
        
        int e2 = 2 * err;
        if (e2 > -dy) {
            err -= dy;
            x0 += sx;
        }
        if (e2 < dx) {
            err += dx;
            y0 += sy;
        }
    }
}

void LEDMatrix::drawRect(int x, int y, int width, int height, CRGB color) {
    drawLine(x, y, x + width - 1, y, color);
    drawLine(x + width - 1, y, x + width - 1, y + height - 1, color);
    drawLine(x + width - 1, y + height - 1, x, y + height - 1, color);
    drawLine(x, y + height - 1, x, y, color);
}

void LEDMatrix::fillRect(int x, int y, int width, int height, CRGB color) {
    for (int j = y; j < y + height; j++) {
        for (int i = x; i < x + width; i++) {
            setPixel(i, j, color);
        }
    }
}

void LEDMatrix::drawCircle(int x0, int y0, int radius, CRGB color) {
    int x = radius;
    int y = 0;
    int err = 0;
    
    while (x >= y) {
        setPixel(x0 + x, y0 + y, color);
        setPixel(x0 + y, y0 + x, color);
        setPixel(x0 - y, y0 + x, color);
        setPixel(x0 - x, y0 + y, color);
        setPixel(x0 - x, y0 - y, color);
        setPixel(x0 - y, y0 - x, color);
        setPixel(x0 + y, y0 - x, color);
        setPixel(x0 + x, y0 - y, color);
        
        if (err <= 0) {
            y += 1;
            err += 2 * y + 1;
        }
        if (err > 0) {
            x -= 1;
            err -= 2 * x + 1;
        }
    }
}

void LEDMatrix::fillCircle(int x0, int y0, int radius, CRGB color) {
    for (int y = -radius; y <= radius; y++) {
        for (int x = -radius; x <= radius; x++) {
            if (x * x + y * y <= radius * radius) {
                setPixel(x0 + x, y0 + y, color);
            }
        }
    }
}

CRGB* LEDMatrix::getPanel(PanelPosition pos) {
    return panels_[pos];
}

const CRGB* LEDMatrix::getPanel(PanelPosition pos) const {
    return panels_[pos];
}