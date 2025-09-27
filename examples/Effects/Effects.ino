#include <LEDMatrix.h>
#include <Effects.h>

LEDMatrix matrix;

Effect* effects[] = {
    new RainbowEffect(3),
    new PlasmaEffect(),
    new FireEffect(),
    new StarfieldEffect(50),
    new WaveEffect(),
    new MatrixRainEffect(15)
};

const int numEffects = sizeof(effects) / sizeof(effects[0]);
int currentEffect = 0;
unsigned long lastChange = 0;

void setup() {
    Serial.begin(115200);
    Serial.println("LED Matrix Effects Demo");
    
    matrix.begin();
    matrix.setBrightness(96);
    
    effects[currentEffect]->init(matrix);
    Serial.print("Starting effect: ");
    Serial.println(effects[currentEffect]->getName());
}

void loop() {
    if (millis() - lastChange > 10000) {
        currentEffect = (currentEffect + 1) % numEffects;
        effects[currentEffect]->init(matrix);
        Serial.print("Effect: ");
        Serial.println(effects[currentEffect]->getName());
        lastChange = millis();
    }
    
    effects[currentEffect]->update(matrix);
    delay(20);
}