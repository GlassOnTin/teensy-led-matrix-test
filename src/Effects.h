#ifndef EFFECTS_H
#define EFFECTS_H

#include <Arduino.h>
#include "LEDMatrix.h"

class Effect {
public:
    virtual ~Effect() {}
    virtual void init(LEDMatrix& matrix) = 0;
    virtual void update(LEDMatrix& matrix) = 0;
    virtual const char* getName() const = 0;
};

class RainbowEffect : public Effect {
public:
    RainbowEffect(uint8_t speed = 5);
    void init(LEDMatrix& matrix) override;
    void update(LEDMatrix& matrix) override;
    const char* getName() const override { return "Rainbow"; }
    
private:
    uint8_t hue_;
    uint8_t speed_;
};

class PlasmaEffect : public Effect {
public:
    PlasmaEffect();
    void init(LEDMatrix& matrix) override;
    void update(LEDMatrix& matrix) override;
    const char* getName() const override { return "Plasma"; }
    
private:
    uint16_t time_;
};

class FireEffect : public Effect {
public:
    FireEffect();
    ~FireEffect();
    void init(LEDMatrix& matrix) override;
    void update(LEDMatrix& matrix) override;
    const char* getName() const override { return "Fire"; }
    
private:
    uint8_t* heat_;
    int width_;
    int height_;
    
    static constexpr uint8_t COOLING = 55;
    static constexpr uint8_t SPARKING = 120;
};

class StarfieldEffect : public Effect {
public:
    struct Star {
        float x, y, z;
        uint8_t brightness;
    };
    
    StarfieldEffect(int numStars = 100);
    ~StarfieldEffect();
    void init(LEDMatrix& matrix) override;
    void update(LEDMatrix& matrix) override;
    const char* getName() const override { return "Starfield"; }
    
private:
    Star* stars_;
    int numStars_;
    float speed_;
};

class WaveEffect : public Effect {
public:
    WaveEffect();
    void init(LEDMatrix& matrix) override;
    void update(LEDMatrix& matrix) override;
    const char* getName() const override { return "Wave"; }
    
private:
    float phase_;
    float amplitude_;
    float frequency_;
    uint8_t hue_;
};

class MatrixRainEffect : public Effect {
public:
    struct Drop {
        int x;
        float y;
        float speed;
        uint8_t length;
        uint8_t hue;
    };
    
    MatrixRainEffect(int numDrops = 20);
    ~MatrixRainEffect();
    void init(LEDMatrix& matrix) override;
    void update(LEDMatrix& matrix) override;
    const char* getName() const override { return "Matrix Rain"; }
    
private:
    Drop* drops_;
    int numDrops_;
    void initDrop(Drop& drop, LEDMatrix& matrix);
};

#endif