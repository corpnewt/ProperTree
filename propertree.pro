# This file is used to compile the output from Cython
# To generate that output, run cython propertree.py --embed --cplus --warning-extra
TEMPLATE = app

CONFIG += \
          console \
          c++11 \
          sdk_no_version_check

CONFIG -= \
         app_bundle \
         qt

SOURCES += \
        propertree.cpp \
        scripts/plist.cpp \
        scripts/plistwindow.cpp \
        scripts/run.cpp \
        scripts/utils.cpp

VERSION = 0.1.2

TARGET = propertree
macx:TARGET = "ProperTree.app"

!win32:!macx {
    # Linux: static link and extra security (see: https://wiki.debian.org/Hardening)
    LIBS += -Wl,-Bstatic -Wl,-z,relro -Wl,-z,now
}

QMAKE_CXXFLAGS *= -D_FORTIFY_SOURCE=2 -O2 -fPIE -fstack-protector-all
QMAKE_LFLAGS *= -fstack-protector-all
win32:QMAKE_LFLAGS *= -Wl,--dynamicbase -Wl,--nxcompat
win32:QMAKE_LFLAGS *= -Wl,--large-address-aware

isEmpty( PYTHON_VERSION ) {
  win32:PYTHON_VERSION=27
  unix:PYTHON_VERSION=2.7
}

QMAKE_CXXFLAGS_WARN_ON = -fdiagnostics-show-option -Wall -Wextra -Wformat -Wformat-security -Wno-unused-parameter -Wstack-protector

PYTHON_VERSION=$$(PYTHON_VERSION)

macx {
  INCLUDEPATH += /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/Frameworks/Python.framework/Headers/
  LIBS += -F/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/Frameworks -framework Python
} else:win32 {
  CONFIG(debug, debug|release) {
  DEBUG_EXT = _d
  } else {
    DEBUG_EXT =
  }
  win32:INCLUDEPATH += $$(PYTHON_PATH)/PC $$(PYTHON_PATH)/include
  win32:LIBS += $$(PYTHON_LIB)/python$${PYTHON_VERSION}$${DEBUG_EXT}.lib
} else:unix {
    system(python$${PYTHON_VERSION}-config --embed --libs) {
    unix:LIBS += $$system(python$${PYTHON_VERSION}-config --embed --libs)
} else: unix:LIBS += $$system(python$${PYTHON_VERSION}-config --libs)
    unix:QMAKE_CXXFLAGS += $$system(python$${PYTHON_VERSION}-config --includes)
}

win32:DEFINES += WIN32
win32:RC_FILE = misc/propertree.rc

win32:!contains(MINGW_THREAD_BUGFIX, 0) {
    DEFINES += _MT
    QMAKE_LIBS_QT_ENTRY = -lmingwthrd $$QMAKE_LIBS_QT_ENTRY
}

!win32:!macx {
    DEFINES += LINUX
    LIBS += -lrt
    # _FILE_OFFSET_BITS=64 lets 32-bit fopen transparently support large files.
    DEFINES += _FILE_OFFSET_BITS=64
}

macx:ICON =
macx:QMAKE_INFO_PLIST = misc/propertree.plist

contains(RELEASE, 1) {
    !win32:!macx {
        # Linux: turn dynamic linking back on for c/c++ runtime libraries
        LIBS += -Wl,-Bdynamic
    }
}

# QMAKE_POST_LINK=$(STRIP) $(TARGET)

DISTFILES += \
    misc/logos/AppIcon.icns
