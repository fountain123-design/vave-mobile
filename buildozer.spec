[app]

# (str) Title of your application
title = VAVE 降本建议

# (str) Package name
package.name = vavemobile

# (str) Package domain (needed for android/ios packaging)
package.domain = com.vave.ai

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,json,ttc,otf,ttf,md

# (list) Source files to exclude (let empty to not exclude anything)
source.exclude_exts = spec,pyc,log

# (str) Application versioning (method 1)
version = 1.0

# (str) Supported orientation (one of landscape/portrait/square/allsensor/auto)
orientation = portrait

# (list) List of inclusions using pattern matching
# android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE
android.permissions = INTERNET

# (bool) Automatically accept Android SDK license (needed for headless CI builds)
android.accept_sdk_license = True

# (int) Android API to use
android.api = 33
android.minapi = 24

# (str) Android NDK version to use
android.ndk = 25b

# (bool) Android adaptive icon
android.adaptive_icon = False

# (str) Icon (if empty, the default icon is used)
# icon.filename = %(source.dir)s/data/icon.png

# (str) Presplash (if empty, the default presplash is used)
# presplash.filename = %(source.dir)s/data/presplash.png

# (list) Python for android requirements
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.1,requests,openai

# (str) Custom source folders for requirements
# requirements.source.kivy = ../../kivy

# (list) Garden requirements
# garden_requirements =

# (str) OUYA Console Category. Should be one of GAME or APP
# Only for OUYA
# ouya.category = GAME

# (str) Filename of OUYA Console icon. It must be a 732x412 png image.
# ouya.icon.filename = %(source.dir)s/data/ouya_icon.png

# (str) XML file to include as an intent filters in <activity> tag
# android.manifest.intent_filters = 

# (list) Pattern to whitelist for the whole project
# android.whitelist =

# (str) Path to a custom whitelist file
# android.whitelist_src =

# (str) Path to a custom blacklist file
# android.blacklist_src =

# (list) List of Java .jar files to add to the libs so that they are included in the classpath.
# android.add_jars = foo.jar,bar.jar

# (list) List of Java files to add to the android project (can be java or a
# directory containing the files)
# android.add_src =

# (list) Android AAR archives to add
# android.add_aars =

# (list) Android Library projects to add (list of paths)
# android.add_libs_android =

# (str) android.logcat_filters = *:S python:D
# android.logcat_filters = *:S python:D

# (bool) Copy library instead of making a symlink
# android.copy_libs = 1

# (str) The Android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a, armeabi-v7a

# (str) Pre-build hook to upgrade pip in venv (fix resolvelib incompatibility)
p4a.hook = %(source.dir)s/upgrade_pip_hook.py

# (bool) Show build platform warnings
log_level = 2

# (str) Path to build output (relative to buildozer.spec)
build_dir = ./build

[presplash]

[buildozer]

# (int) Log threshold (0 = everything, 1 = info, 2 = warning, 3 = error)
log_level = 2

# (int) Display warning if buildozer is older than this many days
warn_on_old_buildozer = 30

# (str) Space-separated full paths to other buildozer.spec files to include
# include = 

# (str) Path to a custom buildozer bin directory
# buildozer.bin_dir = ./bin
