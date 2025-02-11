class SerialConnectionManager{

  public:
    bool serialConnection = false; //While serialConnection is known connection at the moment...
    // bool serialLost = false; //...serialLoss indicates going from connected to disconnected.

    void begin(unsigned long baudRate = 9600){
      Serial.begin(baudRate);
    }

    static SerialConnectionManager& getInstance() {
      static SerialConnectionManager instance; // Created on first use
      return instance;
    }

    SerialConnectionManager(const SerialConnectionManager&) = delete;
    SerialConnectionManager& operator=(const SerialConnectionManager&) = delete;

  private:
    SerialConnectionManager() {
      
    }

    // Private destructor (optional)
    ~SerialConnectionManager() {
    }
};

class SerialMessageHandler
{

  public:
    static SerialMessageHandler& getInstance() {
        static SerialMessageHandler instance;
        return instance;
    }

    SerialMessageHandler(const SerialMessageHandler&) = delete;
    SerialMessageHandler& operator=(const SerialMessageHandler&) = delete;

    void passMessage(const MessageStruct& message, float value = NAN, const String &timestamp = "") const
    {
      String outgoingMessage = stringMessageHandler.buildMessage(message, value, timestamp);
      sendMessage(outgoingMessage);
    }

    ParsedMessageStruct getMessage()
    {
      String incomingMessage = receiveMessage();
      ParsedMessageStruct parsed = stringMessageHandler.parseMessage(incomingMessage);
      return parsed;
    }

    // Sends the message via Serial
    void sendMessage(const String& message) const
    {
      Serial.println(message);
    }

    // Receives a message from Serial until a newline character is encountered
    String receiveMessage() const
    {
      if (Serial.available())
      {
          return Serial.readStringUntil('\n');
      }
      else
      {
          return negativeOneSentinel;
      }
    }


  private:
    // Private constructor to prevent external instantiation more than once
    SerialMessageHandler() {
    }

    // Private destructor (optional)
    ~SerialMessageHandler() {
    }

    StringMessageHandler &stringMessageHandler = StringMessageHandler::getInstance();

};

class SerialHandshakeHandler
{
  //If the whole procedure with both handshake and detection for going from serial contact to serial loss is implemented, the serial connection manager would need the handshake handler as a dependency and not opposite.
  //The whole thing would happen in a handleSerialConnection method in the serial connectio manager, using the handshake handler
  //This class will need to be moved to below all the other serial classes.

  public:
    // Static method to access the single instance
    static SerialHandshakeHandler& getInstance() {
        static SerialHandshakeHandler instance;
        return instance;
    }

    void handleHandshake(const ParsedMessageStruct &message) {
      if(message.message == &Messages::PING_PC_ARDUINO)
      {
        serialConnectionManager.serialConnection = true;
        pingReceivedTimer.resetTimer();
        serialMessageHandler.passMessage(Messages::PING_ARDUINO_PC);
      }
      else
      {
        if(pingReceivedTimer.timedOut())
        {
          serialConnectionManager.serialConnection = false;
        }
      }
    }

    // Delete copy constructor and assignment operator to avoid misuse
    SerialHandshakeHandler(const SerialHandshakeHandler&) = delete;
    SerialHandshakeHandler& operator=(const SerialHandshakeHandler&) = delete;

  private:
    unsigned long pingReceivedTimeout = 15000;
    Timer pingReceivedTimer;

    // Private constructor to prevent instantiation
    SerialHandshakeHandler()
      : pingReceivedTimer(pingReceivedTimeout)
    {}

    ~SerialHandshakeHandler() = default;

    SerialConnectionManager &serialConnectionManager = SerialConnectionManager::getInstance();
    SerialMessageHandler &serialMessageHandler = SerialMessageHandler::getInstance();
};