#!/bin/sh
# X session entry: launch the cast app on the PiTFT (/dev/fb1).
# Installed to ~/.xinitrc by install_service.sh.
# Rotation is handled by the config.txt overlay (rotate=), not xrandr —
# the PiTFT is an SPI framebuffer (fbdev), which does not support RandR rotation.
APP_DIR="@APP_DIR@"
exec "$APP_DIR/scripts/start_app.sh"
