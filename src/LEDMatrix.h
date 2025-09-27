#ifndef LED_MATRIX_H
#define LED_MATRIX_H

#include <Arduino.h>
#include <FastLED.h>

class LEDMatrix {
public:
    static constexpr int PANEL_WIDTH = 32;
    static constexpr int PANEL_HEIGHT = 8;
    static constexpr int LEDS_PER_PANEL = PANEL_WIDTH * PANEL_HEIGHT;
    static constexpr int MATRIX_WIDTH = PANEL_WIDTH * 2;
    static constexpr int MATRIX_HEIGHT = PANEL_HEIGHT * 2;
    static constexpr int TOTAL_LEDS = LEDS_PER_PANEL * 4;
    
    enum PanelPosition {
        BOTTOM_LEFT = 0,
        BOTTOM_RIGHT = 1,
        TOP_LEFT = 2,
        TOP_RIGHT = 3
    };
    
    struct Config {
        uint8_t pin_bottom_left;
        uint8_t pin_bottom_right;
        uint8_t pin_top_left;
        uint8_t pin_top_right;
        uint8_t brightness;
        bool invert_display;
        bool skip_first_column;
        
        Config() : 
            pin_bottom_left(1),
            pin_bottom_right(2),
            pin_top_left(3),
            pin_top_right(4),
            brightness(26),  // 10% brightness for demo effects
            invert_display(true),
            skip_first_column(true) {}
    };
    
    LEDMatrix(const Config& config = Config());
    ~LEDMatrix();
    
    void begin();
    void clear();
    void show();
    void setBrightness(uint8_t brightness);
    
    void setPixel(int x, int y, CRGB color);
    void setPixel(int x, int y, uint8_t r, uint8_t g, uint8_t b);
    CRGB getPixel(int x, int y) const;
    
    void fillScreen(CRGB color);
    void drawLine(int x0, int y0, int x1, int y1, CRGB color);
    void drawRect(int x, int y, int width, int height, CRGB color);
    void fillRect(int x, int y, int width, int height, CRGB color);
    void drawCircle(int x0, int y0, int radius, CRGB color);
    void fillCircle(int x0, int y0, int radius, CRGB color);
    
    CRGB* getPanel(PanelPosition pos);
    const CRGB* getPanel(PanelPosition pos) const;
    
    int getWidth() const { return MATRIX_WIDTH; }
    int getHeight() const { return MATRIX_HEIGHT; }
    
private:
    Config config_;
    CRGB* panels_[4];
    
    int getPanelIndex(int x, int y) const;
    int getPixelIndex(int localX, int localY) const;
    void drawPixel(int x, int y, CRGB color);
};

#endif