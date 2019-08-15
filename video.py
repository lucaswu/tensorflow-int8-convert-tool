#! /usr/bin/python
# -*- coding: utf8 -*-
from __future__ import division, print_function, absolute_import

import sys
import os
import numpy as np
import scipy.misc
from base import *
import subprocess as sp
import re


try:
    from subprocess import DEVNULL  # py3k
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

FFMPEG_BINARY="ffmpeg.exe" if(platform.system()=="Windows") else "ffmpeg"

def print_debug(print_text, *args, textColor="white", end = "\n", isPrint=True):
        print2(print_text, args, textColor=textColor, end=end)

def _parse_infos(filename, print_infos=False):
    T = Timer()
    is_GIF = filename.endswith('.gif')
    cmd = [FFMPEG_BINARY, "-i", filename]
    if is_GIF:
        cmd += ["-f", "null", "/dev/null"]
    popen_params = {"bufsize": 1024*1024, "stdout": sp.PIPE, "stderr": sp.PIPE, "stdin": DEVNULL}
    if os.name == "nt":
        popen_params["creationflags"] = 0x08000000
    #T.begin()
    proc = sp.Popen(cmd, **popen_params)
    infos = proc.stderr.read().decode('utf8')
    proc.communicate()
    del proc
    #T.end()

    if print_infos:
        # print the whole info text returned by FFMPEG
        print_debug(infos, textColor='gray')

    lines = infos.splitlines()
    if "No such file or directory" in lines[-1]:
        raise IOError("MoviePy error: the file %s could not be found !\nPlease check that you entered the correct path."%filename)

    result = dict()

    # get duration (in seconds)
    try:
        keyword = ('frame=' if is_GIF else 'Duration: ')
        line = [l for l in lines if keyword in l][0]
        match = re.findall(r"Duration: (\d+):(\d+):(\d+).(\d+)", line)[0]
        sec = 3600*int(match[0])+60*int(match[1])+int(match[2])+int(match[3])/100.0
        result['video_duration'] = sec
    except:
        raise IOError("MoviePy error: failed to read the duration of file %s.\nHere are the file infos returned by ffmpeg:\n\n%s"%(filename, infos))
        
    # get the output line that speaks about video
    lines_video = [l for l in lines if ' Video: ' in l and re.search(r'\d+x\d+', l)]
    result['video_found'] = ( lines_video != [] )
    if result['video_found']:
        try:
            line = lines_video[0]
            # get the size, of the form 460x320 (w x h)
            match = re.search(" [0-9]*x[0-9]*(,| )", line)
            s = list(map(int, line[match.start():match.end()-1].split('x')))
            result['video_size'] = s
        except:
            raise IOError(("MoviePy error: failed to read video dimensions in file %s.\nHere are the file infos returned by ffmpeg:\n\n%s")%(filename, infos))

        # get the frame rate. Sometimes it's 'tbr', sometimes 'fps', sometimes
        # tbc, and sometimes tbc/2...
        # Current policy: Trust tbr first, then fps. If result is near from x*1000/1001
        # where x is 23,24,25,50, replace by x*1000/1001 (very common case for the fps).
        try:
            match = re.search(r"( [0-9]*.| )[0-9]* tbr", line)
            tbr = float(line[match.start():match.end()].split(' ')[1])
            result['video_fps'] = tbr
        except:
            match = re.search(r"( [0-9]*.| )[0-9]* fps", line)
            result['video_fps'] = float(line[match.start():match.end()].split(' ')[1])

        # It is known that a fps of 24 is often written as 24000/1001
        # but then ffmpeg nicely rounds it to 23.98, which we hate.
        coef = 1000.0/1001.0
        fps = result['video_fps']
        for x in [23,24,25,30,50]:
            if (fps!=x) and abs(fps - x*coef) < 0.01:
                result['video_fps'] = x*coef
        result['video_nframes'] = int(result['video_duration']*result['video_fps'])

        # We could have also recomputed the duration from the number
        # of frames, as follows:
        # >>> result['video_duration'] = result['video_nframes'] / result['video_fps']

    lines_audio = [l for l in lines if ' Audio: ' in l]

    result['audio_found'] = (lines_audio != [])
    if result['audio_found']:
        line = lines_audio[0]
        try:
            match = re.search(r" [0-9]* Hz", line)
            result['audio_fps'] = int(line[match.start()+1:match.end()])
        except:
            result['audio_fps'] = 'unknown'
    #T.end()
    return result

_pix_fmt_dict={'rgb24':'rgb24', 'bgr24':'bgr24', 'rgb':'rgb24', 'bgr':'bgr24', 'yuv420p':'yuv420p', 'yuv444p':'yuv444p', 'i420':'yuv420p', 'i444':'yuv444p', 'gray':'gray'}

class VideoReader:
    def __init__(this, filename, buf_frames=10, wxh=None, pix_fmt='rgb'):
        this.filename = filename
        res = _parse_infos(filename, False)
        this.fps = res['video_fps']
        this.size = res['video_size']
        this.duration = res['video_duration']
        this.frame_num = res['video_nframes']
        this.pix_fmt = _pix_fmt_dict[pix_fmt.lower()] #'rgb24'
        this.wxh = wxh if(wxh!=None and (wxh[0]!=this.size[0] or wxh[1]!=this.size[1])) else None
        [this.w, this.h, this.cn] = [this.size[0], this.size[1], 3] if(wxh==None) else [wxh[0], wxh[1], 3]
        this.buf_frames = max(1, buf_frames)
        this.popen_buf_size = this.w*this.h*this.cn+1024
        #print_debug("fps=%g  size=%dx%d  frame_num=%d"%(this.fps, this.size[0], this.size[1], this.frame_num), textColor='green')
        this.initialize()
        #print_debug("open '%s'"%(filename), textColor='green')
        #this.video_mem = VideoMemory(this.buf_frames, this.w, this.h, this.cn)

    def _get_frame_bytes(this):
        if(this.pix_fmt=='rgb24' or this.pix_fmt=='bgr24'):
            return this.w*this.h*this.cn
        if(this.pix_fmt=='yuv420p'):
            return this.w*this.h+2*((this.w//2)*(this.h//2))
        if(this.pix_fmt=='yuv444p'):
            return this.w*this.h*3
        if(this.pix_fmt=='gray'):
            return this.w*this.h

    def initialize(this, pos=0):
        """Opens the file, creates the pipe. """
        #print_debug("initialize(pos=%d)"%(pos), textColor='magenta')
        this.close(False) # if any
        cmd = [FFMPEG_BINARY]
        if(pos>0):
            cmd += ['-ss', "%.6f"%((pos-0.5)/this.fps)]
        if(this.wxh==None):
            cmd += ['-i', this.filename, '-loglevel', 'error', '-f', 'image2pipe', "-pix_fmt", this.pix_fmt, '-vcodec', 'rawvideo', '-']
        else:
            cmd += ['-i', this.filename, '-loglevel', 'error', '-f', 'image2pipe', "-pix_fmt", this.pix_fmt, '-vcodec', 'rawvideo', '-s', '%dx%d'%(this.wxh[0], this.wxh[1]), '-']
        popen_params = {"bufsize": this.popen_buf_size, "stdout": sp.PIPE, "stderr": sp.PIPE, "stdin": DEVNULL}
        if os.name == "nt":
            popen_params["creationflags"] = 0x08000000
        this.proc = sp.Popen(cmd, **popen_params)
        this.pos = pos-1

    def skip_frames(this, num=1):
        nbytes = this._get_frame_bytes()
        for i in range(num):
            s = this.proc.stdout.read(nbytes)
            #if(len(s)!=nbytes):
            #    frame = this.video_mem.get_frame(this.pos)
            #else:
            #    frame = np.fromstring(s, dtype=np.uint8).reshape([this.h, this.w, this.cn])
            this.pos += 1
            #this.video_mem.set_frame(frame, this.pos)

    def read_frame(this):
        nbytes = this._get_frame_bytes()
        s = this.proc.stdout.read(nbytes)
        if(len(s)!=nbytes):
            # print2("Warning: in file %s, "%(this.filename)+"%d bytes wanted but %d bytes read,"%(nbytes, len(s))+"at frame %d/%d, at time %.2f/%.2f sec. "%(this.pos,this.frame_num, this.pos/this.fps, this.duration)+"Using the last valid frame instead.", textColor='red')
            if(not hasattr(this, 'last_read')):
                raise IOError(("MoviePy error: failed to read the first frame of video file %s. That might mean that the file is corrupted. That may also mean that you are using a deprecated version of FFMPEG. On Ubuntu/Debian "
                                   "for instance the version in the repos is deprecated. Please update to a recent version from the website.")%(this.filename))
            frame = this.last_read
        else:
            frame = np.fromstring(s, dtype=np.uint8)
            if(this.pix_fmt=='rgb24' or this.pix_fmt=='bgr24'):
                frame = frame.reshape([this.h, this.w, this.cn])
            elif(this.pix_fmt=='yuv444p'):
                frame = frame.reshape([3, this.h, this.w])
            elif(this.pix_fmt=='yuv420p'):
                frame = frame.reshape([6, this.h//2, this.w//2])
            elif(this.pix_fmt=='gray'):
                frame = frame.reshape([this.h, this.w])
            this.last_read = frame
            this.pos += 1
        return frame

    def get_frame(this, pos):
        pos = min(max(0, pos), this.frame_num-1)
        #frame = this.video_mem.get_frame(pos)
        #if(type(frame)!=type(None)):
        #    return frame
        if(pos==this.pos):
            return this.last_read
        if(pos<this.pos or pos>this.pos+this.buf_frames):
            #print_debug("reset(pos=%d this.pos=%d)"%(pos, this.pos), textColor='blue')
            this.initialize(0 if(pos<this.buf_frames) else pos)
        this.skip_frames(pos-this.pos-1)
        frame = this.read_frame()
        #this.video_mem.set_frame(frame, pos)
        return frame

    def close(this, isPrint=True):
        if(hasattr(this, 'proc')):
            this.proc.terminate()
            this.proc.stdout.close()
            this.proc.stderr.close()
            this.proc.wait()
            del this.proc
            # print_debug("VideoReader.close(%s)"%(this.filename), textColor='magenta', isPrint=isPrint)

    def __del__(this):
        this.close()
        if(hasattr(this, 'last_read')):
            del this.last_read
        #if(hasattr(this, 'video_mem')):
        #    del this.video_mem
        #if(hasattr(this, 'filename')): print_debug("VideoReader.__del__.close(%s)"%(this.filename), textColor='magenta')

class VideoWriter:
    def __init__(this, filename, fps=30, pix_fmt='rgb24', wxh=None, preset=None, bitrate=None, crf=None, threads=None, audiofile=None, logfile=None, ffmpeg_params=None):
        """
        VideoWriter(filename, fps=30, preset=None|'superfast'|'veryfast'|'medium', bitrate=None, crf=None, threads=None, audiofile=None, logfile=None, ffmpeg_params=None)
        """
        this.filename = filename
        this.codec = "libx264"
        this.ext = this.filename.split(".")[-1]
        this.fps = fps
        this.preset = preset
        this.bitrate = bitrate
        this.threads = threads
        this.audiofile = audiofile
        this.logfile = sp.PIPE if(logfile==None) else logfile
        this.pix_fmt = _pix_fmt_dict[pix_fmt.lower()] #'rgb24'
        this.wxh = wxh
        this.ffmpeg_params = ffmpeg_params
        this.pos = 0
        this.crf = crf

    def initialize(this, size):
        # order is important
        loglevel = ('error' if(this.logfile == sp.PIPE) else 'info')
        cmd = [FFMPEG_BINARY, '-y','-loglevel', loglevel, '-f', 'rawvideo', '-vcodec', 'rawvideo','-s', '%dx%d' % (size[0], size[1]),
               '-pix_fmt', this.pix_fmt, '-r', '%.2f'%this.fps, '-i', '-', '-an']
        if(this.audiofile!=None):
            cmd += ['-i', this.audiofile, '-acodec', 'copy']
        cmd += ['-vcodec', this.codec]
        if(this.preset!=None):
            cmd += ['-preset', this.preset]
        if(this.crf!=None):
            cmd += ['-crf', '%d'%(this.crf)]
            # cmd += ["-maxrate", "3660k"]
            # cmd += ["-bufsize", "6000k"] #4000,4500
        if(this.ffmpeg_params!=None):
            cmd += this.ffmpeg_params
        if(this.bitrate!= None):
            cmd += ['-vb', "%dk"%this.bitrate]
        if(this.threads!=None):
            cmd += ["-threads", str(this.threads)]
        if((size[0] % 2 == 0) and (size[1] % 2 == 0)):
            cmd += ['-pix_fmt', 'yuv420p']
        cmd += [this.filename]
        popen_params = {"stdout": DEVNULL, "stderr": this.logfile, "stdin": sp.PIPE}
        # This was added so that no extra unwanted window opens on windows
        # when the child process is created
        if(os.name == "nt"):
            popen_params["creationflags"] = 0x08000000
        this.proc = sp.Popen(cmd, **popen_params)

    def set_frame(this, frame):
        """ Writes one frame in the file."""
        if(this.pos==0):
            this.initialize([frame.shape[1], frame.shape[0]] if(this.wxh==None) else this.wxh)
        try:
            # a = 1
            # if sys.version_info.major >= 3:
            #     this.proc.stdin.write(frame)
            # else:
            #     this.proc.stdin.write(frame)
            if sys.version_info.major >=3:
               this.proc.stdin.write(frame.tobytes())
            else:
               this.proc.stdin.write(frame.tostring())

        except IOError as err:
            ffmpeg_error = this.proc.stderr.read()
            error = (str(err) + ("\n\nMoviePy error: FFMPEG encountered the following error while writing file %s:\n\n %s" % (this.filename, ffmpeg_error)))

            if b"Unknown encoder" in ffmpeg_error:
                error = error+("\n\nThe video export failed because FFMPEG didn't find the specified codec for video encoding (%s). Please install this codec or change the codec when calling "
                  "write_videofile. For instance:\n  >>> clip.write_videofile('myvid.webm', codec='libvpx')")%(this.codec)

            elif b"incorrect codec parameters ?" in ffmpeg_error:
                 error = error+("\n\nThe video export failed, possibly because the codec specified for the video (%s) is not compatible with the given "
                  "extension (%s). Please specify a valid 'codec' argument in write_videofile. This would be 'libx264' or 'mpeg4' for mp4, 'libtheora' for ogv, 'libvpx for webm. "
                  "Another possible reason is that the audio codec was not compatible with the video codec. For instance the video extensions 'ogv' and 'webm' only allow 'libvorbis' (default) as a"
                  "video codec.")%(this.codec, this.ext)

            elif  b"encoder setup failed" in ffmpeg_error:
                error = error+("\n\nThe video export failed, possibly because the bitrate you specified was too high or too low for the video codec.")
            elif b"Invalid encoder type" in ffmpeg_error:
                error = error + ("\n\nThe video export failed because the codec or file extension you provided is not a video")
            raise IOError(error)
        this.pos += 1
        return frame

    def close(this, isPrint=True):
        if(hasattr(this, 'proc')):
            this.proc.stdin.close()
            if this.proc.stderr is not None:
                this.proc.stderr.close()
            this.proc.wait()
            del this.proc
            print_debug("video has saved to '%s'"%(this.filename), textColor='magenta', isPrint=isPrint)

    def __del__(this):
        this.close(False)
        #if(hasattr(this, 'filename')): print_debug("VideoWriter.__del__.close(%s)"%(this.filename), textColor='magenta')

    @staticmethod
    def parse_video_info(filename, print_infos=False):
        "return [frame_num, w, h, fps]"
        info = _parse_infos(filename, print_infos)
        fps = info['video_fps']
        size = info['video_size']
        duration = info['video_duration']
        frame_num = info['video_nframes']
        [w, h, cn] = [size[0], size[1], 3]
        return [frame_num, w, h, fps]

    @staticmethod
    def video_to_yuv(avi_name, yuv_name, wxh=None, start_sec=None, duration_sec=None, threads=1):
        "ffmpeg.exe -i pandakill_8.mp4 -pix_fmt yuv420p -y pandakill_1920x1080.yuv"
        wxh = "%dx%d"%(wxh[0],wxh[1]) if(type(wxh)==type([])) else wxh
        [n,w,h,fps] = VideoWriter.parse_video_info(avi_name)
        name = os.path.splitext(yuv_name)
        new_name = name[0]+'.yuv'
        if(start_sec!=None and duration_sec!=None):
            cmd = '%s -ss %.6f -t %.6f -i "%s" '%(FFMPEG_BINARY, start_sec, duration_sec, avi_name)
        else:
            cmd = '%s -i "%s" '%(FFMPEG_BINARY, avi_name)
        if(wxh!=None and ('%dx%d'%(w,h))!=wxh):
            cmd += '-s %s '%wxh
        if(threads!=None):
            cmd += "-threads %d "%(threads)
        cmd += '-pix_fmt yuv420p -y "%s" '%(new_name)
        os.system(cmd)
        if(new_name!=yuv_name):
            if(os.path.exists(yuv_name)):
                os.remove(yuv_name)
            os.rename(new_name, yuv_name)

    @staticmethod
    def yuv_to_video(yuv_name, avi_name, wxh, fps):
        wxh = "%dx%d"%(wxh[0],wxh[1]) if(type(wxh)==type([])) else wxh
        name = os.path.splitext(yuv_name)
        new_name = name[0]+'.yuv'
        if(new_name!=yuv_name): os.rename(yuv_name, new_name)
        cmd = '%s -s %s -pix_fmt yuv420p -i "%s" -y -vcodec libx264 -preset slow -r %f "%s"'%(FFMPEG_BINARY, wxh, new_name, fps, avi_name)
        print_debug(cmd, textColor='green')
        os.system(cmd)
        if(new_name!=yuv_name): os.rename(new_name, yuv_name)

    @staticmethod
    def video_encode(src_name, dst_name, wxh=None, bitrate=None, threads=4, preset='slow', start_sec=None, duration_sec=None, copy_video=False, crf=None, remove_audio=False, fps=None):
        if(os.path.exists(src_name)==False):
            print_debug("'%s' is not exit"%(src_name), textColor='red')
            return None
        #print2("Note: video_encode may cause frame mismatching problem. You'd better use video_encode2.", textColor='red')
        fileTypes = ['.avi', '.mp4', '.flv', '.mov', '.mkv']
        if os.path.splitext(src_name)[1] not in fileTypes:
            # print2("skip %s" % src_name, textColor='red')
            return None
        cmd = [FFMPEG_BINARY]
        if(start_sec!=None):
            cmd += ['-ss', "%.6f"%start_sec]
            if(duration_sec!=None):
                cmd += ['-t', "%.6f"%duration_sec]
            cmd += ['-accurate_seek']
        if(copy_video):
            cmd += ['-i', src_name,'-y', '-f', 'mp4', '-acodec', 'copy', '-vcodec', 'copy', '-avoid_negative_ts', '1'] if(remove_audio==False) else ['-i', src_name,'-y', '-f', 'mp4', '-an', '-vcodec', 'copy', '-avoid_negative_ts', '1']
        else:
            cmd += ['-i', src_name,'-y', '-f', 'mp4', '-acodec', 'copy', '-vcodec', 'libx264','-pix_fmt', 'yuv420p'] if(remove_audio==False) else ['-i', src_name,'-y', '-f', 'mp4', '-an', '-vcodec', 'libx264','-pix_fmt', 'yuv420p']
            if(wxh!=None):
                cmd += ['-s', '%dx%d'%(wxh[0],wxh[1]) if(type(wxh)==type([])) else wxh]
            if(preset!=None):
                cmd += ['-preset', preset]
            if(crf!=None):
                cmd += ['-crf', '%d'%(crf)]
            elif(bitrate!= None):
                cmd += ['-vb', "%dk"%(bitrate)]
        if(threads!=None):
            cmd += ["-threads", str(threads)]
        if(fps!=None):
            cmd += ['-r', '%f'%(fps)]
        cmd += [dst_name]
        popen_params = {"stdout": sp.PIPE, "stderr": sp.PIPE, "stdin": DEVNULL}
        # This was added so that no extra unwanted window opens on windows
        # when the child process is created
        if(os.name == "nt"):
            popen_params["creationflags"] = 0x08000000
        #print_debug(cmd, textColor='green')
        proc = sp.Popen(cmd, **popen_params)
        infos = proc.stderr.read().decode('utf8')
        proc.communicate()
        del proc
        #print_debug(infos, textColor='gray')
        return infos

    @staticmethod
    def video_encode2(src_name, dst_name, wxh=None, bitrate=None, crf=None, threads=4, preset='slow', start_sec=None, duration_sec=None, isPrint=True):
        if(os.path.exists(src_name)==False):
            print_debug("'%s' is not exit"%(src_name), textColor='red')
            return None
        fileTypes = ['.avi', '.mp4', '.flv', '.mov', '.mkv']
        if os.path.splitext(src_name)[1] not in fileTypes:
            # print_debug("skip %s" % src_name, textColor='red')
            return None
        #[frame_num, w,h, fps] = Video.parse_video_info(src_name)
        reader = VideoReader(src_name, 1, wxh, 'I420')
        writer = VideoWriter(dst_name, reader.fps, 'I420', [reader.w, reader.h] if(wxh==None) else wxh, preset, bitrate, crf, threads)
        [start_idx, duration] = [int(start_sec*reader.fps+0.5), int(duration_sec*reader.fps+0.5)] if(start_sec!=None and duration_sec!=None) else [0, reader.frame_num]
        for i in range(start_idx, start_idx+duration):
            print_debug("\r%4d/%d"%(i-start_idx+1, duration), textColor='yellow', end='\t', isPrint=isPrint)
            frame = reader.get_frame(i)
            writer.set_frame(frame)
        print_debug("", isPrint=isPrint)
        reader.close(isPrint=False)
        writer.close(isPrint=False)

def YUV2RGB(Y, U, V):
    B = int(1.164*(Y - 16)                   + 2.018*(U - 128)+0.5)
    G = int(1.164*(Y - 16) - 0.813*(V - 128) - 0.391*(U - 128)+0.5)
    R = int(1.164*(Y - 16) + 1.596*(V - 128)+0.5)
    return [R,G,B]

def RGB2YUV(R, G, B):
    Y  =      int((0.257 * R) + (0.504 * G) + (0.098 * B) + 16+0.5)
    Cr = V =  int((0.439 * R) - (0.368 * G) - (0.071 * B) + 128+0.5)
    Cb = U = int(-(0.148 * R) - (0.291 * G) + (0.439 * B) + 128+0.5)
    return [Y,U,V]







