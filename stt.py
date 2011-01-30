#!/usr/bin/env python

# Copyright (c) 2011 Evren Esat Ozkan
#FIXME # Licencing:

#REQUIRES:
# gstreamer
# pygtk
# pocketsphinx


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




config = {
    'hmm': '/usr/share/pocketsphinx/model/hmm/wsj1',
    'lm': '1.lm',
    'dict': '1.dic'
    }

class Voximp(object):
    dial = None
    def __init__(self):
        self.init_gst()
        self.pipeline.set_state(gst.STATE_PLAYING)

    def init_gst(self):
#        self.pipeline = gst.parse_launch('alsasrc ! audioconvert ! audioresample '
        self.pipeline = gst.parse_launch('filesrc location=calendar.mp3 ! decodebin ! audioresample '
                                         + '! vader name=vad auto-threshold=true '
                                         + '! pocketsphinx name=asr ! fakesink ')
        asr = self.pipeline.get_by_name('asr')
        asr.connect('partial_result', self.asr_partial_result)
        asr.connect('result', self.asr_result)
        asr.set_property('lm', config['lm'])
        asr.set_property('dict', config['dict'])
        asr.set_property('configured', True)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.application_message)

        self.pipeline.set_state(gst.STATE_PAUSED)

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


versionNumber = '0.0.1'

if __name__ == '__main__':
    app = Voximp()
    gtk.main()
