from gpiozero import Button
from signal import pause

# OUT du TTP223 connecté au GPIO17
touch_sensor = Button(17, pull_up=False)

def pressed():
    print("Capteur TTP223 touché")

def released():
    print("Capteur TTP223 relâché")

touch_sensor.when_pressed = pressed
touch_sensor.when_released = released

print("Test TTP223 en cours...")
pause()