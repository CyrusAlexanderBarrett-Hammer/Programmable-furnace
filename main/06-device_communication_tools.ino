struct MessageStruct
{
  char category; //Categories enforce structure
  char message;
};

struct ParsedMessageStruct
{
  //Category and message combines into instruction with MessageStruct
  MessageStruct *message;
  float value;
  String timestamp;
  // Indicate whether the parsed message is valid
  bool isValid;
};

namespace Messages{
  //Pre-written instructions
  //Categories encforce structure.
  static const MessageStruct PING_ARDUINO_PC = {'1', '2'}; //Sent to PC
  static const MessageStruct PING_PC_ARDUINO = {'1', '1'}; //Received from PC

  static const MessageStruct TEMPERATURE_READING = {'2', '1'}; //Sent to PC

  static const MessageStruct FORCE_EMERGENCY_STOP = {'4', '0'}; //Received from PC

  static const MessageStruct EMERGENCY_ALARM = {'9', '0'}; //Sent to PC
  static const MessageStruct THERMOSENSOR_ERROR = {'9', '1'}; //Sent to PC
  static const MessageStruct WATCHDOG_SR_LATCH_FROZEN = {'9', '2'}; //Sent to PC. The oven heating signal is stuck to high.
  static const MessageStruct OVEN_OVERHEAT = {'9', '3'}; //Sent to PC

  //Allows iteration by using pointers to Messages' memory addresses, unlike iterating over their structs directly
  const MessageStruct* messagePointers[] = {
    &Messages::PING_ARDUINO_PC,
    &Messages::PING_PC_ARDUINO,
    &Messages::TEMPERATURE_READING,
    &Messages::FORCE_EMERGENCY_STOP,
    &Messages::EMERGENCY_ALARM,
    &Messages::THERMOSENSOR_ERROR,
    &Messages::WATCHDOG_SR_LATCH_FROZEN,
    &Messages::OVEN_OVERHEAT
  };

  static constexpr size_t NUM_MESSAGES = sizeof(messagePointers) / sizeof(messagePointers[0]); //size calculations are platform dependent, size_t bridges the gap
};

//Timeout durations for sending any outgoing messages to avoid overcrowding the line
namespace MessageTimeouts {
  // Instantiate Timer for each message with specific timeout durations
  //What about PING_ARDUINO_PC_TIMER? It has no timeout since it responds once on ping from PC.
  //FORCE_EMERGENCY_STOP is sent from Python on the computer, so the timeout is handled there
  
  //All in milliseconds
  static Timer TEMPERATURE_READING(1500, true);
  static Timer EMERGENCY_ALARM(1000, true); //Milliseconds
  static Timer THERMOSENSOR_ERROR(1000, true); //Milliseconds
  static Timer WATCHDOG_SR_LATCH_FROZEN(1000, true); //Milliseconds
  static Timer OVEN_OVERHEAT(1000, true); //Milliseconds
}


class StringMessageHandler
{
//Class is a singleton, forcing you to have a single reference point for it. It makes the code tidier and more resource efficient.

  public:
    // Access the Singleton instance (singleton implementation, I just copy-paste)
    static StringMessageHandler& getInstance() {
        static StringMessageHandler instance; // Created on first use
        return instance;
    }

    // Delete copy constructor and assignment operator to prevent copies (singleton implementation, I just copy-paste)
    StringMessageHandler(const StringMessageHandler&) = delete;
    StringMessageHandler& operator=(const StringMessageHandler&) = delete;

    // Builds a message in the format "category,message,value,timestamp\n"
    String buildMessage(const MessageStruct& message, float value = NAN, const String &timestamp = "") const //Null substitute in timestamp for Python receival, C++ is lacking
    {
      String buildtMessage = "";
      // Append category
      buildtMessage += String(message.category);
      buildtMessage += messagePartSeparator;
      // Append message
      buildtMessage += String(message.message);
      buildtMessage += messagePartSeparator;
      // Append value with two decimal places or "NaN" if not a number
      if (isnan(value)) {
          buildtMessage += "NaN";
      } else {
          buildtMessage += String(value, 2); // 2 decimal places
      }
      buildtMessage += messagePartSeparator;
      // Append timestamp
      if (timestamp == ""){
        buildtMessage += "NaN";
      } else {
        buildtMessage += timestamp;
      }
      return buildtMessage;
    }

    ParsedMessageStruct parseMessage (const String &message){ //Deconstructs a serial message in the format category,message,value,timestamp\n(\n is optional)
      
      ParsedMessageStruct parsed;
      
      if(message != negativeOneSentinel)
      {
        //Protocol format for message is "category,message,value,timestamp", so three commas
        int commaCount = 0;
        for (int i = 0; i < message.length(); i++) {
          if (message.charAt(i) == messagePartSeparator) {
            commaCount++;
          }
        }
        
        // If comma count isn't exactly 3, it's invalid
        if (commaCount != 3) {
          // Early return with isValid = false
          parsed.message = nullptr;
          parsed.value = NAN;
          parsed.timestamp = negativeOneSentinel;
    
          return parsed;
        }
        
        //Find comma positions for message separation
        int commaIndex = 0;
        int commaIndexes[3];
        int commaIndexesLength = sizeof(commaIndexes)/sizeof(*commaIndexes);
        for(int i = 0; i < commaIndexesLength; i++){
          commaIndex = message.indexOf(messagePartSeparator, commaIndex + 1); //Find the next comma starting from nothing or the previous one
          //Test necessity
          if (commaIndex >= 0 && commaIndex < message.length()){ //Avoid out of bounds
            commaIndexes[i] = commaIndex;
          }
          else{
            // If this ever fails, it's invalid
            parsed.message = nullptr;
            parsed.value = NAN;
            parsed.timestamp = negativeOneSentinel;
            parsed.isValid = false;
            return parsed;
          }
        }
        
        char messageCategory = message.charAt(commaIndexes[0] - 1); //First digit before the first comma
        char messageMessage = message.charAt(commaIndexes[1] - 1); //First digit before the second comma
        MessageStruct *messageStruct = findMessage(messageCategory, messageMessage); //Gets the correct message type using category and message
        if(messageStruct != nullptr){
          parsed.message = messageStruct;
        }
        else{
          // Invalid because we didn't find the message
          parsed.message = nullptr;
          parsed.value = NAN;
          parsed.timestamp = negativeOneSentinel;
          parsed.isValid = false;
          return parsed;
        }
        
        float messageValue;
        String messageValueString = message.substring(commaIndexes[1] + 1, commaIndexes[2]);
        if(messageValueString != "NaN"){
          messageValue = atof(messageValueString.c_str()); //String to float
          parsed.value = messageValue;
        }
        else{
          parsed.value = NAN;
        }
        
        String messageTimestampString = message.substring(commaIndexes[2] + 1);
        if(messageTimestampString != "NaN"){
          // Check if timestamp format is valid
          if(isTimestampFormatValid(messageTimestampString)){
            parsed.timestamp = messageTimestampString;
          }
          else{
            // Invalid timestamp
            parsed.message = nullptr;
            parsed.value = NAN;
            parsed.timestamp = negativeOneSentinel;
            parsed.isValid = false;
            return parsed;
          }
        }
      }
      else
      {
        //In this case, there's no message
        parsed.message = nullptr;
        parsed.value = NAN;
        parsed.timestamp = negativeOneSentinel;
        parsed.isValid = false;
        return parsed;
      }
      
      parsed.isValid = true;
      return parsed;
    }

  private:
    // Private constructor to prevent external instantiation
    StringMessageHandler() { //(singleton implementation, I just copy-paste)
    }

    // Private destructor (optional)
    ~StringMessageHandler() { //(singleton implementation, I just copy-paste)
    }

    char messagePartSeparator = ',';

    // Verify timestamp format "%m/%d/%Y %H:%M:%S"
    // Checks if the string has 19 characters with /, space, and colons, and numbers. It does NOT check if the day and month is correct, but that's not necessary.
    bool isTimestampFormatValid(const String &ts) const
    {
      int len = ts.length();

      // Minimum length is 13: "M/D/YYYY H:M:S"
      // Maximum length is 19: "MM/DD/YYYY HH:MM:SS"
      if(len < 13 || len > 19) return false;

      // Find the positions of the delimiters
      int firstSlash = ts.indexOf('/');
      if(firstSlash == -1 || firstSlash < 1 || firstSlash > 2) return false;

      int secondSlash = ts.indexOf('/', firstSlash + 1);
      if(secondSlash == -1 || secondSlash < firstSlash + 2 || secondSlash > firstSlash + 3) return false;

      int space = ts.indexOf(' ', secondSlash + 1);
      if(space == -1 || space < secondSlash + 5 || space > secondSlash + 6) return false;

      int firstColon = ts.indexOf(':', space + 1);
      if(firstColon == -1 || firstColon < space + 2 || firstColon > space + 3) return false;

      int secondColon = ts.indexOf(':', firstColon + 1);
      if(secondColon == -1 || secondColon < firstColon + 2 || secondColon > firstColon + 3) return false;

      // Check if all other characters are digits
      for(int i = 0; i < len; i++){
          if(i == firstSlash || i == secondSlash || i == space || i == firstColon || i == secondColon) {
              // skip these since they're '/', '/', ' ', ':', ':'
              continue;
          }
          if(!isDigit(ts.charAt(i))) {
              return false;
          }
      }

      return true;
    }

    const MessageStruct* findMessage(char category, char message){
      for(size_t i = 0; i < Messages::NUM_MESSAGES; ++i){
        if(category == Messages::messagePointers[i]->category && message == Messages::messagePointers[i]->message){
          return Messages::messagePointers[i];
        }
      }
      return nullptr; //Message not there
    }

};