class Timer
{
  private:
    unsigned long durationMs;
    unsigned long startTime;

    void startTimer()
    {
      startTime = millis();
    }
  
  public:
    // Constructor with an additional parameter to start as timed out
    Timer(unsigned long _durationMs, bool _startTimedOut = false)
      : durationMs(_durationMs)
    {
        if (_startTimedOut) {
            // timedOut() will return true immediately
            startTime = millis() - durationMs;
        } else {
            startTimer(); // Start the timer normally
        }
    }

    void resetTimer()
    {
      startTime = millis();
    }

    unsigned long getElapsedTimeMs()
    {
      unsigned long currentTime = millis();
      unsigned long deltaTime = currentTime - startTime;
      return deltaTime;
    }

    float getElapsedTimeS()
    {
      float timeInSeconds = getElapsedTimeMs() / 1000;
      return timeInSeconds;
    }

    bool timedOut()
    {
      unsigned long elapsedTime = getElapsedTimeMs();

      if(elapsedTime >= durationMs)
      {
        return true;
      }
      else
      {
        return false;
      }
    }
};