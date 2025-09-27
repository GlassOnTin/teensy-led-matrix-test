#include <LEDMatrix.h>

LEDMatrix matrix;

void setup() {
    Serial.begin(115200);
    Serial.println("Basic LED Matrix Demo");
    
    matrix.begin();
    matrix.setBrightness(96);
}

void loop() {
    matrix.clear();
    
    matrix.fillRect(0, 0, 10, 10, CRGB::Red);
    matrix.drawRect(20, 0, 20, 10, CRGB::Green);
    matrix.drawCircle(50, 8, 6, CRGB::Blue);
    
    for (int x = 0; x < matrix.getWidth(); x++) {
        matrix.setPixel(x, 15, CHSV(x * 4, 255, 255));
    }
    
    matrix.show();
    delay(1000);
    
    matrix.clear();
    for (int i = 0; i < 20; i++) {
        int x = random(matrix.getWidth());
        int y = random(matrix.getHeight());
        CRGB color = CHSV(random(256), 255, 255);
        matrix.fillCircle(x, y, 2, color);
    }
    matrix.show();
    delay(1000);
}