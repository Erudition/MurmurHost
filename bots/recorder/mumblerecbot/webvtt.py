# -*- coding: utf-8 -*-

import codecs
import collections
import time

class WebVtt:
    """
    Creates a transcript in WebVTT format (.vtt).
    This handles speaker labels and system events (started/stopped).
    """
    def __init__(self, filename, regions=None):
        # We use UTF-8-SIG as it's the most compatible with Windows/Video editors.
        self.file = codecs.open(filename, "w", "utf_8_sig")
        self.file.write(u"WEBVTT\n")
        if regions is not None:
            if isinstance(regions, list):
                for region in regions:
                    self.file.write(region + '\n')
            else:
                self.file.write(regions + '\n')
        self.file.write(u"\n")

        self.pending = collections.deque()
        self.zero_time = time.time()
        
    def add_cue(self, text, id=None, region=None, duration=None):
        """Adds a new caption cue (speaker or system event)."""
        cue = Cue(self, text, id=id, region=region, duration=duration)
        self.pending.append(cue)
        if duration is not None:
            self.check_end()
        return(cue)
    
    def check_end(self):
        """Writes cues to disk once they have a stop time."""
        if not self.file:
            return
        while len(self.pending) > 0 and self.pending[0].stop is not None:
            cue = self.pending.popleft()
            self.file.write(cue.get_string())
        # EXPLICIT FLUSH LEARNING:
        # Prevents data loss if the bot process is terminated. 
        # Keeps the .vtt file 'live' during long recording sessions.
        self.file.flush()
    
    def close(self):
        """Finalizes the file and ensures all pending cues are ended."""
        if hasattr(self, 'file') and self.file:
            while len(self.pending) > 0:
                # Force-end any speaker who was still talkng when we stopped.
                self.pending[0].end(False)
                self.check_end()
            self.file.close()
            self.file = None

    def __del__(self):
        self.close()
        

class Cue:
    def __init__(self, parent, text, duration=None, id=None, region=None):
        self.parent = parent
        self.text = text
        self.id = id
        self.region = region
        self.start = time.time() - self.parent.zero_time
        if duration is None:
            self.stop = None
        else:
            self.stop = self.start + duration
        
    def end(self, check=True):
        self.stop = time.time() - self.parent.zero_time
        if check:
            self.parent.check_end()
            
    def set_region(self, region):
        self.region = region
            
    def get_string(self):
        if self.stop is None:
            return(u"")
        
        ret = u""
        if self.id:
            ret += self.id + u"\n"

        ret += self.convert_time(self.start) + u" --> " + self.convert_time(self.stop)
        if self.region:
            ret += u" region:{region} ".format(region=self.region)
        ret += u"\n"
        
        ret += self.text + u"\n\n"
        
        return(ret)
        
    def convert_time(self, seconds):
        """Converts raw seconds to HH:MM:SS.mmm format required by VTT."""
        # Handle small drift for precision
        if seconds < 0: seconds = 0
            
        micro = int((seconds - int(seconds)) * 1000)
        seconds = int(seconds)
        
        minutes = int(seconds/60)
        seconds -= minutes*60
        
        hours = int(minutes/60)
        minutes -= hours*60
        
        return("{hours:02}:{minutes:02}:{seconds:02}.{micro:03}".format(hours=hours, minutes=minutes, seconds=seconds, micro=micro))
