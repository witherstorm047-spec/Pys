[app]
title = ATHENA NEXUS
package.name = athenanexus
package.domain = org.athena
source.dir = .
source.include_exts = py,json,npz,png,jpg,ttf
version = 1.0
requirements = python3,numpy,pygame
orientation = landscape
fullscreen = 1
android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
