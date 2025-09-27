#include <Arduino.h>
#include "LEDMatrix.h"
#include "SerialStream.h"
#include "Effects.h"

LEDMatrix matrix;
SerialStream* serialStream = nullptr;

enum Mode {
    MODE_SERIAL_STREAM,
    MODE_EFFECTS
};

Mode currentMode = MODE_EFFECTS;
Effect* currentEffect = nullptr;
Effect* effects[] = {
    new RainbowEffect(),
    new PlasmaEffect(),
    new FireEffect(),
    new StarfieldEffect(),
    new WaveEffect(),
    new MatrixRainEffect()
};
const int numEffects = sizeof(effects) / sizeof(effects[0]);
int currentEffectIndex = 0;
unsigned long lastEffectChange = 0;
const unsigned long effectDuration = 10000;

void setup() {
    // Teensy 4.0 can handle up to 6Mbps reliably
    Serial.begin(6000000);
    
    matrix.begin();
    
    serialStream = new SerialStream(matrix);
    serialStream->begin();
    
    if (currentMode == MODE_EFFECTS && numEffects > 0) {
        currentEffect = effects[0];
        currentEffect->init(matrix);
    }
    
    Serial.println("LED Matrix initialized");
    Serial.println("Send 'e' to switch to effects mode");
    Serial.println("Send 's' to switch to serial stream mode");
}

void loop() {
    if (Serial.available() > 0 && Serial.peek() != 0xFF) {
        char cmd = Serial.read();
        if (cmd == 'e' || cmd == 'E') {
            currentMode = MODE_EFFECTS;
            if (currentEffect) {
                currentEffect->init(matrix);
            }
            Serial.println("Switched to effects mode");
        } else if (cmd == 's' || cmd == 'S') {
            currentMode = MODE_SERIAL_STREAM;
            Serial.println("Switched to serial stream mode");
        }
    }
    
    if (currentMode == MODE_SERIAL_STREAM) {
        serialStream->update();
    } else if (currentMode == MODE_EFFECTS) {
        if (millis() - lastEffectChange > effectDuration) {
            currentEffectIndex = (currentEffectIndex + 1) % numEffects;
            currentEffect = effects[currentEffectIndex];
            currentEffect->init(matrix);
            lastEffectChange = millis();
            Serial.print("Effect: ");
            Serial.println(currentEffect->getName());
        }
        
        if (currentEffect) {
            currentEffect->update(matrix);
        }
        
        // Reduced delay for higher frame rate (50 FPS)
        delay(10);
    }
}