#!/bin/bash


while ! curl -s --connect-timeout 1 http://172.20.10.3 >/dev/null; do
    sleep 1
done

# Cache le curseur de la souris
unclutter -idle 0 &

exec /usr/bin/chromium \
  --kiosk \
  --start-maximized \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-translate \
  --disable-features=Translate,TranslateUI \
  --lang=en-US \
  --disable-component-update \
  --password-store=basic \
  --no-first-run \
  "http://172.20.10.3/Interface%20UI/1.Manitou.html"
