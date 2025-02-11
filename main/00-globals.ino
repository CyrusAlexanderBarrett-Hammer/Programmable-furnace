#include "String.h"

#include <Adafruit_MAX31856.h>
#include <SPI.h>;

const String negativeOneSentinel = "-1"; //NAN equivalent for when NaN can't be used. Can be used anywhere, but NaN should be used where possible.