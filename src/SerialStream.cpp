#include "SerialStream.h"

SerialStream::SerialStream(LEDMatrix& matrix, uint32_t baudRate) 
    : matrix_(matrix), 
      baudRate_(baudRate),
      bufferPos_(0),
      waitingForStart_(true),
      frameReady_(false),
      frameCount_(0) {
    
    int frameSize = matrix.getWidth() * matrix.getHeight() * 3;
    frameBuffer_ = new uint8_t[frameSize];
    memset(startBuffer_, 0, 3);
}

SerialStream::~SerialStream() {
    delete[] frameBuffer_;
}

void SerialStream::begin() {
    Serial.begin(baudRate_);
    Serial.setTimeout(10);
}

void SerialStream::update() {
    while (Serial.available() > 0) {
        uint8_t b = Serial.read();
        
        if (waitingForStart_) {
            if (checkStartMarker(b)) {
                waitingForStart_ = false;
                bufferPos_ = 0;
                frameReady_ = false;
            }
        } else {
            frameBuffer_[bufferPos_++] = b;
            
            int frameSize = matrix_.getWidth() * matrix_.getHeight() * 3;
            if (bufferPos_ >= frameSize) {
                processFrame();
                waitingForStart_ = true;
                bufferPos_ = 0;
                frameReady_ = true;
                frameCount_++;
            }
        }
    }
}

bool SerialStream::checkStartMarker(uint8_t byte) {
    startBuffer_[0] = startBuffer_[1];
    startBuffer_[1] = startBuffer_[2];
    startBuffer_[2] = byte;
    
    return (startBuffer_[0] == START_MARKER[0] && 
            startBuffer_[1] == START_MARKER[1] && 
            startBuffer_[2] == START_MARKER[2]);
}

void SerialStream::processFrame() {
    // Optimized: Process frame in larger chunks
    int idx = 0;
    const int width = matrix_.getWidth();
    const int height = matrix_.getHeight();
    
    // Process 4 pixels at a time for better cache usage
    for (int y = 0; y < height; y++) {
        int x = 0;
        // Process 4 pixels at once
        for (; x < width - 3; x += 4) {
            for (int i = 0; i < 4; i++) {
                uint8_t r = frameBuffer_[idx++];
                uint8_t g = frameBuffer_[idx++];
                uint8_t b = frameBuffer_[idx++];
                matrix_.setPixel(x + i, y, r, g, b);
            }
        }
        // Handle remaining pixels
        for (; x < width; x++) {
            uint8_t r = frameBuffer_[idx++];
            uint8_t g = frameBuffer_[idx++];
            uint8_t b = frameBuffer_[idx++];
            matrix_.setPixel(x, y, r, g, b);
        }
    }
    matrix_.show();
}