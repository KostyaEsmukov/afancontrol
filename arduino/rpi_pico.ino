// The pins defined in this program are for the Raspberry Pi Pico (RP2040).
// Flashed via Arduino IDE with https://arduino-pico.readthedocs.io/en/latest/install.html

#define PWM_STARTING_VALUE 255  // 0 = disabled, 255 = full speed.

// Use INPUT if the GP0–GP22 tachometer lines have external 3.3 V pull-ups.
// GP26–GP28 always use internal pull-ups. These ADC-capable pins must
// stay undriven while the Pico is off.
#define TACHO_PIN_MODE INPUT_PULLUP

#include <Arduino.h>

// Fan   PWM   TACH   PWM slice/channel
//  1     0     1     0A
//  2     2     3     1A
//  3     7     6     3B
//  4     8     4     4A
//  5     9     5     4B
//  6    10    11     5A
//  7    13    12     6B
//  8    14    15     7A
//  9    17    16     0B
// 10    19    18     1B
// 11    21    27     2B
// 12    20    26     2A
// 13    22    28     3A

/////////////////////////
// FAN PWM outputs:

// https://arduino-pico.readthedocs.io/en/latest/analog.html
// analogWrite() uses hardware PWM, with a default range of 0 to 255.
// Each of the selected GPIOs uses a different PWM slice/channel.
byte currentPWM0;
byte currentPWM2;
byte currentPWM7;
byte currentPWM8;
byte currentPWM9;
byte currentPWM10;
byte currentPWM13;
byte currentPWM14;
byte currentPWM17;
byte currentPWM19;
byte currentPWM21;
byte currentPWM20;
byte currentPWM22;

#define SET_PWM(PIN, PWM) currentPWM##PIN = (PWM);

#define PRINT_PWM_JSON(PIN) \
Serial.print("\""); \
Serial.print(PIN, DEC); \
Serial.print("\":"); \
Serial.print(currentPWM##PIN, DEC);

/////////////////////////
// FAN tachometer (RPM) inputs:

// Fan speed from the tachometer is measured by counting the number
// of interrupts (pulses) over a short period of time (`MEASUREMENT_TIME_MS`).
//
// Between periods, the current status is reported as JSON and
// an incoming command is read (if any) from the serial port.
//
// The number of pulses for each time period is written to a ring buffer,
// which allows us to compute the RPM over a longer interval than a single
// short `MEASUREMENT_TIME_MS` period, yielding a smoother RPM reading.
//
// The number of periods of the ring buffer is `PULSES_BUFFER_LEN`,
// so the total amount of time the pulses are measured for would be
// `PULSES_BUFFER_LEN` * `MEASUREMENT_TIME_MS`.
//
#define MEASUREMENT_TIME_MS 250
#define PULSES_BUFFER_LEN 6
volatile int pulsesBufferPosition = 0;
volatile bool measuringPulses = false;

// * 60 seconds in 1 minute (we count revolutions per *minute*);
// * 1000 to go from seconds to milliseconds;
// * Divided by the amount of time the pulses are measured.
//
// Be sure to select the dividers which yield an integer result after each division.
#define PULSES_MULTIPLIER (1L * 60 * 1000 / MEASUREMENT_TIME_MS / PULSES_BUFFER_LEN)

// When a PWM wire runs near the tachometer wire, the latter might
// pick up interference and trigger extra interrupts,
// spoiling the RPM measurements.
//
// PWM works at 25 kHz. The tachometer runs at about 4 to 200 Hz (120 to 6000 RPM),
// so the extraneous PWM pulses would have a delay of about 0.04 to 1 ms, while
// the genuine tachometer pulses would have a delay of 5 to 250 ms.
//
// This problem is similar to the common one occurring with the switches
// (http://www.gammon.com.au/switches), when a click on a switch produces
// many short pulses instead of a single long one.
//
// This variable defines the minimum delay (in ms) between two `RISING`
// interrupts for the second pulse to count as a valid tachometer pulse.
#define PULSES_ACCEPT_MIN_DURATION_MS 3

#define TACHO_PULSES_INT_FUNCTION(PIN) \
volatile int tachoPulses##PIN [PULSES_BUFFER_LEN]; \
volatile unsigned long lastPulse##PIN; \
void incTachoPulses##PIN () { \
  if (!measuringPulses) return; \
  unsigned long now = millis(); \
  if (now - lastPulse##PIN < PULSES_ACCEPT_MIN_DURATION_MS) { lastPulse##PIN = now; return; } \
  lastPulse##PIN = now; \
  tachoPulses##PIN [pulsesBufferPosition] ++; \
}

#define TACHO_PULSES_ATTACH_INT(PIN) \
pinMode(PIN, (PIN) >= 26 ? INPUT_PULLUP : TACHO_PIN_MODE); \
attachInterrupt(digitalPinToInterrupt(PIN), incTachoPulses##PIN, RISING); \
{ \
  for (int i = 0; i < PULSES_BUFFER_LEN; i++) tachoPulses##PIN[i] = 0; \
  lastPulse##PIN = 0; \
}

#define TACHO_PULSES_NEXT_BUCKET \
pulsesBufferPosition = (pulsesBufferPosition + 1) % PULSES_BUFFER_LEN;

#define TACHO_PULSES_RESET_CURRENT_BUCKET(PIN) \
tachoPulses##PIN[pulsesBufferPosition] = 0;

#define PRINT_RPM_JSON(PIN) \
Serial.print("\""); \
Serial.print(PIN, DEC); \
Serial.print("\":"); \
Serial.print(PULSES_MULTIPLIER * sumPulses(tachoPulses##PIN) / 2, DEC);
// ^^^ Regarding division by 2: PC fans do 2 pulses per each revolution,
// see https://electronics.stackexchange.com/q/8295

int sumPulses(volatile int tachoPulses [PULSES_BUFFER_LEN]) {
    int sum = 0;
    for (int i = 0; i < PULSES_BUFFER_LEN; i++) {
        sum += tachoPulses[i];
    }
    return sum;
}

// All exposed GPIOs on the Pico support interrupts.
TACHO_PULSES_INT_FUNCTION(1);
TACHO_PULSES_INT_FUNCTION(3);
TACHO_PULSES_INT_FUNCTION(6);
TACHO_PULSES_INT_FUNCTION(4);
TACHO_PULSES_INT_FUNCTION(5);
TACHO_PULSES_INT_FUNCTION(11);
TACHO_PULSES_INT_FUNCTION(12);
TACHO_PULSES_INT_FUNCTION(15);
TACHO_PULSES_INT_FUNCTION(16);
TACHO_PULSES_INT_FUNCTION(18);
TACHO_PULSES_INT_FUNCTION(27);
TACHO_PULSES_INT_FUNCTION(26);
TACHO_PULSES_INT_FUNCTION(28);


/////////////////////////
// Serial commands:

// Use byte rather than char to avoid signedness differences between boards.
const byte setSpeedCommand = 0xF1; // The only supported command currently.
byte commandBuffer[3];  // Buffer for the incoming command: [command; pin; speed].
int commandPosition = 0;  // The current position in the `commandBuffer`

/////////////////////////

void setup() {
  analogWriteFreq(25000); // 40us == 25kHz
  analogWriteRange(255);

  SET_PWM(0, PWM_STARTING_VALUE);
  SET_PWM(2, PWM_STARTING_VALUE);
  SET_PWM(7, PWM_STARTING_VALUE);
  SET_PWM(8, PWM_STARTING_VALUE);
  SET_PWM(9, PWM_STARTING_VALUE);
  SET_PWM(10, PWM_STARTING_VALUE);
  SET_PWM(13, PWM_STARTING_VALUE);
  SET_PWM(14, PWM_STARTING_VALUE);
  SET_PWM(17, PWM_STARTING_VALUE);
  SET_PWM(19, PWM_STARTING_VALUE);
  SET_PWM(21, PWM_STARTING_VALUE);
  SET_PWM(20, PWM_STARTING_VALUE);
  SET_PWM(22, PWM_STARTING_VALUE);

  TACHO_PULSES_ATTACH_INT(1);
  TACHO_PULSES_ATTACH_INT(3);
  TACHO_PULSES_ATTACH_INT(6);
  TACHO_PULSES_ATTACH_INT(4);
  TACHO_PULSES_ATTACH_INT(5);
  TACHO_PULSES_ATTACH_INT(11);
  TACHO_PULSES_ATTACH_INT(12);
  TACHO_PULSES_ATTACH_INT(15);
  TACHO_PULSES_ATTACH_INT(16);
  TACHO_PULSES_ATTACH_INT(18);
  TACHO_PULSES_ATTACH_INT(27);
  TACHO_PULSES_ATTACH_INT(26);
  TACHO_PULSES_ATTACH_INT(28);

  Serial.begin(115200);
}

void loop () {

  analogWrite(0, currentPWM0);
  analogWrite(2, currentPWM2);
  analogWrite(7, currentPWM7);
  analogWrite(8, currentPWM8);
  analogWrite(9, currentPWM9);
  analogWrite(10, currentPWM10);
  analogWrite(13, currentPWM13);
  analogWrite(14, currentPWM14);
  analogWrite(17, currentPWM17);
  analogWrite(19, currentPWM19);
  analogWrite(21, currentPWM21);
  analogWrite(20, currentPWM20);
  analogWrite(22, currentPWM22);

  // Measure RPM from tachometers:
  TACHO_PULSES_RESET_CURRENT_BUCKET(1);
  TACHO_PULSES_RESET_CURRENT_BUCKET(3);
  TACHO_PULSES_RESET_CURRENT_BUCKET(6);
  TACHO_PULSES_RESET_CURRENT_BUCKET(4);
  TACHO_PULSES_RESET_CURRENT_BUCKET(5);
  TACHO_PULSES_RESET_CURRENT_BUCKET(11);
  TACHO_PULSES_RESET_CURRENT_BUCKET(12);
  TACHO_PULSES_RESET_CURRENT_BUCKET(15);
  TACHO_PULSES_RESET_CURRENT_BUCKET(16);
  TACHO_PULSES_RESET_CURRENT_BUCKET(18);
  TACHO_PULSES_RESET_CURRENT_BUCKET(27);
  TACHO_PULSES_RESET_CURRENT_BUCKET(26);
  TACHO_PULSES_RESET_CURRENT_BUCKET(28);

  measuringPulses = true;
  delay (MEASUREMENT_TIME_MS);
  measuringPulses = false;
  TACHO_PULSES_NEXT_BUCKET;

  readSerialCommand();

  // Print the status (in JSON):

  Serial.print("{");

  Serial.print("\"fan_inputs\": {");
  PRINT_RPM_JSON(1);
  Serial.print(",");
  PRINT_RPM_JSON(3);
  Serial.print(",");
  PRINT_RPM_JSON(6);
  Serial.print(",");
  PRINT_RPM_JSON(4);
  Serial.print(",");
  PRINT_RPM_JSON(5);
  Serial.print(",");
  PRINT_RPM_JSON(11);
  Serial.print(",");
  PRINT_RPM_JSON(12);
  Serial.print(",");
  PRINT_RPM_JSON(15);
  Serial.print(",");
  PRINT_RPM_JSON(16);
  Serial.print(",");
  PRINT_RPM_JSON(18);
  Serial.print(",");
  PRINT_RPM_JSON(27);
  Serial.print(",");
  PRINT_RPM_JSON(26);
  Serial.print(",");
  PRINT_RPM_JSON(28);
  Serial.print("}, ");

  Serial.print("\"fan_pwm\": {");
  PRINT_PWM_JSON(0);
  Serial.print(",");
  PRINT_PWM_JSON(2);
  Serial.print(",");
  PRINT_PWM_JSON(7);
  Serial.print(",");
  PRINT_PWM_JSON(8);
  Serial.print(",");
  PRINT_PWM_JSON(9);
  Serial.print(",");
  PRINT_PWM_JSON(10);
  Serial.print(",");
  PRINT_PWM_JSON(13);
  Serial.print(",");
  PRINT_PWM_JSON(14);
  Serial.print(",");
  PRINT_PWM_JSON(17);
  Serial.print(",");
  PRINT_PWM_JSON(19);
  Serial.print(",");
  PRINT_PWM_JSON(21);
  Serial.print(",");
  PRINT_PWM_JSON(20);
  Serial.print(",");
  PRINT_PWM_JSON(22);
  Serial.print("}");

  Serial.print("}\n");
}

void readSerialCommand() {
  while (Serial.available()) {
    int value = Serial.read();
    if (value < 0) break;
    byte c = (byte)value;
    if (commandPosition == 0 && c != setSpeedCommand) {
      Serial.print("{\"error\": \"Unknown command ");
      Serial.print(c, HEX);
      Serial.print("\"}\n");
      continue;
    }
    commandBuffer[commandPosition] = c;
    commandPosition++;
    if (commandPosition >= 3) {
      // The command buffer is now complete, process it:
      processSerialCommand();

      commandPosition = 0;
    }
  }
}

void processSerialCommand() {
  // assert (commandBuffer[0] == setSpeedCommand);

  byte pwm = commandBuffer[2];
  switch (commandBuffer[1]) {
    case  0: SET_PWM( 0, pwm); break;
    case  2: SET_PWM( 2, pwm); break;
    case  7: SET_PWM( 7, pwm); break;
    case  8: SET_PWM( 8, pwm); break;
    case  9: SET_PWM( 9, pwm); break;
    case 10: SET_PWM(10, pwm); break;
    case 13: SET_PWM(13, pwm); break;
    case 14: SET_PWM(14, pwm); break;
    case 17: SET_PWM(17, pwm); break;
    case 19: SET_PWM(19, pwm); break;
    case 21: SET_PWM(21, pwm); break;
    case 20: SET_PWM(20, pwm); break;
    case 22: SET_PWM(22, pwm); break;
    default:
      Serial.print("{\"error\": \"Unknown pin ");
      Serial.print((int)commandBuffer[1], DEC);
      Serial.print(" for the set speed command\"}\n");
  }
}
