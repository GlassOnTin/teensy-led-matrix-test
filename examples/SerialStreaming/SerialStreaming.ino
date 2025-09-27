#include <LEDMatrix.h>
#include <SerialStream.h>

LEDMatrix matrix;
SerialStream stream(matrix);

void setup() {
    matrix.begin();
    stream.begin();
    
    Serial.println("Serial Streaming Mode");
    Serial.println("Waiting for video data...");
    Serial.println("Frame format: 0xFF 0xFE 0xFD followed by RGB data");
}

void loop() {
    stream.update();
    
    static unsigned long lastReport = 0;
    if (millis() - lastReport > 1000) {
        if (stream.getFrameCount() > 0) {
            Serial.print("FPS: ");
            Serial.println(stream.getFrameCount());
            stream.resetFrameCount();
        }
        lastReport = millis();
    }
}