#ifndef SERIAL_STREAM_H
#define SERIAL_STREAM_H

#include <Arduino.h>
#include "LEDMatrix.h"

class SerialStream {
public:
    static constexpr uint32_t DEFAULT_BAUD_RATE = 2000000;
    static constexpr uint8_t START_MARKER[3] = {0xFF, 0xFE, 0xFD};
    
    SerialStream(LEDMatrix& matrix, uint32_t baudRate = DEFAULT_BAUD_RATE);
    ~SerialStream();
    
    void begin();
    void update();
    bool isFrameReady() const { return frameReady_; }
    uint32_t getFrameCount() const { return frameCount_; }
    void resetFrameCount() { frameCount_ = 0; }
    
private:
    LEDMatrix& matrix_;
    uint32_t baudRate_;
    
    uint8_t* frameBuffer_;
    int bufferPos_;
    bool waitingForStart_;
    bool frameReady_;
    uint32_t frameCount_;
    
    uint8_t startBuffer_[3];
    
    void processFrame();
    bool checkStartMarker(uint8_t byte);
};

#endif