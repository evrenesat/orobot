#!/usr/bin/python
# Daniel Holth <dholth@fastmail.fm>
# April, 2009

import gobject
gobject.threads_init()

import sys
import os.path

import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade
import pygst
pygst.require('0.10')
import gst

class Main(object):
    def __init__(self):
        self.state = "START"
        self.keyword = "TWITTER"
        self.media = Media()
        self.setupWindow()
        self.window.show_all()

    def setupWindow(self):
        self.wTree = gtk.glade.XML("twitterkiller.glade", "mainwindow")
        self.window = self.wTree.get_widget("mainwindow")
        self.window.connect("destroy", self.destroy)
        self.textview = self.wTree.get_widget("textview")
        self.textbuf = self.textview.get_buffer()
        signals = { "on_file_activated": self.file_set,
                    "on_mainwindow_destroy": self.destroy }
        self.wTree.signal_autoconnect(signals)
        
    def file_set(self, widget):
        widget.set_sensitive(False)
        filenames = widget.get_filenames()
        c2w = self.media.convertToWav(filenames[0])
        pipeline, destination = c2w
        self.filename = filenames[0]
        self.intermediate = destination
        # if pipeline is None then we already have a .wav file
        if pipeline is None:
            if False:
                import utterances
                self.media.utterances = utterances.utterances
                self.redact()
            else:
                self.find_keywords(destination)
            return
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_wav_message, destination)
        self.pipeline = pipeline
        self.state = "TRANSCODE"
        gtk.gdk.threads_enter()
        pipeline.set_state(gst.STATE_PLAYING)
        gtk.gdk.threads_exit()

    def find_keywords(self, wavfile):
        """Find keywords from a .wav file."""
        print "Analyzing", wavfile
        pipeline = self.media.findKeywords(wavfile)
        self.state = "ANALYZE"
        bus = pipeline.get_bus()
        bus.connect("message", self.on_keywords_message)
        pipeline.set_state(gst.STATE_PLAYING)

    def on_wav_message(self, bus, message, data=None):
        t = message.type
        if t == gst.MESSAGE_APPLICATION:
            return
        elif t == gst.MESSAGE_ASYNC_DONE:
            print message
        elif t == gst.MESSAGE_EOS:
            print "Done transcoding to .wav"
            self.find_keywords(data)
        elif t == gst.MESSAGE_ERROR:
            print message

    def on_keywords_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_APPLICATION:
            msgtype = message.structure.get_name()
            if msgtype == "result":
                hyp = message.structure['hyp']
                uttid = message.structure['uttid']
                self.textbuf.begin_user_action()
                i = self.textbuf.get_start_iter()
                if self.keyword not in hyp:
                    hyp = hyp.lower()                 
                self.textbuf.insert(i, "%s %s\n" % (uttid, hyp, ))
                self.textbuf.end_user_action()
        elif t == gst.MESSAGE_EOS:
            print "Done analyzing text"
            self.redact()

    def redact(self):
        """Output edited podcast"""
        pipeline = self.media.redact(self.intermediate)
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_redact_message)
        pipeline.set_state(gst.STATE_PLAYING)
        self.redact_pipeline = pipeline

    def on_redact_message(self, bus, message, data=None):
        t = message.type
        if t == gst.MESSAGE_EOS:
            print "Done editing."
            self.redact_pipeline.set_state(gst.STATE_NULL)
            self.destroy(self.window)
        else:
            print "Redact Message", t

    def destroy(self, widget, data=None):
        print "Goodbye"
        gtk.main_quit()

class Media(object):
    def __init__(self):
        self.utterances = []
    
    def convertToWav(self, filename):
        """Return (pipeline, destination_file_name) to convert filename to .wav
        Caller must start the pipeline. If filename is already .wav, return
        (None, filename).

        gstreamer cannot always seek MP3 depending on the installed
        plugins.  Probably using .wav for our many gnlfilesource also
        reduces overhead in the final gnonlin step. (needs mp3parse from
        -ugly to seek mp3)"""

        destination = os.path.extsep.join((os.path.splitext(filename)[0], "wav"))
        if os.path.exists(destination) and os.path.samefile(filename, destination):
            return (None, destination)
        else:
            pipeline = gst.parse_launch("filesrc name=mp3src ! decodebin ! audioconvert ! wavenc ! filesink name=wavsink")
            source = pipeline.get_by_name("mp3src")
            sink = pipeline.get_by_name("wavsink")
            source.set_property("location", filename)
            sink.set_property("location", destination)
            return (pipeline, destination)

    def findKeywords(self, filename, keyword="TWITTER"):
        """Locate spoken occurrences of keyword (always uppercase)
        in filename."""
        self.utterances = []
        self.bufferutts = []
        self.last_vs = 0
        self.last_ve = 0
        self.last_alt_position = 0
        self.last_hyp = ""
        self.last_uttid = ""
        self.keyword = keyword
      
        self.pipeline = gst.parse_launch(
                'filesrc name=input ! decodebin ! audioconvert '
              + '! audioresample '
              + '! vader name=vad auto-threshold=true '
              + '! pocketsphinx name=asr ! appsink sync=false name=appsink')
       
        src = self.pipeline.get_by_name("input")
        src.set_property("location", filename)

        self.appsink = self.pipeline.get_by_name("appsink")
        self.appsink.set_property("emit-signals", True)
        self.appsink.connect("new-buffer", self.new_buffer)

        vad = self.pipeline.get_by_name("vad")
        vad.connect("vader-start", self.vader_start)
        vad.connect("vader-stop", self.vader_end)

        asr = self.pipeline.get_by_name('asr')
        asr.connect('result', self.asr_result)
        asr.props.dict = '3286/3286.dic'
        asr.props.lm = '3286/3286.lm'
        asr.props.latdir = '/tmp/lattice'
        asr.props.configured = True

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.application_message)
        bus.connect('message::new-buffer', self.application_message)
        self.pipeline.set_state(gst.STATE_PAUSED) 
        return self.pipeline

    def vader_start(self, vader, *args):
        print "VS", args
        self.last_vs = args[0]

    def vader_end(self, vader, *args):
        print "VE", args
        self.last_ve = args[0]

    def new_buffer(self, appsink):
        text = appsink.props.last_buffer.data
        timestamp = appsink.props.last_buffer.timestamp
        self.bufferutts.append((self.last_vs, text))
        print "NB", timestamp, text

    def asr_partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def asr_result(self, asr, text, uttid):
        """Forward result signals on the bus to the main thread."""
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def application_message(self, bus, msg):
        """Receive application messages from the bus."""
        msgtype = msg.structure.get_name()
        if msgtype == 'result':
            position = msg.src.query_position(gst.FORMAT_TIME)[0]
            # are we getting alt_postion from fakesink which is updated
            # after asr_result is sent?
            alt_position = self.pipeline.query_position(gst.FORMAT_TIME)[0]
            print position, alt_position
            # misses the last utterance but synthesizes a first one:
            self.final_result(self.last_hyp, self.last_uttid, alt_position)
            self.last_hyp = msg.structure['hyp']
            self.last_uttid = msg.structure['uttid']

    def final_result(self, hyp, uttid, position):
        """Insert the final result."""
        positive = True
        if not self.keyword in hyp.upper():
            positive = False
            hyp = hyp.lower()
        # position is the beginning of the utterance:
        self.utterances.append((positive, position, uttid, hyp))
        print self.utterances[-1]

    def redact(self, source_file):

        pipeline = gst.parse_launch("gnlcomposition name=compo audioconvert name=conv ! vorbisenc ! oggmux ! filesink name=redacted")

        product = pipeline.get_by_name("redacted")
        product.set_property("location", os.path.splitext(source_file)[0] + ".redacted.ogg")

        compo = pipeline.get_by_name("compo")

        self.audioconvert = pipeline.get_by_name("conv")

        if self.utterances:
            self.utterances.append(self.utterances[-1])
        # (omit, position, uttid, hyp)
        butts = [(False, 0, "", "")] + [(self.keyword in text, timestamp, "", text) for timestamp, text in self.bufferutts]
        import spanner
        elapsed = 0
        for span in spanner.span(butts):
            omit, start, end = span
            if omit:
                chunk_length = end - start
                if chunk_length == 0:
                    continue
                filesrc = gst.element_factory_make("gnlfilesource")
                filesrc.props.location = source_file
                filesrc.props.start = elapsed
                filesrc.props.duration = chunk_length
                filesrc.props.media_start = start
                filesrc.props.media_duration, chunk_length
                compo.add(filesrc)
                elapsed += chunk_length
   
        compo.props.start = 0
        compo.props.duration = elapsed 
        compo.props.media_start = 0
        compo.props.media_duration = elapsed

        # I think a gnonlin element with duration=0 should play to the end of
        # the source.
        #
        # chunk_length = span[2] - span[1]
        # filesrc = gst.element_factory_make("gnlfilesource")
        # filesrc.set_property("location", source_file)
        # filesrc.set_property("start", elapsed)
        # filesrc.set_property("duration", chunk_length)
        # filesrc.set_property("media-start", span[1])
        # filesrc.set_property("media-duration", chunk_length)
        # compo.add(filesrc)

        compo.connect("pad-added", self.on_pad)
        pipeline.set_state(gst.STATE_PAUSED)
        return pipeline

    def on_pad(self, comp, pad):
        print "ON PAD"
        convpad = self.audioconvert.get_compatible_pad(pad, pad.get_caps())
        pad.link(convpad)

if __name__ == "__main__":
    start = Main()
    gtk.gdk.threads_enter()
    gtk.main()
    gtk.gdk.threads_leave()
