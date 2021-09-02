# aura-pt-release
This repository serves as the space for all the latest Aura-PT software releases


V1.4

A bug was identified in the PT program. When a user saves a custom set of alarms on the sensor board memory chip, it erases the data on other memory addresses. This will result in an OVF reading on Oxygen. 

Fix:
1. Download the o2comp.dat and reprogram all the sensors.
2. Update AuraPT with v1.4
