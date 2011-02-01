#!/usr/bin/env python

# Copyright (c) 2011 Evren Esat Ozkan
#FIXME # Licencing:

#REQUIRES:
# gstreamer
# pygtk
# pocketsphinx
#from thread import start_new_thread

import pygtk
pygtk.require('2.0')
import gtk

import gobject
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst
from subprocess import Popen
import os
import sys
import getopt




CONF={
    'hmm': '/usr/share/pocketsphinx/model/hmm/wsj1',
}

LMD = {"EXIT":{},
"NEW":{},
"CALENDAR":{'EVENT':'','':'','':'','':'','':'','':'','':''},
"ENTRY":{},
"NOTE":{},
"TO DO":{},
"ALARM":{},
"RECORD":{},
"PHONE":{},
"COMPUTER":{},
"INTERNET":{},
"MUSIC":{},
"CAMERA":{},
"TWEET":{},
"SPEAK":{},
"TIME":{},
"INFO":{},
"QUIET":{},
}

#def say(why):
#    start_new_thread(espeak,(wht,))

def espeak(wht):
    os.system('espeak "%s"'%wht)

class STT(object):
    def __init__(self):
    #        print sys.argv
    #        pipeline,self.filename=self.convertToWav(sys.argv[1])
    #        pipeline.set_state(gst.STATE_PLAYING)
        self.gst_string='pulsesrc ! audioconvert ! audioresample ! vader name=vad auto-threshold=true \
        ! pocketsphinx name=asr ! appsink sync=false name=appsink'
        self.pipeline=None
        self.gst_start()



    def gst_stop(self):
        if self.pipeline.get_state()[1].value_name=='GST_STATE_PLAYING':
            self.pipeline.set_state(gst.STATE_NULL)

    def gst_start(self,phase='MAIN'):
        if self.pipeline: self.gst_stop()
        if phase!='MAIN': espeak('entering %s menu'%phase)
        self.pipeline=gst.parse_launch(self.gst_string)
        #        src = self.pipeline.get_by_name("input")
        #        print self.filename
        #        src.set_property("location", self.filename)
        asr = self.pipeline.get_by_name('asr')
        asr.connect('partial_result', self.asr_partial_result)
        asr.connect('result', self.asr_result)
        asr.set_property('lm', LMD[phase]+'.lm')
        asr.set_property('dict', LMD[phase]+'.dic')
        asr.set_property('configured', True)
#        self.asr=asr

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.application_message)
        self.pipeline.set_state(gst.STATE_PLAYING)

#        self.pipeline.set_state(gst.STATE_PAUSED)

#    def convertToWav(self, filename):
#        """Return (pipeline, destination_file_name) to convert filename to .wav
#        Caller must start the pipeline. If filename is already .wav, return
#        (None, filename).
#
#        gstreamer cannot always seek MP3 depending on the installed
#        plugins.  Probably using .wav for our many gnlfilesource also
#        reduces overhead in the final gnonlin step. (needs mp3parse from
#        -ugly to seek mp3)"""
#
#        destination = os.path.extsep.join((os.path.splitext(filename)[0], "wav"))
#        if os.path.exists(destination) and os.path.samefile(filename, destination):
#            return (None, destination)
#        else:
#            pipeline = gst.parse_launch("filesrc name=mp3src ! decodebin ! audioconvert ! wavenc ! filesink name=wavsink")
#            source = pipeline.get_by_name("mp3src")
#            sink = pipeline.get_by_name("wavsink")
#            source.set_property("location", filename)
#            sink.set_property("location", destination)
#            pipeline.set_state(gst.STATE_PLAYING)
#            return (pipeline, destination)

    def asr_partial_result(self, asr, text, uttid):
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def asr_result(self, asr, text, uttid):
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def application_message(self, bus, msg):
        msgtype = msg.structure.get_name()
        if msgtype == 'partial_result':
            self.partial_result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'result':
            self.final_result(msg.structure['hyp'], msg.structure['uttid'])
            #self.pipeline.set_state(gst.STATE_PAUSED)
            #self.button.set_active(False)

    def partial_result(self, hyp, uttid):
        print "partial: %s" % hyp

    def final_result(self, hyp, uttid):
        print "final: %s" % hyp
        if hyp=='CALENDAR':
            self.gst_start(hyp)
        elif hyp in ['MAIN','BACK']:
            self.gst_start('MAIN')
versionNumber = '0.0.1'

if __name__ == '__main__':
    app = STT()
    gtk.main()
