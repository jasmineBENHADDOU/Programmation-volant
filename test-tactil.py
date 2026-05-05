from gpiozero import Button
from signal import pause

hall = Button(17, pull_up=True)

def detected():
    print("1")

def removed():
    print("0")

hall.when_pressed = detected
hall.when_released = removed

pause()