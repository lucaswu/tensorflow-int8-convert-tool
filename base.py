import platform
from builtins import *
from functools import cmp_to_key
import re
import os

isWindows=(platform.system()=="Windows")

import ctypes
STD_OUTPUT_HANDLE= -11
class TextColor:
    BLACK     = 0  # - black
    DaBLUE    = 1  # - dark blue
    DaGREEN   = 2  # - dark green
    DaCYAN    = 3  # - dark cyan
    DaRED     = 4  # - dark red
    DaMAGENTA = 5  # - dark magenta
    GOLDEN    = 6  # - golden
    GRAY      = 7  # - gray
    DaGRAY    = 8  # - dark gray
    BLUE      = 9  # - blue
    GREEN     = 10 # - green
    CYAN      = 11 # - cyan
    RED       = 12 # - red
    MAGENTA   = 13 # - magenta
    YELLOW    = 14 # - yellow
    WHITE     = 15 # - white

if(isWindows):
    _std_out_handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

#import sys
import types
_win_color_map = {"black":0, "dark blue":1,"dark green":2, "dark cyan":3, "dark red":4, "dark magenta":5, "dark pink":5, "golden":6, 
        "gray":7, "dark gray":8, "blue":9, "green":10, "cyan":11, "red":12, "magenta":13, "pink":13, "yellow":14, "white":15}

_linux_color_map={"end":"\033[0m", "black":"\033[0;30m", "red":"\033[1;31m", "green":"\033[1;32m", "yellow":"\033[1;33m", 
                 "blue":"\033[1;34m", "magenta":"\033[1;35m", "pink":"\033[1;35m", "cyan":"\033[1;36m", "white":"\033[1;37m","gray":"\033[0;37m",
                 "dark blue":"\033[0;34m", "dark red":"\033[0;31m", "dark green":"\033[0;32m", "golden":"\033[0;33m", 
                 "dark magenta":"\033[0;35m", "dark gray":"\033[0;37m", "dark cyan":"\033[0;36m"}
_linux_color_list=["black", "red", "green", "yellow","blue", "magenta", "pink", "cyan", "white", "gray", "dark blue", "dark red", "dark green",
                   "golden", "dark magenta", "dark gray", "dark cyan"]

def printf(print_text, *args, textColor="white", end = "", isPrint=True):
    ''' 
    printf is similar to print but with more text color parameter AND do not append a newline by default.
    textColor: use const int value [TextColor.RED, TextColor.GREEN, TextColor.BLUE, TextColor.YELLOW, TextColor.WHITE, ...]
               or string value ['red', 'green', 'blue', 'yellow', 'white', ...]
    print_text: text to print
    args: more arguments to print
    '''
    if(isPrint==False):
        return

    if(isWindows):
        if(type(textColor)==type('a')):
            textColor=textColor.lower()
            textColor=_win_color_map[textColor]
        ctypes.windll.kernel32.SetConsoleTextAttribute(_std_out_handle, textColor)
        print(print_text % args, end=end, flush=True)
        ctypes.windll.kernel32.SetConsoleTextAttribute(_std_out_handle, TextColor.WHITE)
    else:
        if(type(textColor)==type(1)):
            textColor=_linux_color_list[textColor]
        textColor=textColor.lower()
        s = print_text % args
        s = _linux_color_map[textColor] + s +_linux_color_map["end"]
        print(s, end=end, flush=True)

def setConsoleColor(textColor='red'):
    if(isWindows):
        if(type(textColor)==type('a')):
            textColor=textColor.lower()
            textColor=_win_color_map[textColor]
        ctypes.windll.kernel32.SetConsoleTextAttribute(_std_out_handle, textColor)

def print2(print_text, *args, textColor="white", end = "\n", isPrint=True, isFlush=False):
    ''' 
    print2 is similar to print but with more text color parameter.
    textColor: use const int value [TextColor.RED, TextColor.GREEN, TextColor.BLUE, TextColor.YELLOW, TextColor.WHITE, ...]
               or string value ['red', 'green', 'blue', 'yellow', 'white', ...]
    print_text: text to print
    args: more arguments to print
    '''
    if(isPrint==False):
        return

    flush=False if end=='\n' else True
    if(isFlush): flush=True
    n=len(args)
    if(isWindows):
        if(type(textColor)==type('a')):
            textColor=textColor.lower()
            textColor=_win_color_map[textColor]
        ctypes.windll.kernel32.SetConsoleTextAttribute(_std_out_handle, textColor)
        if(n==0 or args==((),)):
            print(print_text, end=end, flush=flush)
        elif(n==1):
            print(print_text, args[0], end=end, flush=flush)
        else:
            print(print_text, args, end=end, flush=flush)
        ctypes.windll.kernel32.SetConsoleTextAttribute(_std_out_handle, TextColor.WHITE)
    else:
        if(type(textColor)==type(1)):
            textColor=_linux_color_list[textColor]
        textColor=textColor.lower()
        s = _linux_color_map[textColor] + str(print_text) +_linux_color_map["end"]
        if(n==0 or args==((),)):
            print(s, end=end, flush=flush)
        elif(n==1):
            print(s, args[0], end=end, flush=flush)
        else:
            print(s, args, end=end, flush=flush)

def mkdir(dir_path, empty_dir=True, isPrint=True):
    """
    dir_path: path of the folder
    empty_dir: if the folder exists then delete all files in the folder.
    """
    print(dir_path)
    import shutil
    if(empty_dir):
        if(os.path.exists(dir_path)):
            try:
                shutil.rmtree(dir_path)
                # print2("delete all files in '%s'" % dir_path, textColor='magenta', isPrint=isPrint)
            except:
                print2("mkdir: delte files in '%s' failed"%(dir_path), textColor='red', isPrint=isPrint)
    try:
        os.makedirs(dir_path, exist_ok=True)
    except:
        print2("mkdir: makedirs '%s' failed"%(dir_path), textColor='red', isPrint=isPrint)
    # print2("create '%s'" % dir_path, textColor='green', isPrint=isPrint)

makeDir = mkdir

import time
class Timer:
    """
    usage: 
          T=Timer()
          T.begin()
          # the code you want to estimate timing
          T.end("Fun")
    """
    def __init__(self):
        self.__freq = self._get_frequency()
        self.set_global_start()

    def _get_frequency(self):
        if(isWindows):
            freq=ctypes.c_longlong(0)
            ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
            freq=freq.value
        else:
            freq=1.0
        return freq

    def _get_time(self):
        if(isWindows):
            t=ctypes.c_longlong(0)
            ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(t))
            _t=t.value
        else:
            _t=time.time()
        return _t

    def set_global_start(self):
        self.__start = self._get_time()
        return self.__start

    def begin(self):
        self.__t1 = self._get_time()
        return self.__t1

    def end(self, tag = 'run', isPrint=True, end='\n', textColor=None):
        """
        used to print program running time
        tag: main message to print
        isPrint: whether print or not

        the return value is the milliseconds which between begin() and end()
        """
        self.__t2 = self._get_time()
        millisec=1000.0*(self.__t2-self.__t1)/self.__freq
        self.__end = self.__t2
        if(isPrint):
            if(millisec>1000):
                printf("%s time=%.3f sec", tag, millisec/1000.0, textColor="red" if(textColor==None) else textColor, end=end)
            elif(millisec>1):
                printf("%s time=%3.0f ms", tag, millisec, textColor="green" if(textColor==None) else textColor, end=end)
            else:
                printf("%s time=%3.0f us", tag, millisec*1000.0, textColor="yellow" if(textColor==None) else textColor, end=end)
        self.__t1=self.__t2
        self.millisec = millisec
        return millisec

    def pass_time(self, use_end_time=True, out_str=True):
        'pass_time(out_str=True, use_end_time=True)'
        if(use_end_time!=True):
            self.__end = self._get_time()
        self._pass_sec = (self.__end-self.__start)/self.__freq
        [h,m,s] = secToHMS(self._pass_sec)
        if(out_str):
            return "%02d:%02d:%02d"%(h,m,s)
        return [h,m,s]

    def rest_time(self, pass_idx, total_idx, out_str=True):
        'rest_time(pass_idx, total_idx, out_str=True)'
        pass_idx = max(1, pass_idx+1)
        rest_idx = total_idx-pass_idx
        self._pass_sec = (self.__end-self.__start)/self.__freq
        rest_sec = self._pass_sec*rest_idx/pass_idx
        [h,m,s] = secToHMS(rest_sec)
        if(out_str):
            return "%02d:%02d:%02d"%(h,m,s)
        return [h,m,s]