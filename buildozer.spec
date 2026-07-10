[app]

# (str) Title of your application
title = TV Player

# (str) Package name
package.name = tvplayer

# (str) Package domain (needed for android/ios packaging)
package.domain = org.kivy

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,json,m3u,txt,md

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,filetype,requests

# (str) Supported orientation
orientation = landscape

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK

# Indicate as target API level the minimum required.
android.api = 33

# Indicate as minimum API level required.
android.minapi = 21

# (int) Android SDK version to use
android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25.2.9519653

# (int) Android NDK API level
android.ndk.api = 21

# (bool) Use private site-packages
p4a.bootstrap = sdl2

# (str) Android logcat filters
android.logcat_filters = *:S python:D

# (bool) Indicate if source code should be stripped
strip = False

# (bool) Avoid certain native .so's being pyloaded
avoid_source_extensions = 

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Path to build artifact storage
bin = ./bin
