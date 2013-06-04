afancontrol
===========
Advanced fan speed control daemon for your Linux box.

Information
===========
This program lets you create complex configurations of fans speed control.
Fans must support PWM control.
Temperature sources might be files, HDDs, our own scripts.
You can create almost any desired configuration for your specific case.
See config file for more info.

Dependencies
============
* hddtemp
* Python 3.2 or newer
* lm_sensors
* Supported monitoring device on your motherboard. See this list: http://www.lm-sensors.org/wiki/Devices

Installation
============
1. Edit config to suit you needs. You might want to place it in /etc/afancontrol/afancontrol.conf as it is default config path.
2. Place executables anywhere in your system.
For example: chmod +x {afancontrol,afancontrol_fantest}; cp {afancontrol,afancontrol_fantest} /usr/local/sbin/
3. Edit afancontrol.initd script to suit your environment
4. chmod +x afancontrol.initd; mv afancontrol.initd /etc/init.d/afancontrol
5. Check that everything is OK: /etc/init.d/afancontrol test && /etc/init.d/afancontrol start
6. Add program to autostart. Debian/Ubuntu: update-rc.d afancontrol defaults


