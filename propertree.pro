TEMPLATE = app

CONFIG += \
          console \
#          c++11 \
          sdk_no_version_check

CONFIG -= \
         app_bundle \
         qt

SOURCES += \
    propertree.build/static_src/MetaPathBasedLoader.c \
    propertree.build/static_src/CompiledCellType.c \
    propertree.build/static_src/CompiledCodeHelpers.c \
    propertree.build/static_src/CompiledFrameType.c \
    propertree.build/static_src/CompiledFunctionType.c \
    propertree.build/static_src/CompiledGeneratorType.c \
    propertree.build/static_src/InspectPatcher.c \
    propertree.build/static_src/MainProgram.c

VERSION = 0.1.2

TARGET = propertree
macx:TARGET = "ProperTree.app"

!win32:!macx {
    # Linux: static link and extra security (see: https://wiki.debian.org/Hardening)
    LIBS += -Wl,-Bstatic -Wl,-z,relro -Wl,-z,now
}

# This is to emulate the behaviour of SingleExe.scons
QMAKE_CFLAGS *=   -D_NUITKA_SYSFLAG_PY3K_WARNING=0 \
                  -D_NUITKA_SYSFLAG_DIVISION_WARNING=0 \
                  -D_NUITKA_SYSFLAG_UNICODE=0 \
                  -D_NUITKA_SYSFLAG_OPTIMIZE=0 \
                  -D_NUITKA_SYSFLAG_NO_SITE=0 \
                  -D_NUITKA_SYSFLAG_VERBOSE=0 \
                  -D_NUITKA_SYSFLAG_BYTES_WARNING=0 \
                  -D_NUITKA_SYSFLAG_NO_SITE=0

QMAKE_CFLAGS *= -D_FORTIFY_SOURCE=2 -O2 -fPIE -fstack-protector-all
QMAKE_CXXFLAGS *= -D_FORTIFY_SOURCE=2 -O2 -fPIE -fstack-protector-all

QMAKE_LFLAGS *= -fstack-protector-all
win32:QMAKE_LFLAGS *= -Wl,--dynamicbase -Wl,--nxcompat
win32:QMAKE_LFLAGS *= -Wl,--large-address-aware

isEmpty( PYTHON_VERSION ) {
  win32:PYTHON_VERSION=27
  unix:PYTHON_VERSION=2.7
}

QMAKE_CFLAGS_WARN_ON = -fdiagnostics-show-option -Wall -Wextra -Wformat -Wformat-security -Wno-unused-parameter -Wstack-protector
QMAKE_CXXFLAGS_WARN_ON = -fdiagnostics-show-option -Wall -Wextra -Wformat -Wformat-security -Wno-unused-parameter -Wstack-protector

PYTHON_VERSION=$$(PYTHON_VERSION)

macx {
  INCLUDEPATH += $$PWD/propertree.build
  INCLUDEPATH += /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/Frameworks/Python.framework/Headers/
  # TODO: Replace this with something less jank
  INCLUDEPATH += /usr/local/lib/python3.7/site-packages/nuitka/build/include/
  INCLUDEPATH += /usr/local/lib/python3.7/site-packages/nuitka/build/static_src/
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
