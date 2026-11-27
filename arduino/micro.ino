// The pins defined in this program are for the Arduino Micro.

#define PWM_STARTING_VALUE 255  // 0 = disabled, 255 = full speed.

/////////////////////////
// FAN PWM outputs:

// https://www.pjrc.com/teensy/td_libs_TimerOne.html
// https://github.com/PaulStoffregen/TimerOne
// https://github.com/PaulStoffregen/TimerThree
#include <TimerOne.h>
#include <TimerThree.h>

// TimerOne and TimerThree accept PWM duty values from 0 to 1023.
// The standard range for PWM fans on Linux is, however, from 0 to 255.
// The macro below converts values from the 0–255 range to the 0–1023 range.
#define PWM_255_TO_1023(PWM) ((PWM == 0) ? 0 : (1L * PWM + 1) * 4 - 1)

// These are the pins connected to timers 1 and 3 on the Arduino Micro.
// See https://www.pjrc.com/teensy/td_libs_TimerOne.html
byte currentPWM5;
byte currentPWM9;
byte currentPWM10;
byte currentPWM11;

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
int pulsesBufferPosition = 0;

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
  unsigned long now = millis(); \
  if (now - lastPulse##PIN < PULSES_ACCEPT_MIN_DURATION_MS) { lastPulse##PIN = now; return; } \
  lastPulse##PIN = now; \
  tachoPulses##PIN [pulsesBufferPosition] ++; \
}

#define TACHO_PULSES_ATTACH_INT(PIN) \
pinMode(PIN, INPUT); \
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

// These are the pins on the Arduino Micro that support interrupts.
// See https://www.arduino.cc/reference/en/language/functions/external-interrupts/attachinterrupt/
TACHO_PULSES_INT_FUNCTION(0);
TACHO_PULSES_INT_FUNCTION(1);
TACHO_PULSES_INT_FUNCTION(2);
TACHO_PULSES_INT_FUNCTION(3);
TACHO_PULSES_INT_FUNCTION(7);


/////////////////////////
// Serial commands:

char setSpeedCommand = '\xf1'; // The only supported command currently.
char commandBuffer[3];  // Buffer for the incoming command: [command; pin; speed].
int commandPosition = 0;  // The current position in the `commandBuffer`

/////////////////////////

void setup() {
  // https://github.com/PaulStoffregen/TimerOne/blob/master/examples/FanSpeed/FanSpeed.pde
  Timer1.initialize(40); // 40us == 25kHz
  Timer3.initialize(40);

  SET_PWM(5, PWM_STARTING_VALUE);
  SET_PWM(9, PWM_STARTING_VALUE);
  SET_PWM(10, PWM_STARTING_VALUE);
  SET_PWM(11, PWM_STARTING_VALUE);

  TACHO_PULSES_ATTACH_INT(0);
  TACHO_PULSES_ATTACH_INT(1);
  TACHO_PULSES_ATTACH_INT(2);
  TACHO_PULSES_ATTACH_INT(3);
  TACHO_PULSES_ATTACH_INT(7);

  Serial.begin(115200);
}

void loop () {

  Timer3.pwm(5, PWM_255_TO_1023(currentPWM5));
  Timer1.pwm(9, PWM_255_TO_1023(currentPWM9));
  Timer1.pwm(10, PWM_255_TO_1023(currentPWM10));
  Timer1.pwm(11, PWM_255_TO_1023(currentPWM11));

  // Measure RPM from tachometers:
  TACHO_PULSES_RESET_CURRENT_BUCKET(0);
  TACHO_PULSES_RESET_CURRENT_BUCKET(1);
  TACHO_PULSES_RESET_CURRENT_BUCKET(2);
  TACHO_PULSES_RESET_CURRENT_BUCKET(3);
  TACHO_PULSES_RESET_CURRENT_BUCKET(7);
  interrupts();
  delay (MEASUREMENT_TIME_MS);
  noInterrupts();
  TACHO_PULSES_NEXT_BUCKET;

  readSerialCommand();

  // Print the status (in JSON):

  Serial.print("{");

  Serial.print("\"fan_inputs\": {");
  PRINT_RPM_JSON(0);
  Serial.print(",");
  PRINT_RPM_JSON(1);
  Serial.print(",");
  PRINT_RPM_JSON(2);
  Serial.print(",");
  PRINT_RPM_JSON(3);
  Serial.print(",");
  PRINT_RPM_JSON(7);
  Serial.print("}, ");

  Serial.print("\"fan_pwm\": {");
  PRINT_PWM_JSON(5);
  Serial.print(",");
  PRINT_PWM_JSON(9);
  Serial.print(",");
  PRINT_PWM_JSON(10);
  Serial.print(",");
  PRINT_PWM_JSON(11);
  Serial.print("}");

  Serial.print("}\n");
}

void readSerialCommand() {
  while (Serial.available()) {
    char c = Serial.read();
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

  byte pwm = (byte)commandBuffer[2];
  switch (commandBuffer[1]) {
    case 5:  SET_PWM(5,  pwm); break;
    case 9:  SET_PWM(9,  pwm); break;
    case 10: SET_PWM(10, pwm); break;
    case 11: SET_PWM(11, pwm); break;
    default:
      Serial.print("{\"error\": \"Unknown pin ");
      Serial.print((int)commandBuffer[1], DEC);
      Serial.print(" for the set speed command\"}\n");
  }
}
