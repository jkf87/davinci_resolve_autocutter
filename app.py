import os
import platform
import time
import json
import sys
import subprocess

import hashlib
import codecs

import logging
import logging.handlers as handlers

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, font
from tkinter import *

from threading import Thread

import torch
import whisper
from whisper import tokenizer as whisper_tokenizer

import librosa
import soundfile

from mots_resolve import MotsResolve

import re
from sentence_transformers import SentenceTransformer, util

from timecode import Timecode

import webbrowser

# define a global target dir so we remember where we chose to save stuff last time when asked
# but start with the user's home directory
user_home_dir = os.path.expanduser("~")
initial_target_dir = user_home_dir


# this is where we used to store the user data prior to version 0.16.14
# but we need to have a more universal approach, so we'll move this to
# the home directory of the user which is platform dependent (see below)
OLD_USER_DATA_PATH = 'userdata'

# this is where StoryToolkitAI stores the config files
# including project.json files and others
# on Mac, this is usually /Users/[username]/StoryToolkitAI
# on Windows, it's normally C:\Users\[username]\StoryToolkitAI
# on Linux, it's probably /home/[username]/StoryToolkitAI
USER_DATA_PATH = os.path.join(user_home_dir, 'StoryToolkitAI')

# create user data path if it doesn't exist
if not os.path.exists(USER_DATA_PATH):
    os.makedirs(USER_DATA_PATH)

# this is where we store the app configuration
APP_CONFIG_FILE_NAME = 'config.json'

# the location of the log file
APP_LOG_FILE = os.path.join(USER_DATA_PATH, 'app.log')

class Style():
    BOLD = '\33[1m'
    ITALIC = '\33[3m'
    UNDERLINE = '\33[4m'
    BLINK = '\33[5m'
    BLINK2 = '\33[6m'
    SELECTED = '\33[7m'

    GREY = '\33[20m'
    RED = '\33[91m'
    GREEN = '\33[92m'
    YELLOW = '\33[93m'
    BLUE = '\33[94m'
    VIOLET = '\33[95m'
    CYAN = '\33[96m'
    WHITE = '\33[97m'

    ENDC = '\033[0m'


# START LOGGER CONFIGURATION

# System call so that Windows enables console colors
os.system("")

# logger colors + style
class Logger_ConsoleFormatter(logging.Formatter):

    #format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    format = '%(levelname)s: %(message)s'

    FORMATS = {
        logging.DEBUG: Style.BLUE + format + Style.ENDC,
        logging.INFO: Style.GREY + format + Style.ENDC,
        logging.WARNING: Style.YELLOW + format + Style.ENDC,
        logging.ERROR: Style.RED + format + Style.ENDC,
        logging.CRITICAL: Style.RED + Style.BOLD + format + Style.ENDC
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# enable logger
logger = logging.getLogger('StAI')

# set the maximum log level
logger.setLevel(logging.DEBUG)

# create console handler and set level to info
logger_console_handler = logging.StreamHandler()

# if --debug was used in the command line arguments, use the DEBUG logging level for the console
# otherwise use INFO level
logger_console_handler.setLevel(logging.INFO if '--debug' not in sys.argv else logging.DEBUG)

# add console formatter to ch
logger_console_handler.setFormatter(Logger_ConsoleFormatter())

# add logger_console_handler to logger
logger.addHandler(logger_console_handler)

## Here we define our file formatter
# format the file logging
file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s: %(message)s (%(filename)s:%(lineno)d)")

# create file handler and set level to debug (we want to log everything in the file)
logger_file_handler = handlers.RotatingFileHandler(APP_LOG_FILE, maxBytes=1000000, backupCount=3)
logger_file_handler.setFormatter(file_formatter)
logger_file_handler.setLevel(logging.DEBUG)

# add file handler to logger
logger.addHandler(logger_file_handler)


# signal the start of the session in the log by adding some info about the machine
logger.debug('\n--------------\n'
             'Platform: {} {}\n Platform version: {}\n OS: {} \n running Python {}'
             '\n--------------'.format(
    platform.system(), platform.release(),
    platform.version(),
    ' '.join(map(str, platform.win32_ver()+platform.mac_ver())),
    '.'.join(map(str, sys.version_info))))




# this makes sure that the user has all the required packages installed
try:
    # get the path of app.py
    file_path = os.path.realpath(__file__)

    # check if all the requirements are met
    import pkg_resources
    pkg_resources.require(open(os.path.join(os.path.dirname(file_path), 'requirements.txt'), mode='r'))

    logger.debug('All package requirements met.')

except:

    # let the user know that the packages are wrong
    import traceback
    traceback_str = traceback.format_exc()

    logger.error(traceback_str)

    # get the relative path of the requirements file
    requirements_rel_path = os.path.relpath(os.path.join(os.path.dirname(__file__), 'requirements.txt'))

    requirements_warning_msg = ('\n'
          'Some of the packages required to run StoryToolkitAI are missing from your Python environment.\n'
          'Please run pip install -r {} '
          'to make sure that the right versions of the required packages are installed or StoryToolkitAI will not '
          'run properly.\n\n'
          'If you are running the standalone version of the app, please report this error to the developers together '
                                'with the log file found at: {}\n'
          .format(requirements_rel_path, APP_LOG_FILE))

    logger.error(requirements_warning_msg)

    # keep this message in the console for a bit
    time.sleep(5)


class toolkit_UI:
    '''
    This handles all the GUI operations mainly using tkinter
    '''

    class UImenus:

        def __init__(self, toolkit_UI_obj):

            # declare the main objects
            self.toolkit_UI_obj = toolkit_UI_obj
            self.toolkit_ops_obj = toolkit_UI_obj.toolkit_ops_obj
            self.stAI = toolkit_UI_obj.stAI

            self.app_items_obj = toolkit_UI_obj.app_items_obj

            # this is the main menubar (it's been declared in the main UI class to clear it before init)
            self.main_menubar = Menu(self.toolkit_UI_obj.root)

            # reset it for now so we don't see weird menus before it is populated
            self.toolkit_UI_obj.root.config(menu=self.main_menubar)

        def load_menubar(self):

            # get the current focus
            # print("focus is:", self.root.focus_get())


            filemenu = Menu(self.main_menubar, tearoff=0)
            filemenu.add_command(label="Configuration directory", command=self.open_userdata_dir)
            # filemenu.add_command(label="New", command=donothing)
            # filemenu.add_command(label="Open", command=donothing)
            # filemenu.add_command(label="Save", command=donothing)
            # filemenu.add_separator()
            # filemenu.add_command(label="Exit", command=lambda: sys.exit())
            self.main_menubar.add_cascade(label="File", menu=filemenu)

            helpmenu = Menu(self.main_menubar, tearoff=0)

            # if this is not on MacOS, add the about button in the menu
            if platform.system() != 'Darwin':

                #helpmenu.add_separator()
                filemenu.add_command(label="Preferences...", command=self.app_items_obj.open_preferences_window)

                helpmenu.add_command(label="About", command=self.about_dialog)
                helpmenu.add_separator()

            # otherwise show stuff in MacOS specific menu places
            else:

                # change the link in the about dialogue
                self.toolkit_UI_obj.root.createcommand('tkAboutDialog', self.app_items_obj.open_about_window)
                self.toolkit_UI_obj.root.createcommand('tk::mac::ShowPreferences', self.app_items_obj.open_preferences_window)
                #self.toolkit_UI_obj.root.createcommand('tkPreferencesDialog', self.app_items_obj.open_about_window)

                # see https://tkdocs.com/tutorial/menus.html#platformmenus
                #menubar = Menu(self.toolkit_UI_obj.root)
                #appmenu = Menu(menubar, name='apple')
                #menubar.add_cascade(menu=appmenu)
                #appmenu.add_command(label='About My Application')
                #appmenu.add_separator()

                system_menu = tk.Menu(self.main_menubar, name='apple')
                #system_menu.add_command(command=lambda: self.w.call('tk::mac::standardAboutPanel'))
                #system_menu.add_command(command=lambda: self.updater.checkForUpdates())

                #system_menu.entryconfigure(0, label="About")
                system_menu.entryconfigure(1, label="Check for Updates...")
                #self.main_menubar.add_cascade(menu=system_menu)

                helpmenu.add_command(label="Go to project page", command=self.open_project_page)

            helpmenu.add_command(label="Features info", command=self.open_features_info)
            helpmenu.add_command(label="Report an issue", command=self.open_issue)
            helpmenu.add_command(label="Made by mots", command=self.open_mots)
            self.main_menubar.add_cascade(label="Help", menu=helpmenu)

            self.toolkit_UI_obj.root.config(menu=self.main_menubar)

        def donothing(self):
            return

        def open_userdata_dir(self):
            # if we're on a Mac, open the user data dir in Finder
            if platform.system() == 'Darwin':
                subprocess.call(['open', '-R', self.stAI.user_data_path])

            # if we're on Windows, open the user data dir in Explorer
            elif platform.system() == 'Windows':
                subprocess.call(['explorer', self.stAI.user_data_path])

            # if we're on Linux, open the user data dir in the file manager
            elif platform.system() == 'Linux':
                subprocess.call(['xdg-open', self.stAI.user_data_path])


        def open_project_page(self):
            webbrowser.open_new("http://storytoolkit.ai")
            return

        def open_features_info(self):
            webbrowser.open_new("https://github.com/octimot/StoryToolkitAI#features-info")
            return

        def open_issue(self):
            webbrowser.open_new("https://github.com/octimot/StoryToolkitAI/issues")
            return

        def about_dialog(self):
            self.app_items_obj.open_about_window()

        def open_mots(self):
            webbrowser.open_new("https://mots.us")
            return

    class TranscriptEdit:
        '''
        All the functions available in the transcript window should be part of this class
        '''

        def __init__(self, toolkit_UI_obj=None):

            # keep a reference to the toolkit_UI object here
            self.toolkit_UI_obj = toolkit_UI_obj

            # keep a reference to the StoryToolkitAI object here
            self.stAI = toolkit_UI_obj.stAI

            # keep a reference to the toolkit_ops_obj object here
            self.toolkit_ops_obj = toolkit_UI_obj.toolkit_ops_obj

            self.root = toolkit_UI_obj.root

            # search results indexes stored here
            # we're making it a dict so that we can store result indexes for each window individually
            self.search_result_indexes = {}

            # when searching for text, you may want the user to cycle through the results, so this keep track
            # keeps track on which search result is the user currently on (in each transcript window)
            self.search_result_pos = {}

            # to keep track of what is being searched on each window
            self.search_strings = {}

            # to stop certain events while typing,
            # we keep track if we have typing going on in any of the windows
            self.typing = {}

            # to know in which windows is the user editing transcripts
            self.transcript_editing = {}

            # to know which window works with which transcription_file_path
            self.transcription_file_paths = {}

            # to store the transcript segments of each window,
            # including their start + end times and who knows what else?!
            # here, they are simply ordered in their line orders, where the segment_index is line_no-1:
            #               self.transcript_segments[window_id][segment_index] = segment_dict
            # the segment_index is not the segment_id mentioned below!
            self.transcript_segments = {}

            # we need this to have a reference between
            # the line number of a segment within the transcript and the id of that segment in the transcription file
            # so the dict should look like: self.transcript_segments_ids[window_id][segment_line_no] = segment_id
            # the segment_id is not the segment_index mentioned above!
            self.transcript_segments_ids = {}

            # save other data from the transcription file for each window here
            self.transcription_data = {}

            # save transcription groups of each transcription window here
            self.transcript_groups = {}

            # save the selected groups of each transcription window here
            # (multiple selections allowed)
            self.selected_groups = {}

            # all the selected transcript segments of each window
            # the selected segments dict will use the text element line number as an index, for eg:
            # self.selected_segments[window_id][line] = transcript_segment
            self.selected_segments = {}

            # to keep track of the modified transcripts
            self.transcript_modified = {}

            # the active_segment stores the text line number of each window to keep track where
            # the cursor is currently on the transcript
            self.active_segment = {}

            # when changed, active segments line numbers move to last_active_segment
            self.last_active_segment = {}

            # the current timecode of each window
            self.current_window_tc = {}

            # this keeps track of which transcription window is in sync with the resolve playhead
            self.sync_with_playhead = {}


        def link_to_timeline_button(self, button=None, transcription_file_path=None,
                                    link=None, timeline_name=None):

            if transcription_file_path is None:
                return None

            link_result = self.toolkit_ops_obj.link_transcription_to_timeline(
                transcription_file_path=transcription_file_path,
                link=link, timeline_name=timeline_name)

            # make the UI link (or unlink) the transcript to the timeline
            if link_result and link_result is not None:

                # get the window id of the transcription file
                # this is stored in the self.transcription_file_paths dict, where the key is the window id
                # and the value is the transcription file path
                window_id = None
                for key, value in self.transcription_file_paths.items():
                    if value == transcription_file_path:
                        window_id = key
                        break

                # check if the data in the transcription file is valid
                if window_id is not None and window_id in self.transcript_segments:
                    transcription_data = self.transcription_data[window_id]

                    # if the fps in the transcription data is different than the current timeline fps
                    # if current_timeline_fps is not None \
                    #        and (('timeline_fps' in transcription_data  \
                    #            and transcription_data['timeline_fps'] != current_timeline_fps) \
                    #            or 'timeline_fps' not in transcription_data):

                    #        # ask the user wether to update the fps in the transcription file
                    #        update_fps = messagebox.askyesno(
                    #            title="Update Transcription framerate",
                    #            message="The framerate in the transcription file "
                    #                    "is different than the current timeline framerate. \n\n"
                    #                    "Do you want to update transcription file to match "
                    #                    "the current timeline framerate?")

                    #        if update_fps:
                    #            transcription_data['timeline_fps'] = current_timeline_fps

                    #            print(current_timeline_fps)
                    #            #self.toolkit_ops_obj.save_transcription_file(transcription_file_path, transcription_data)



                # if the reply is true, it means that the transcript is linked
                # therefore the button needs to read the opposite action
                button.config(text="Unlink from Timeline")
                return True
            elif not link_result and link_result is not None:
                # and the opposite if transcript is not linked
                button.config(text="Link to Timeline")
                return False

            # if the link result is None
            # don't change anything to the button
            else:
                return

        def sync_with_playhead_button(self, button=None, window_id=None, sync=None):

            if button is None or window_id is None:
                return False

            self.sync_with_playhead_update(window_id, sync)

            return sync

        def sync_with_playhead_update(self, window_id, sync=None):

            if window_id not in self.sync_with_playhead:
                self.sync_with_playhead[window_id] = False

            # if no sync variable was passed, toggle the current sync state
            if sync is None:
                sync = not self.sync_with_playhead[window_id]

            self.sync_with_playhead[window_id] = sync

            return sync

        def set_typing_in_window(self, event=None, window_id=None, typing=None):

            if window_id is None:
                return None

            # if there isn't a typing tracker for this window, create one
            if window_id not in self.typing:
                self.typing[window_id] = False

            # if typing was passed, assign it
            if typing is not None:
                self.typing[window_id] = typing

            # return the status of the typing
            return self.typing[window_id]

        def get_typing_in_window(self, window_id):

            # if there isn't a typing tracker for this window, create one
            if window_id not in self.typing:
                self.typing[window_id] = False

            return self.typing[window_id]

        def set_transcript_editing(self, event=None, window_id=None, editing=None):

            if window_id is None:
                return None

            # if there isn't a typing tracker for this window, create one
            if window_id not in self.transcript_editing:
                self.transcript_editing[window_id] = False

            # if typing was passed, assign it
            if editing is not None:
                self.transcript_editing[window_id] = editing

            # return the status of the typing
            return self.transcript_editing[window_id]

        def get_transcript_editing_in_window(self, window_id):

            # if there isn't a typing tracker for this window, create one
            if window_id not in self.transcript_editing:
                self.transcript_editing[window_id] = False

            return self.transcript_editing[window_id]

        def search_text(self, search_str=None, text_element=None, window_id=None):
            '''
            Used to search for text inside tkinter text objects
            This also tags the search results
            :return:
            '''

            if search_str is None or text_element is None or window_id is None:
                return False

            # remove tag 'found' from index 1 to END
            text_element.tag_remove('found', '1.0', END)

            # remove tag 'current_result_tag' from index 1 to END
            text_element.tag_remove('current_result_tag', '1.0', END)

            # reset the search result indexes and the result position
            self.search_result_indexes[window_id] = []
            self.search_result_pos[window_id] = 0

            # get the search string as the user is typing
            search_str = self.search_strings[window_id] = search_str.get()

            if search_str:
                idx = '1.0'

                self.search_strings[window_id] = search_str

                while 1:
                    # searches for desired string from index 1
                    idx = text_element.search(search_str, idx, nocase=True, stopindex=END)

                    # stop the loop when we run out of results (indexes)
                    if not idx:
                        break

                    # store each index
                    self.search_result_indexes[window_id].append(idx)

                    # last index sum of current index and
                    # length of text
                    lastidx = '%s+%dc' % (idx, len(search_str))

                    # add the found tag at idx
                    text_element.tag_add('found', idx, lastidx)
                    idx = lastidx

                #  take the viewer to the first occurrence
                if self.search_result_indexes[window_id] and len(self.search_result_indexes[window_id]) > 0 \
                        and self.search_result_indexes[window_id][0] != '':
                    text_element.see(self.search_result_indexes[window_id][0])

                    # and visually tag the results
                    self.tag_results(text_element, self.search_result_indexes[window_id][0], window_id)

                # mark located string with red
                text_element.tag_config('found', foreground=self.toolkit_UI_obj.resolve_theme_colors['red'])

        def tag_results(self, text_element, text_index, window_id):
            '''
            Another handy function that tags the search results directly on the transcript inside the transcript window
            This is also used to show on which of the search results is the user right now according to search_result_pos
            :param text_element:
            :param text_index:
            :param window_id:
            :return:
            '''
            if text_element is None:
                return False

            # remove previous position tags
            text_element.tag_delete('current_result_tag')

            if not text_index or text_index == '' or text_index is None or window_id is None:
                return False

            # add tag to show the user on which result position we are now
            # the tag starts at the text_index and ends according to the length of the search string
            text_element.tag_add('current_result_tag', text_index, text_index + '+'
                                 + str(len(self.search_strings[window_id])) + 'c')

            # the result tag has a white background and a red foreground
            text_element.tag_config('current_result_tag', background=self.toolkit_UI_obj.resolve_theme_colors['white'],
                                    foreground=self.toolkit_UI_obj.resolve_theme_colors['red'])

        def cycle_through_results(self, text_element=None, window_id=None):

            if text_element is not None or window_id is not None \
                    or self.search_result_indexes[window_id] or self.search_result_indexes[window_id][0] != '':

                # get the current search result position
                current_pos = self.search_result_pos[window_id]

                # as long as we're not going over the number of results
                if current_pos < len(self.search_result_indexes[window_id]) - 1:

                    # add 1 to the current result position
                    current_pos = self.search_result_pos[window_id] = current_pos + 1

                    # this is the index of the current result position
                    text_index = self.search_result_indexes[window_id][current_pos]

                    # go to the next search result
                    text_element.see(text_index)

                # otherwise go back to start
                else:
                    current_pos = self.search_result_pos[window_id] = 0

                    # this is the index of the current result position
                    text_index = self.search_result_indexes[window_id][current_pos]

                    # go to the next search result
                    text_element.see(self.search_result_indexes[window_id][current_pos])

                # visually tag the results
                self.tag_results(text_element, text_index, window_id)

        def get_line_char_from_click(self, event, text_element=None):

            index = text_element.index("@%s,%s" % (event.x, event.y))
            line, char = index.split(".")

            return line, char

        def transcription_window_keypress(self, event=None, **attributes):
            '''
            What to do with the keypresses on transcription windows?
            :param attributes:
            :return:
            '''

            if self.get_typing_in_window(attributes['window_id']):
                return

            # for now, simply pass to select text lines if it matches one of these keys
            if event.keysym in ['Up', 'Down', 'v', 'V', 'A', 'i', 'o', 'm', 'M', 'C', 'q', 's', 'L',
                                'g', 'G', 'BackSpace', 't', 'a',
                                'apostrophe', 'semicolon', 'colon', 'quotedbl']:
                self.segment_actions(event, **attributes)

        def transcription_window_mouse(self, event=None, **attributes):
            '''
            What to do with mouse presses on transcription windows?
            :param event:
            :param attributes:
            :return:
            '''

            #print(event.state)
            # for now simply pass the event to the segment actions
            self.segment_actions(event, mouse=True, **attributes)

        def segment_actions(self, event=None, text_element=None, window_id=None,
                            special_key=None, mouse=False, status_label=None):
            '''
            Handles the key and mouse presses in relation with transcript segments (lines)
            :return:
            '''

            if text_element is None or window_id is None:
                return False

            #if special_key is not None:
            #     print(special_key)

            # HERE ARE SOME USEFUL SHORTCUTS FOR THE TRANSCRIPTION WINDOW:
            # see the shortcuts in the README file

             # initialize the active segment number
            self.active_segment[window_id] = self.get_active_segment(window_id, 1)

            # PRE- CURSOR MOVE EVENTS:
            # below we have the events that should happen prior to moving the cursor

            # UP key events
            if event.keysym == 'Up':

                # move cursor (active segment) on the previous segment on the transcript
                self.set_active_segment(window_id, text_element, line_calc=-1)

            # DOWN key events
            elif event.keysym == 'Down':

                # move cursor (active segment) on the next segment on the transcript
                self.set_active_segment(window_id, text_element, line_calc=1)

            # APOSTROPHE key events
            elif event.keysym == 'apostrophe':
                # go_to_time end time of the last selected segment
                self.go_to_selected_time(window_id=window_id, position='end')

            # SEMICOLON key events
            elif event.keysym == 'semicolon':
                # go_to_time start time of the first selected segment
                self.go_to_selected_time(window_id=window_id, position='start')


            # on mouse presses
            if mouse:

                # first get the line and char numbers based text under the click event
                index = text_element.index("@%s,%s" % (event.x, event.y))
                line_str, char_str = index.split(".")

                # make the clicked segment into active segment
                self.set_active_segment(window_id, text_element, int(line_str))

                # and move playhead to that time
                self.go_to_selected_time(window_id, 'start', ignore_selection=True)

                # if cmd was also pressed
                if special_key == 'cmd':

                    # add clicked segment to selection
                    self.segment_to_selection(window_id, text_element, int(line_str))

            # what is the currently selected line number again?
            line = self.get_active_segment(window_id)

            # POST- CURSOR MOVE EVENTS
            # these are the events that might require the new line and segment numbers

            # v key events
            if event.keysym == 'v':

                # add/remove active segment to selection
                # if it's not in the selection
                self.segment_to_selection(window_id, text_element, line)

            # Shift+V key events
            if event.keysym == 'V':
                # clear selection
                self.clear_selection(window_id, text_element)

            # CMD+A key events
            if event.keysym == 'a' and special_key == 'cmd':

                # get the number of segments in the transcript
                num_segments = len(self.transcript_segments[window_id])

                # create a list containing all the segment numbers
                segment_list = list(range(1, num_segments+1))

                # select all segments by passing all the line numbers
                self.segment_to_selection(window_id, text_element, segment_list)

                return 'break'

            # Shift+A key events
            if event.keysym == 'A':

                # select all segments between the active_segment and the last_active_segment

                # first, get the lowest index between the active and the last active segments
                if self.active_segment[window_id] >= self.last_active_segment[window_id]:
                    start_segment = self.last_active_segment[window_id]
                    max_segment = self.active_segment[window_id]
                else:
                    max_segment = self.last_active_segment[window_id]
                    start_segment = self.active_segment[window_id]

                # first clear the entire selection
                self.clear_selection(window_id, text_element)

                # then take each segment, starting with the lowest and select them
                n = start_segment
                while n <= max_segment:
                    self.segment_to_selection(window_id, text_element, n)
                    n = n+1


            # Shift+C key event (copy segments with timecodes to clipboard)
            if event.keysym == 'C':

                # is control also pressed?
                if special_key == 'cmd':
                    # copy segment with timecodes
                    # self.copy_segment_timecodes(window_id, text_element, line)
                    text, _, _, _ \
                        = self.get_segments_or_selection(window_id, split_by='line',
                                                         add_to_clipboard=True, add_time_column=True)

                else:
                    # copy the text content to clipboard
                    self.get_segments_or_selection(window_id, add_to_clipboard=True, split_by='index')


            # m key event (add duration markers)
            if event.keysym == 'm' or event.keysym == 'M':

                #print('Special Key:', special_key)

                # add segment based markers

                global resolve
                global current_timeline

                # this only works if resolve is connected
                if resolve and 'name' in current_timeline:

                    # first get the selected (or active) text from the transcript
                    # this should return a list of all the text chunks, the full text
                    #   and the start and end times of the entire text
                    text, full_text, start_sec, end_sec = \
                        self.get_segments_or_selection(window_id, add_to_clipboard=False,
                                                       split_by='index', timecodes=True)

                    # now, take care of the marker name
                    marker_name = False

                    # if Shift+M was pressed, prompt the user for the marker name
                    if event.keysym == 'M':

                        marker_name = simpledialog.askstring(
                                        parent=self.toolkit_UI_obj.windows[window_id],
                                        title="Markers Name",
                                        prompt="Marker Name:")

                        # if the user pressed cancel, return
                        if not marker_name:
                            return False

                    # if we still don't have a marker name
                    if not marker_name or marker_name == '':
                        # use a generic name which the user will most likely change afterwards
                        marker_name = 'Transcript Marker'

                    # calculate the start timecode of the timeline (simply use second 0 for the conversion)
                    # we will use this to calculate the text_chunk durations
                    timeline_start_tc = self.toolkit_ops_obj.calculate_sec_to_resolve_timecode(0)

                    # now take all the text chunks
                    for text_chunk in text:

                        # calculate the end timecodes for each text chunk
                        end_tc = self.toolkit_ops_obj.calculate_sec_to_resolve_timecode(text_chunk['end'])

                        # get the start_tc from the text_chunk but place it back into a Timecode object
                        # using the timeline framerate
                        start_tc = Timecode(timeline_start_tc.framerate, text_chunk['start_tc'])

                        # and subtract the end timecode from the start_tc of the text_chunk
                        # to get the marker duration (still timecode object for now)
                        # the start_tc of the text_chunk should be already in the text list
                        marker_duration_tc = end_tc-start_tc

                        # in Resolve, marker indexes are the number of frames from the beginning of the timeline
                        # so in order to get the marker index, we need to subtract the timeline_start_tc from start_tc

                        # but only if the start_tc is larger than the timeline_start_tc so we don't get a
                        # Timecode class error
                        if start_tc > timeline_start_tc:
                            start_tc_zero = start_tc-timeline_start_tc
                            marker_index = start_tc_zero.frames

                        # if not consider that we are at frame 1
                        else:
                            marker_index = 1

                        # check if there's another marker at the exact same index
                        index_blocked = True
                        while index_blocked:

                            if 'markers' in current_timeline and marker_index in current_timeline['markers']:

                                # give up if the duration is under a frame:
                                if marker_duration_tc.frames <= 1:
                                    self.notify_via_messagebox(title='Cannot add marker',
                                                               message='Not enough space to add marker on timeline.',
                                                               type='warning'
                                                               )
                                    return False

                                # notify the user that the index is blocked by another marker
                                add_frame = messagebox.askyesno(title='Cannot add marker',
                                                    message="Another marker exists at {}.\n\n"
                                                            "Do you want to place the new marker one frame later?"
                                                                .format(start_tc))

                                # if the user wants to move this marker one frame to the right, be it
                                if add_frame:
                                    start_tc.frames = start_tc.frames+1
                                    marker_index = marker_index+1

                                    # but this means that the duration should be one frame shorter
                                    marker_duration_tc.frames = marker_duration_tc.frames-1
                                else:
                                    return False

                            else:
                                index_blocked = False

                        marker_data = {}
                        marker_data[marker_index] = {}

                        # the name of the marker
                        marker_data[marker_index]['name'] = marker_name

                        # choose the marker color from Resolve
                        marker_data[marker_index]['color'] = self.stAI.get_app_setting('default_marker_color',
                                                                                         default_if_none='Blue')

                        # add the text to the marker data
                        marker_data[marker_index]['note'] = text_chunk['text']

                        # the marker duration needs to be in frames
                        marker_data[marker_index]['duration'] = marker_duration_tc.frames

                        # no need for custom data
                        marker_data[marker_index]['customData'] = ''

                        # pass the marker add request to resolve
                        self.toolkit_ops_obj.resolve_api.add_timeline_markers(current_timeline['name'],
                                                                              marker_data,
                                                                              False)

            # q key event (close transcription window)
            if event.keysym == 'q':
                # close transcription window
                self.toolkit_UI_obj.destroy_transcription_window(window_id)

            # Shift+L key event (link current timeline to this transcription)
            if event.keysym == 'L':
                # link transcription to file
                self.toolkit_ops_obj.link_transcription_to_timeline(self.transcription_file_paths[window_id])

            # s key event (sync transcript cursor with playhead)
            if event.keysym == 's':
                self.sync_with_playhead_update(window_id=window_id)

            # CMD+G key event (group selected - adds new group or updates segments of existing group)
            if event.keysym == 'g' and special_key == 'cmd':

                # if a group is selected, just update it
                if window_id in self.selected_groups and len(self.selected_groups[window_id])==1:

                    # use the selected group id
                    group_id = self.selected_groups[window_id][0]

                    # update group
                    self.toolkit_UI_obj.on_group_update_press(t_window_id=window_id,
                                                               t_group_window_id=window_id+'_transcript_groups',
                                                               group_id=group_id)


                # otherwise create a new group
                else:
                    if self.group_selected(window_id=window_id):
                        logger.info('Group added')

            # SHIFT+G opens group window
            if event.keysym == 'G':
                 #self.group_selected(window_id=window_id)
                self.toolkit_UI_obj.open_transcript_groups_window(transcription_window_id=window_id)

            # colon key event (align current line start to playhead)
            if event.keysym == 'colon':
                self.align_line_to_playhead(window_id=window_id, line_index=line, position='start')

            # double quote key event (align current line end to playhead)
            if event.keysym == 'quotedbl':
                self.align_line_to_playhead(window_id=window_id, line_index=line, position='end')

            if event.keysym == 't':

                # first get the selected (or active) text from the transcript
                text, full_text, start_sec, end_sec = \
                    self.get_segments_or_selection(window_id, add_to_clipboard=False,
                                                   split_by='index', timecodes=True, allow_active_segment=False)

                # now turn the text blocks into time intervals
                time_intervals = ''
                retranscribe = False
                ask_message = "Do you want to re-transcribe the entire transcript?"
                if text is not None and text and len(text) > 0:

                    # get all the time intervals based on the text blocks
                    for text_block in text:
                        time_intervals = time_intervals + "{}-{}\n".format(text_block['start'], text_block['end'])

                    ask_message = "Do you want to re-transcribe the selected segments?"

                # ask the user if they want to re-transcribe
                retranscribe = messagebox.askyesno(title='Re-transcribe',
                                               message=ask_message)

                # if the user cancels re-transcribe or no segments were selected, cancel
                if not retranscribe:
                    return False

                # close the transcription window
                # @todo (temporary solution until we work on a better way to update transcription windows
                self.toolkit_UI_obj.destroy_window_(self.toolkit_UI_obj.windows, window_id=window_id)

                # remove the selection references too
                self.clear_selection(window_id=window_id)

                # and start the transcription config process
                self.toolkit_ops_obj\
                    .prepare_transcription_file(toolkit_UI_obj=self.toolkit_UI_obj,
                                                task='transcribe',
                                                retranscribe=self.transcription_file_paths[window_id],
                                                time_intervals=time_intervals)

            # BackSpace key event (delete selected)
            if event.keysym == 'BackSpace':
                self.delete_line(window_id=window_id, text_element=text_element,
                                 line_no=line, status_label=status_label)

        def delete_line(self, window_id, text_element, line_no, status_label):
            '''
            Deletes a specific line of text from the transcript and saves the file
            :param window_id:
            :param text_element:
            :param line_index:
            :return:
            '''

            # WORK IN PROGRESS

            if line_no > len(self.transcript_segments[window_id]):
                return False

            # ask the user if they are sure
            if messagebox.askyesno(title='Delete line',
                                     message='Are you sure you want to delete this line?'):

                # get the line
                tkinter_line_index = '{}.0'.format(line_no), '{}.0'.format(int(line_no)+1).split(' ')

                # enable editing on the text element
                text_element.config(state=NORMAL)

                # delete the line - doesn't work!
                # remove the line from the text widget
                text_element.delete(tkinter_line_index[0], tkinter_line_index[1])

                # disable editing on the text element
                text_element.config(state=DISABLED)

                # calculate the segment index
                segment_index = int(line_no)-1

                # remove the line from the text list
                self.transcript_segments[window_id].pop(segment_index)

                # mark the transcript as modified
                self.set_transcript_modified(window_id=window_id, modified=True)

                # save the transcript
                save_status = self.save_transcript(window_id=window_id, text=False, skip_verification=True)

                # let the user know what happened via the status label
                self.update_status_label_after_save(status_label=status_label, save_status=save_status)

                return True

            return False

        def align_line_to_playhead(self, window_id, line_index, position=None):
            """
            Aligns a transcript line to the playhead (only works if Resolve is connected)
            by setting the start time or end time of the line to the playhead position.

            :param window_id: the window id
            :param line_index: the segment index
            :param position: the position to align to (the start or the end of the segment)
            :return: None
            """

            if position is None:
                logger.error('No position specified for align_line_to_playhead()')
                return False

            if resolve is None or position is None:
                logger.error('Resolve is not connected.')
                return False

            move_playhead = messagebox.askokcancel(title='Move playhead',
                                   message='Move the Resolve playhead exactly '
                                            'where you want to align the {} of this segment, '
                                            'then press OK to align.'.format(position)
                                   )

            if not move_playhead:
                logger.debug('User cancelled segment alignment.')
                return False

            # convert the current_tc to seconds
            current_tc_sec = self.toolkit_ops_obj.calculate_resolve_timecode_to_sec()

            # check if we actually have a timecode
            if current_tc_sec is None:
                self.toolkit_UI_obj.notify_via_messagebox(title='Cannot align line to playhead',
                                                message='Cannot align to playhead: '
                                                        'Resolve playhead timecode not available.',
                                                type='error')
                return False

            # convert line_index to segment_index (not segment_id!)
            segment_index = line_index-1

            # stop if the segment index is not in the transcript segments
            if segment_index > len(self.transcript_segments[window_id])-1:
                logger.error('Cannot align line to playhead: no segment index found.')
                return False

            # get the segment data
            segment_data = self.transcript_segments[window_id][segment_index]

            # replace the start or end time with the current_tc_sec
            if position == 'start':
                segment_data['start'] = current_tc_sec
            elif position == 'end':
                segment_data['end'] = current_tc_sec

            # return False if no position was specified
            # (will probably never reach this since we're checking it above)
            else:
                logger.error('No position specified for align_line_to_playhead()')
                return False

            # check if the start time is after the end time
            # and throw an error and cancel if it is
            if segment_data['start'] >= segment_data['end']:
                self.toolkit_UI_obj.notify_via_messagebox(title='Cannot align line to playhead',
                                                message='Cannot align to playhead: '
                                                        'Start time is after end time.',
                                                type='error')
                return False

            # check if the start time is before the previous segment end time
            # and throw an error and cancel if it is
            if segment_index > 0:
                if segment_data['start'] < self.transcript_segments[window_id][segment_index-1]['end']:
                    self.toolkit_UI_obj.notify_via_messagebox(title='Cannot align line to playhead',
                                                    message='Cannot align to playhead: '
                                                            'Start time is before previous segment\'s end time.',
                                                    type='error')
                    return False

            # check if the end time is after the next segment start time
            # and throw an error and cancel if it is
            if segment_index < len(self.transcript_segments[window_id])-1:
                if segment_data['end'] > self.transcript_segments[window_id][segment_index+1]['start']:
                    self.toolkit_UI_obj.notify_via_messagebox(title='Cannot align line to playhead',
                                                    message='Cannot align to playhead: '
                                                            'End time is after next segment\'s start time.',
                                                    type='error')
                    return False

            # update the transcript segments
            self.transcript_segments[window_id][segment_index] = segment_data

            # mark the transcript as modified
            self.set_transcript_modified(window_id=window_id, modified=True)

            # save the transcript
            self.save_transcript(window_id=window_id, text=False, skip_verification=True)

            return True

        def get_segments_or_selection(self, window_id, add_to_clipboard=False, split_by=None, timecodes=True,
                                      allow_active_segment=True, add_time_column=False):
            '''
            Used to extract the text from either the active segment or from the selection
            Will return the text, and the start and end times

            If the split_by parameter is 'index', the text will be split into blocks of text that
            are next to each other in the main transcript_segments[window_id] list.

            If the split_by parameter is 'time', the text will be split into blocks of text that
            have no time gaps between them.

            If timecodes is true, the return will also include the text blocks' start and end timecodes
            (if Resolve is available)

            If add_to_clipboard is True, the function copies the full_text to the clipboard

            :param window_id:
            :param add_to_clipboard:
            :param split_by: None, 'index' or 'time'
            :param timecodes
            :return:
            '''

            # the full text string
            full_text = ''

            # the return text list
            text = [{}]

            # the start and end times of the entire selection
            start_sec = None
            end_sec = None

            # get the start timecode from Resolve
            if timecodes:
                timeline_start_tc = self.toolkit_ops_obj.calculate_sec_to_resolve_timecode(0)

                if type(timeline_start_tc) is Timecode:
                    timeline_fps = timeline_start_tc.framerate

                # try to get the start timecode, fps and timeline name from the transcription data dict
                if not timeline_start_tc and window_id in self.transcription_data:

                    logger.debug('Timeline timecode not available, trying transcription data instead')

                    timeline_start_tc = self.transcription_data[window_id]['timeline_start_tc'] \
                                        if 'timeline_start_tc' in self.transcription_data[window_id] else None

                    timeline_fps = self.transcription_data[window_id]['timeline_fps'] \
                                        if 'timeline_fps' in self.transcription_data[window_id] else None

                    # convert the timeline_start_tc to a Timecode object but only if the fps is also known
                    if timeline_start_tc is not None and timeline_fps is not None:
                        timeline_start_tc = Timecode(timeline_fps, timeline_start_tc)
                    else:
                        timeline_start_tc = None
                        logger.debug('Timeline timecode not available in transcription data either')

                # if no timecode was received it probably means Resolve is disconnected so disable timecodes
                if not timeline_start_tc or timeline_start_tc is None:
                    timecodes = False

            # if we have some selected segments, use their start and end times
            if window_id in self.selected_segments and len(self.selected_segments[window_id]) > 0:

                start_segment = None
                end_segment = None
                start_sec = 0
                end_sec = 0

                from operator import itemgetter

                # first sort the selected segments by start time
                # (but we are losing the line numbers which are normally in the dict keys!)
                sorted_selected_segments = sorted(self.selected_segments[window_id].values(), key=itemgetter('start'))

                # use this later to see where the selected_segment is in the original transcript
                transcript_segment_index = 0
                prev_transcript_segment_index = None
                prev_segment_end_time = None

                # keep track of text chunks in case the split by parameter was passed
                current_chunk_num = 0

                # add each text
                for selected_segment in sorted_selected_segments:

                    # see where this selected_segment is in the original transcript
                    transcript_segment_index = self.transcript_segments[window_id].index(selected_segment)

                    # split each blocks of text that are next to each other in the main transcript_segments[window_id] list
                    if split_by == 'index':

                        # assign a value if this is the first transcript_segment_index of this iteration
                        if prev_transcript_segment_index is None:
                            prev_transcript_segment_index = transcript_segment_index

                        # if the segment is not right after the previous segment that we processed
                        # it means that there are other segments between them which haven't been selected
                        elif prev_transcript_segment_index+1 != transcript_segment_index:
                            current_chunk_num = current_chunk_num+1
                            text.append({})

                            # show that there might be missing text from the transcription
                            full_text = full_text+'\n[...]\n'

                    # split into blocks of text that have no time gaps between them
                    if split_by == 'time':

                        # assign the end time of the first selected segment
                        if prev_segment_end_time is None:
                            prev_segment_end_time = selected_segment['end']

                        # if the start time of the current segment
                        # doesn't match with the end time of the previous segment
                        elif selected_segment['start'] != prev_segment_end_time:
                            current_chunk_num = current_chunk_num+1
                            text.append({})

                            # show that there might be missing text from the transcription
                            full_text = full_text+'\n[...]\n'

                    # add the current segment text to the current text chunk
                    text[current_chunk_num]['text'] = \
                        text[current_chunk_num]['text']+'\n'+selected_segment['text'].strip() \
                        if 'text' in text[current_chunk_num] else selected_segment['text']

                    # add the start time to the current text block
                    # but only for the first segment of this text block
                    # and we determine that by checking if the start time is not already set
                    if 'start' not in text[current_chunk_num]:
                        text[current_chunk_num]['start'] = selected_segment['start']

                        # also calculate the start timecode of this text chunk (only if Resolve available)
                        # the end timecode isn't needed at this point, so no sense in wasting resources
                        text[current_chunk_num]['start_tc'] = None
                        if timecodes:

                            # init the segment start timecode object
                            # but only if the start seconds are larger than 0
                            if float(selected_segment['start']) > 0:
                                segment_start_timecode = Timecode(timeline_fps,
                                                                  start_seconds=selected_segment['start'])

                                # factor in the timeline start tc and use it for this chunk
                                text[current_chunk_num]['start_tc'] = str(timeline_start_tc+segment_start_timecode)

                            # otherwise use the timeline_start_timecode
                            else:
                                text[current_chunk_num]['start_tc'] = str(timeline_start_tc)

                            # add it to the beginning of the text
                            text[current_chunk_num]['text'] = \
                                text[current_chunk_num]['start_tc']+':\n'+text[current_chunk_num]['text'].strip()

                            # add it to the full text body
                            # but only if we're not adding a time column later
                            if not add_time_column:
                                full_text = full_text+'\n'+text[current_chunk_num]['start_tc']+':\n'

                    # add the end time of the current text chunk
                    text[current_chunk_num]['end'] = selected_segment['end']

                    # add the time to the full text, if this was requested
                    if add_time_column:
                        # use timecode or seconds depending on the timecodes parameter
                        time_column = text[current_chunk_num]['start_tc'] \
                                        if timecodes else '{:.2f}'.format(text[current_chunk_num]['start'])

                        full_text = '{}{}\t'.format(full_text, str(time_column))

                    # add the segment text to the full text variable
                    full_text = (full_text+selected_segment['text'].strip()+'\n')

                    # remember the index for the next iteration
                    prev_transcript_segment_index = transcript_segment_index

                    # split the text by each line, no matter if they're next to each other or not
                    if split_by == 'line':
                        current_chunk_num = current_chunk_num+1
                        text.append({})



            # if there are no selected segments on this window
            # get the text of the active segment
            else:
                # if active segments are not allowed
                if not allow_active_segment:
                    return None, None, None, None

                # if there is no active_segment for the window
                if window_id not in self.active_segment:

                    # create one
                    self.active_segment[window_id] = 1

                # get the line number from the active segment
                line = self.active_segment[window_id]

                # we need to convert the line number to the segment_index used in the transcript_segments list
                segment_index = line - 1

                # add the time in front of the text
                #if add_time_column:
                #    full_text = str(self.transcript_segments[window_id][segment_index]['start']) + '\t'

                # get the text form the active segment
                full_text = self.transcript_segments[window_id][segment_index]['text'].strip()

                # get the start and end times from the active segment
                start_sec = self.transcript_segments[window_id][segment_index]['start']
                end_sec = self.transcript_segments[window_id][segment_index]['end']

                # add this to the return list
                text = [{'text': full_text.strip(), 'start': start_sec, 'end': end_sec, 'start_tc': None}]

                if resolve and timecodes:
                    start_seconds = start_sec if int(start_sec) > 0 else 0.01
                    start_tc = None

                    # init the segment start timecode object
                    # but only if the start seconds are larger than 0
                    if start_sec > 0:
                        segment_start_timecode = Timecode(timeline_fps, start_seconds=start_sec)

                        # factor in the timeline start tc and use it for this chunk
                        start_tc = str(timeline_start_tc + segment_start_timecode)

                    # otherwise use the timeline_start_timecode
                    else:
                        start_tc = str(timeline_start_tc)

                    # add it at the beginning of the text body
                    full_text = start_tc+':\n'+full_text

                    # add this to the return list
                    text = [{'text': full_text.strip(), 'start': start_sec, 'end': end_sec, 'start_tc': start_tc}]

            # remove the last empty text chunk
            if 'text' not in text[-1]:
                text.pop()

            if add_to_clipboard:
                self.root.clipboard_clear()
                self.root.clipboard_append(full_text.strip())
                logger.debug('Copied segments to clipboard')

            # now get the start_sec and the end_sec for the whole text
            start_sec = text[0]['start']
            end_sec = text[-1]['end']

            return text, full_text, start_sec, end_sec

        def go_to_selected_time(self, window_id=None, position=None, ignore_selection=False):

            # if we have some selected segments, use their start and end times
            if window_id in self.selected_segments and len(self.selected_segments[window_id]) > 0 \
                    and not ignore_selection:

                start_sec = None
                end_sec = None

                # go though all the selected_segments and get the lowest start time and the highest end time
                for segment_index in self.selected_segments[window_id]:

                    # get the start time of the earliest selected segment
                    if start_sec is None or self.selected_segments[window_id][segment_index]['start'] < start_sec:
                        start_sec = self.selected_segments[window_id][segment_index]['start']

                    # get the end time of the latest selected segment
                    if end_sec is None or self.selected_segments[window_id][segment_index]['end'] > end_sec:
                        end_sec = self.selected_segments[window_id][segment_index]['end']


            # otherwise use the active segment start and end times
            else:

                # if there is no active_segment for the window, create one
                if window_id not in self.active_segment:
                    self.active_segment[window_id] = 1

                # get the line number from the active segment
                line = self.active_segment[window_id]

                # we need to convert the line number to the segment_index used in the transcript_segments list
                segment_index = line-1

                # get the start and end times from the active segment
                start_sec = self.transcript_segments[window_id][segment_index]['start']
                end_sec = self.transcript_segments[window_id][segment_index]['end']


            # decide where to go depending on which position requested
            if position == 'end':
                seconds = end_sec
            else:
                seconds = start_sec

            # move playhead to seconds
            self.toolkit_ops_obj.go_to_time(seconds=seconds)

        def get_active_segment(self, window_id=None, initial_value=0):
            '''
            This returns the active segment number for the window with the window_id
            :param window_id:
            :return:
            '''
            # if there is no active_segment for the window, create one
            # this will help us keep track of where we are with the cursor
            if window_id not in self.active_segment:
                # but start with 0, considering that it will be re-calculated below
                self.active_segment[window_id] = initial_value

            # same as above for the last_active_segment
            if window_id not in self.last_active_segment:
                # but start with 0, considering that it will be re-calculated below
                self.last_active_segment[window_id] = initial_value

            return self.active_segment[window_id]

        def get_transcription_window_text_element(self, window_id=None):

            if window_id is None:
                logger.error('No window id was passed.')
                return None

            # search through all the elements in the window until we find the transcript text element
            for child in self.toolkit_UI_obj.windows[window_id].winfo_children():

                # go another level deeper, since we are expecting the transcript text element to be inside a frame
                if len(child.winfo_children()) > 0:
                    for child2 in child.winfo_children():
                        if child2.winfo_name() == 'transcript_text':
                            return child2

            # if we get here, we didn't find the transcript text element
            return None

        def set_active_segment(self, window_id=None, text_element=None, line=None, line_calc=None):

            # if no text element is passed,
            # try to get the transcript text element from the window with the window_id
            if text_element is None and self.toolkit_UI_obj is not None and window_id is not None\
                    and window_id in self.toolkit_UI_obj.windows:

                text_element = self.get_transcription_window_text_element(window_id=window_id)

            # if no text element is found, return
            if text_element is None:
                return False

            # remove any active segment tags
            text_element.tag_delete('l_active')

            # count the number of lines in the text
            text_num_lines = len(self.transcript_segments[window_id])

            # initialize the active segment number
            self.active_segment[window_id] = self.get_active_segment(window_id)

            # interpret the line number correctly
            # by passing line_calc, we can add that to the current line number
            if line is None and line_calc:
                line = self.active_segment[window_id] + line_calc

            # remove the active segment if no line or line_calc was passed
            if line is None and line_calc is None:
                del self.active_segment[window_id]
                return False

            # if passed line is lower than 1, go to the end of the transcript
            if line < 1:
                line = text_num_lines

            # if the line is larger than the number of lines, go to the beginning of the transcript
            elif line > text_num_lines:
                line = 1

            # first copy the active segment line number to the last active segment line number
            self.last_active_segment[window_id] = self.active_segment[window_id]

            # then update the active segment
            self.active_segment[window_id] = line

            # now tag the active segment
            text_element.tag_add("l_active", "{}.0".format(line), "{}.end+1c".format(line))
            # text_element.tag_config('l_active', foreground=self.toolkit_UI_obj.resolve_theme_colors['white'])

            # add some nice colors
            text_element.tag_config('l_active', foreground=self.toolkit_UI_obj.resolve_theme_colors['superblack'],
                                    background=self.toolkit_UI_obj.resolve_theme_colors['normal'])

            # also scroll the text element to the line
            text_element.see(str(line) + ".0")

        def clear_selection(self, window_id=None, text_element=None):
            '''
            This clears the segment selection for the said window
            :param window_id:
            :return:
            '''

            if window_id is None:
                return False

            self.selected_segments[window_id] = {}

            self.selected_segments[window_id].clear()

            if text_element is None:
                text_element = self.get_transcription_window_text_element(window_id=window_id)

            if text_element is not None:
                text_element.tag_delete("l_selected")

        def segment_to_selection(self, window_id=None, text_element=None, line: int or list = None):
            '''
            This either adds or removes a segment to a selection,
            depending if it's already in the selection or not

            If line is a list, it will add all the lines in the list to the selection and remove the rest

            :param window_id:
            :param text_element:
            :param line: Either the line no. or a list of line numbers
                        (if a list is passed, it will only add and not remove)
            :return:
            '''

            # if no text element is passed,
            # try to get the transcript text element from the window with the window_id
            if text_element is None and self.toolkit_UI_obj is not None and window_id is not None\
                    and window_id in self.toolkit_UI_obj.windows:

                text_element = self.get_transcription_window_text_element(window_id=window_id)

            if window_id is None or text_element is None or line is None:
                return False

            # if there is no selected_segments dict for the current window, create one
            if window_id not in self.selected_segments:
                self.selected_segments[window_id] = {}

            # if a list of lines was passed, add all the lines to the selection
            if type(line) is list:

                # first clear the selection
                self.clear_selection(window_id=window_id, text_element=text_element)

                # select all the lines in the list
                for line_num in line:

                    # convert the line number to segment_index
                    segment_index = line_num - 1

                    self.selected_segments[window_id][line_num] = self.transcript_segments[window_id][segment_index]

                    # tag the text on the text element
                    text_element.tag_add("l_selected", "{}.0".format(line_num), "{}.end+1c".format(line_num))

                    # raise the tag so we can see it above other tags
                    text_element.tag_raise("l_selected")

                    # color the tag accordingly
                    text_element.tag_config('l_selected', foreground='blue',
                                            background=self.toolkit_UI_obj.resolve_theme_colors['superblack'])

                return True

            # if a single line was passed, add or remove it from the selection
            else:

                # convert the line number to segment_index
                segment_index = line-1

                # if the segment is not in the transcript segments dict
                if line in self.selected_segments[window_id]:
                    # remove it
                    del self.selected_segments[window_id][line]

                    # remove the tag on the text in the text element
                    text_element.tag_remove("l_selected", "{}.0".format(line), "{}.end+1c".format(line))

                # otherwise add it
                else:
                    self.selected_segments[window_id][line] = self.transcript_segments[window_id][segment_index]

                    # tag the text on the text element
                    text_element.tag_add("l_selected", "{}.0".format(line), "{}.end+1c".format(line))

                    # raise the tag so we can see it above other tags
                    text_element.tag_raise("l_selected")

                    # color the tag accordingly
                    text_element.tag_config('l_selected', foreground='blue',
                                            background=self.toolkit_UI_obj.resolve_theme_colors['superblack'])

            return True

        def segment_line_to_id(self, window_id, line):

            # is there a reference to this current window id?
            # normally this should have been created during the opening of the transcription window
            if window_id in self.transcript_segments_ids:

                # is there a reference to the line number?
                if line in self.transcript_segments_ids[window_id]:

                    # then return the stored segment id
                    return self.transcript_segments_ids[window_id][line]

            # if all fails return None
            return None

        def segment_id_to_line(self, window_id, segment_id):

            # is there a reference to this current window id?
            # normally this should have been created during the opening of the transcription window
            if window_id in self.transcript_segments_ids:

                # go through all the ids and return the line number
                try:
                    line = list(self.transcript_segments_ids[window_id].keys()) \
                                [list(self.transcript_segments_ids[window_id].values()).index(segment_id)]

                    # if the line was found, return it
                    return line

                # if the line wasn't found return None
                except ValueError:
                    return None


            # if all fails return None
            return None

        def next_segment_id(self, window_id):
            # is there a reference to this current window id?
            # normally this should have been created during the opening of the transcription window
            if window_id in self.transcript_segments_ids:

                # go through all the ids and calculate the highest
                max_id = 0
                for line_id in self.transcript_segments_ids[window_id]:
                    if max_id < self.transcript_segments_ids[window_id][line_id]:
                        max_id = self.transcript_segments_ids[window_id][line_id]

                # if the line was found, return it
                return int(max_id)+1

            # if all fails return None
            return None

        def group_selected(self, window_id: str, group_name: str = None, add: bool = False) -> bool:
            '''
            This adds the selected segments to a group based on their start and end times
            :param window_id:
            :param group_name: If this is passed, we're just adding the selected segments to the group
            :param add: If this is True, we're adding the selected segments to the group, if it's False,
                        we're only keeping the selected segments in the group
            :return:
            '''

            #group_name = 'another test group'
            #group_notes = 'some test notes'

            group_notes = ''

            # if we have some selected segments, group them
            if window_id in self.selected_segments and len(self.selected_segments[window_id]) > 0:

                # if no group name is available, ask the user for one
                if group_name is None:
                    # ask the user for a group name
                    group_name = simpledialog.askstring('Group name', 'Group name:')

                    # if the user didn't enter anything or canceled, abort
                    if not group_name:
                        return False

                # get the path of the window transcription file based on the window id
                if window_id in self.transcription_file_paths:
                    transcription_file_path = self.transcription_file_paths[window_id]
                else:
                    return False

                # get the existing groups
                if window_id in self.transcript_groups:
                    transcript_groups = self.transcript_groups[window_id]

                else:
                    transcript_groups = {}

                # the segments we pass for grouping need to be in a list format
                segments_for_group = list(self.selected_segments[window_id].values())

                # lowercase all dictionary keys for non-case sensitive comparison
                transcript_groups_lower = {k.lower(): v for k, v in transcript_groups.items()}

                # if this is an add operation and
                # if the group name was passed and it exists in the groups of this transcription,
                # add the selected segments to that group instead of creating a new one
                # (so keep the old segments in the group too)
                if add is True and group_name is not None and group_name.lower() in transcript_groups_lower \
                        and len(transcript_groups[group_name]) > 0 \
                        and 'time_intervals' in transcript_groups[group_name]\
                        and len(transcript_groups[group_name]['time_intervals']) > 0:

                    # but we first need to get the existing segments in the group
                    # by going through the time intervals of the group and getting the corresponding segments
                    existing_group_segments = \
                        self.toolkit_ops_obj.time_intervals_to_transcript_segments(
                                transcript_groups[group_name]['time_intervals'],
                                self.transcript_segments[window_id]
                        )

                    if existing_group_segments is not None:
                        # then we add the new segments to the existing ones
                        # don't worry if there are duplicates, the save function will take care of that
                        segments_for_group += existing_group_segments

                    logger.debug('Adding segments to group: {}'.format(group_name))

                # but if this is not an add operation, yet the group exists in the groups of this transcription
                # make sure the user understands that we're overwriting the existing group
                # BTW to simplify things we're now using the lower case version of the group name as a group_id
                elif add is False and group_name is not None and group_name.strip().lower() in transcript_groups_lower:

                    # ask the user if they're sure they want to overwrite the existing group
                    overwrite = messagebox.askyesno(message='Group already exists\nDo you want to overwrite it?\n\n'
                                                            'This will also empty the group notes.')

                    # if the user didn't confirm, abort
                    if not overwrite:
                        return False

                    logger.debug('Overwriting group: {}'.format(group_name))

                else:
                    logger.debug('Creating new group: {}'.format(group_name))

                # save the segments to the transcription file
                save_return = self.toolkit_ops_obj.t_groups_obj\
                                        .save_segments_as_group_in_transcription_file(
                                            transcription_file_path=transcription_file_path,
                                            segments=segments_for_group,
                                            group_name=group_name,
                                            group_notes=group_notes,
                                            existing_transcript_groups=transcript_groups,
                                            overwrite_existing=True
                )

                if type(save_return) is dict:

                    # initialize the empty group if it doesn't exist
                    if window_id not in self.transcript_groups:
                        self.transcript_groups[window_id] = {}

                    # if the returned value is a dictionary, it means that the window groups have been updated
                    # so we need to update the groups of this window
                    self.transcript_groups[window_id] = save_return

                else:
                    logger.debug('Something may have went wrong while saving the group to the transcription file')
                    return False

                # update the list of groups in the transcript groups window
                self.toolkit_UI_obj.update_transcript_groups_window(t_window_id=window_id)

                return True

        def delete_group(self, t_window_id: str, group_id: str, no_confirmation: bool = False, **kwargs) -> bool:
            '''
            This deletes a group from the transcription file
            and updates the transcription groups window (optional, only if t_group_window_id, groups_listbox are passed)

            :param t_window_id: The transcription window id
            :param group_id:
            :param no_confirmation: If this is True, we're not asking the user for confirmation
            :return:
            '''

            # get the path of the window transcription file based on the window id
            if t_window_id in self.transcription_file_paths:
                transcription_file_path = self.transcription_file_paths[t_window_id]
            else:
                logger.debug('Could not find transcription file path for window id: {}'.format(t_window_id))
                return False

            # get the existing groups
            if t_window_id in self.transcript_groups:
                transcript_groups = self.transcript_groups[t_window_id]

            else:
                transcript_groups = {}
                return True

            # check the group id
            if group_id is None or group_id.strip() == '':
                logger.debug('No group id was passed')
                return False

            # if the group id exists in the groups of this transcription
            if group_id in transcript_groups:

                group_name = transcript_groups[group_id]['name']

                # ask the user if they're sure they want to delete the group
                if not no_confirmation:
                    delete = messagebox.askyesno(message=
                                                 'Are you sure you want to delete '
                                                 'the group "{}"?'.format(group_name))

                    # if the user didn't confirm, abort
                    if not delete:
                        return False

                # remove the group from the groups dictionary
                del transcript_groups[group_id]

                # save the groups to the transcription file
                save_return = self.toolkit_ops_obj.t_groups_obj\
                    .save_transcript_groups(transcription_file_path=transcription_file_path,
                                            transcript_groups=transcript_groups)

                # if the returned value is a dictionary, it means that the window groups have been updated
                if type(save_return) is dict:

                    # update the window with the returned transcript groups
                    self.transcript_groups[t_window_id] = save_return

                    # if the selected group is no longer in the groups of this window
                    # make sure it's also not selected anymore
                    if t_window_id in self.selected_groups \
                        and group_id in self.selected_groups[t_window_id]:

                            # remove the group from the selected groups
                            self.selected_groups[t_window_id].remove(group_id)

                    # update the transcript groups window, if the right arguments were passed:
                    # the kwargs should contain the transcript groups window id and the groups listbox
                    if 't_group_window_id' in kwargs and 'groups_listbox' in kwargs:
                        self.toolkit_UI_obj.update_transcript_groups_window(t_window_id=t_window_id, **kwargs)

                    return True

                else:
                    logger.debug('Something may have went wrong while saving the groups to the transcription file')
                    return False



        def on_press_add_segment(self, event, window_id=None, text=None):
            '''
            This adds a new segment to the transcript
            :param event: the event that triggered this function
            :param window_id: the window id
            :param text: the text element
            :return:
            '''

            if window_id is None or text is None:
                return False

            # get the cursor position where the event was triggered (key was pressed)
            # and the last character of the line
            line, char, last_char = self.get_current_segment_chars(text=text)

            #print('Pos: {}.{}; Last: {}'.format(line, char, last_char))

            # initialize the new_line dict
            new_line = {}

            # the end time of the new line is the end of the current line
            new_line['end'] = self.transcript_segments[window_id][int(line)-1]['end']

            # get the text that is supposed to go on the next line
            new_line['text'] = text.get(INSERT, "{}.end".format(line))

            # the id of the new line is the next available id in the transcript
            new_line['id'] = self.next_segment_id(window_id=window_id)

            # keep in mind the minimum and maximum split times
            split_time_seconds_min = self.transcript_segments[window_id][int(line)-1]['start']
            split_time_seconds_max = self.transcript_segments[window_id][int(line)-1]['end']

            # if resolve is connected, get the timecode from resolve
            if resolve:

                # ask the user to move the playhead in Resolve to where the split should happen via info dialog
                move_playhead = messagebox.askokcancel(title='Move playhead',
                                       message='Move the Resolve playhead exactly '
                                              'where the new segment starts, '
                                              'then press OK to split.'
                                       )

                if not move_playhead:
                    logger.debug('User cancelled segment split.')
                    return 'break'

                # convert the current resolve timecode to seconds
                split_time_seconds = self.toolkit_ops_obj.calculate_resolve_timecode_to_sec()

            # if resolve isn't connected, ask the user to enter the timecode manually
            else:

                # ask the user to enter the timecode manually
                split_time_seconds = simpledialog.askstring(
                                        parent=self.toolkit_UI_obj.windows[window_id],
                                        title='Where to split?',
                                        prompt='At what time should we split this segment?\n\n'
                                               'Enter a value between {} and {}:\n'
                                                .format(split_time_seconds_min,
                                                        split_time_seconds_max),
                                        initialvalue=split_time_seconds_min)

            # if the user didn't specify the split time
            if not split_time_seconds:
                # cancel
                return 'break'

            if float(split_time_seconds) >= float(split_time_seconds_max):

                self.toolkit_UI_obj.notify_via_messagebox(title='Time Value Error',
                                                          message="The {} time is larger "
                                                                  "than the end time of "
                                                                  "the segment you're splitting. Try again.".
                                                                    format('playhead' if resolve else 'entered'),
                                                          type='warning')
                return 'break'

            if float(split_time_seconds) <= float(split_time_seconds_min):

                self.toolkit_UI_obj.notify_via_messagebox(title='Time Value Error',
                                                          message="The {} time is smaller "
                                                                  "than the start time of "
                                                                  "the segment you're splitting. Try again.".
                                                                    format('playhead' if resolve else 'entered'),
                                                          type='warning')

                return 'break'

            # the split time becomes the start time of the new line
            new_line['start'] = split_time_seconds

            # and also the end of the previous line
            self.transcript_segments[window_id][int(line)-1]['end'] = split_time_seconds

            # add the element to the transcript segments right after the current line
            self.transcript_segments[window_id].insert(int(line), new_line)

            # remove the text after the split from the current line
            text.delete("{}.{}".format(line, char), "{}.end".format(line))

            # re-insert the text after the last character of the current line, but also add a line break
            text.insert("{}.end+1c".format(line), new_line['text']+'\n')

            # remap the line numbers to segment ids for this window
            self.remap_lines_to_segment_ids(window_id=window_id, text=text)

            # prevent RETURN key from adding another line break in the text
            return 'break'

        def remap_lines_to_segment_ids(self, window_id, text):

            if window_id is None or text is None:
                return False

            # get all the lines of this text widget
            text_lines = text.get('1.0', END).splitlines()

            # reset self.transcript_segments_ids[window_id]
            self.transcript_segments_ids[window_id] = {}

            if len(text_lines) > 0:

                # go through all the lines and re check segment ids
                for line_no, line in enumerate(text_lines):

                    # the last line of the text widget is always empty, so avoid that
                    if line_no < len(self.transcript_segments[window_id]):

                        # print(line_no, line)

                        # get the segment id for this line directly from the transcript segments dict
                        # that we updated earlier during the split
                        line_segment_id = self.transcript_segments[window_id][line_no]['id']

                        # remap the line no to segment ids for this window
                        self.transcript_segments_ids[window_id][line_no] = line_segment_id

            return True

        def edit_transcript(self, window_id=None, text=None, status_label=None):

            if window_id is None or text is None:
                return False

            text.focus()

            # enable typing mode to disable some shortcuts
            self.set_typing_in_window(window_id=window_id, typing=True)

            # enable transcript_editing for this window
            self.set_transcript_editing(window_id=window_id, editing=True)

            text.bind('<Return>', lambda e: self.on_press_add_segment(e, window_id, text))

            # ESCAPE key defocuses transcript (and implicitly saves the transcript, see below)
            text.bind('<Escape>', lambda e: self.defocus_transcript(text=text))

            # text focusout saves transcript
            text.bind('<FocusOut>', lambda e: self.on_press_save_transcript(e, window_id, text,
                                                                          status_label=status_label))

            # BACKSPACE key at first line character merges the current and the previous segment
            text.bind('<BackSpace>', lambda e:
                    self.on_press_merge_segments(e, window_id=window_id, text=text, merge='previous'))

            # DELETE key at last line character merges the current and the next segment
            text.bind('<Delete>', lambda e:
                    self.on_press_merge_segments(e, window_id=window_id, text=text, merge='next'))

            if status_label is not None:
                status_label.config(text='Not saved.', foreground=self.toolkit_UI_obj.resolve_theme_colors['red'])

            text.config(state=NORMAL)

        def unbind_editing_keys(self, text):
            '''
            This function unbinds all the keys used for editing the transcription
            :return:
            '''

            text.unbind('<Return>')
            text.unbind('<Escape>')
            text.unbind('<BackSpace>')
            text.unbind('<Delete>')

        def get_current_segment_chars(self, text):

            # get the position of the cursor
            line, char = text.index(INSERT).split('.')

            # get the index of the last character of the line where the cursor is
            _, last_char = text.index("{}.end".format(line)).split('.')

            return line, char, last_char

        def set_transcript_modified(self, window_id=None, modified=True):
            '''
            This function sets the transcript_modified flag for the given window
            :param window_id:
            :param modified:
            :return:
            '''

            if window_id is None:
                return False

            self.transcript_modified[window_id] = modified

        def get_transcript_modified(self, window_id):
            '''
            This function returns the transcript_modified flag for the given window
            :param window_id:
            :return:
            '''

            if window_id in self.transcript_modified:
                return self.transcript_modified[window_id]
            else:
                return False

        def on_press_merge_segments(self, event, window_id, text, merge=None):
            '''
            This function checks whether the cursor is at the beginning or at the end of the line and
            it merges the current transcript segment either with the previous or with the next segment

            :param event:
            :param window_id:
            :param text:
            :return:
            '''

            if window_id is None or text is None:
                return False

            if merge not in ['previous', 'next']:
                logger.error('Merge direction not specified.')
                return 'break'

            # get the cursor position where the event was triggered (key was pressed)
            # and the last character of the line
            line, char, last_char = self.get_current_segment_chars(text=text)

            # ignore if we are not at the beginning nor at the end of the current line
            # or if the direction of the merge doesn't match the character number
            if char not in ['0', last_char]\
                or (char == '0' and merge != 'previous')\
                or (char == last_char and merge != 'next'):
                return

            # if we are at the beginning of the line
            # and the merge direction is 'prev'
            if char == '0' and merge == 'previous':

                # get the previous segment
                previous_segment = self.transcript_segments[window_id][int(line)-2]

                # get the current segment
                current_segment = self.transcript_segments[window_id][int(line)-1]

                # merge the current segment with the previous one
                previous_segment['end'] = current_segment['end']
                previous_segment['text'] = previous_segment['text'] + '' + current_segment['text'].lstrip()

                if 'tokens' in current_segment and 'tokens' in previous_segment:
                    previous_segment['tokens'] = previous_segment['tokens'] + current_segment['tokens']

                # signal that the transcript segments has been modified
                previous_segment['merged'] = True

                # remove the line break from the previous line
                text.delete("{}.end".format(int(line)-1), "{}.end+1c".format(int(line)-1))

                # update the previous segment in the list
                self.transcript_segments[window_id][int(line)-2] = previous_segment

                # remove the current segment from the list (the list starts with index 0)
                self.transcript_segments[window_id].pop(int(line)-1)

                # remap self.transcript_segments_ids
                self.remap_lines_to_segment_ids(window_id=window_id, text=text)

                # update the transcript_modified flag
                self.set_transcript_modified(window_id=window_id, modified=True)

                # we're done, prevent the event from propagating and deleting any characters
                return 'break'

            # if we are at the end of the line
            # and the merge direction is 'next'
            if char == last_char and merge == 'next':

                # get the current segment
                current_segment = self.transcript_segments[window_id][int(line)-1]

                # get the next segment
                next_segment = self.transcript_segments[window_id][int(line)]

                # merge the current segment with the next one
                current_segment['end'] = next_segment['end']
                current_segment['text'] = current_segment['text'] + '' + next_segment['text'].lstrip()

                if 'tokens' in current_segment and 'tokens' in next_segment:
                    current_segment['tokens'] = current_segment['tokens'] + next_segment['tokens']

                # signal that the transcript segments have been modified
                current_segment['merged'] = True

                # remove the line break from current line
                text.delete('{}.end'.format(line), '{}.end+1c'.format(line))

                # remove the next segment from the list (the list starts with index 0)
                self.transcript_segments[window_id].pop(int(line))

                # remap self.transcript_segments_ids
                self.remap_lines_to_segment_ids(window_id=window_id, text=text)

                # update the transcript_modified flag
                self.set_transcript_modified(window_id=window_id, modified=True)

                # we're done
                return 'break'

            return 'break'

        def defocus_transcript(self, text):

            # defocus from transcript text
            tk_transcription_window = text.winfo_toplevel()
            tk_transcription_window.focus()

        def on_press_save_transcript(self, event, window_id, text, status_label=None):

            if window_id is None or text is None:
                return False

            # disable text editing again
            text.config(state=DISABLED)

            # unbind all the editing keys
            self.unbind_editing_keys(text)

            # deactivate typing and editing for this window
            self.set_typing_in_window(window_id=window_id, typing=False)
            self.set_transcript_editing(window_id=window_id, editing=False)

            # save the transcript
            save_status = self.save_transcript(window_id=window_id, text=text)

            # let the user know what happened via the status label
            self.update_status_label_after_save(status_label=status_label, save_status=save_status)

        def update_status_label_after_save(self, save_status, status_label):

            if save_status is True:
                # show the user that the transcript was saved
                if status_label is not None:
                    status_label.config(text='Saved.',
                                        foreground=self.toolkit_UI_obj.resolve_theme_colors['normal'])

            # in case anything went wrong while saving,
            # let the user know about it
            elif save_status == 'fail':
                if status_label is not None:
                    status_label.config(text='Save Failed.',
                                        foreground=self.toolkit_UI_obj.resolve_theme_colors['red'])

            # in case the save status is False
            # assume that nothing needed saving
            else:
                if status_label is not None:
                    status_label.config(text='Nothing changed.',
                                        foreground=self.toolkit_UI_obj.resolve_theme_colors['normal'])

        def save_transcript(self, window_id=None, text=None, skip_verification=False):
            '''
            This function saves the transcript to the file

            :param window_id:
            :param text:
            :param skip_verification: if this is True, the function will not verify
                                        if the transcript has been modified and ignore the new text
                                        (useful for non-text updates, like start/end time changes etc.)
            :return:
            '''

            if window_id is None or text is None:
                logger.debug('No window id or text provided.')
                return False

            # make sure that we know the path to this transcription file
            if not window_id in self.transcription_file_paths:
                return 'fail'

            # get the path of the transcription file
            transcription_file_path = self.transcription_file_paths[window_id]

            # get the contents of the transcription file
            old_transcription_file_data = \
                self.toolkit_ops_obj.get_transcription_file_data(transcription_file_path=transcription_file_path)

            # only verify if skip_verification is False or the text is False
            if not skip_verification or text is not False:

                # compare the edited lines with the existing transcript lines
                text_lines = text.get('1.0', END).splitlines()

                segment_no = 0
                full_text = ''

                # find out if the transcript has been modified
                modified = self.get_transcript_modified(window_id=window_id)

                # but even if the transcript has not been modified,
                # we still need to check if the transcript has been edited
                while segment_no < len(text_lines)-1:

                    # add the segment text to a full text variable in case we need it later
                    full_text = full_text+' '+text_lines[segment_no]

                    # if any change to the text was found
                    if text_lines[segment_no].strip() != self.transcript_segments[window_id][segment_no]['text'].strip():

                        # overwrite the segment text with the new text
                        self.transcript_segments[window_id][segment_no]['text'] = text_lines[segment_no].strip()+' '

                        # it means that we have to save the new file
                        modified = True

                    segment_no = segment_no + 1

            # make sure to no longer use the text below if skip_verification is True
            else:
                text = False
                modified = True
                full_text = None

            # if the transcript has been modified (changes detected above or simply modified flag is True)
            if modified:

                modified_transcription_file_data = old_transcription_file_data

                # replace the segments in the transcription file
                modified_transcription_file_data['segments'] = self.transcript_segments[window_id]

                if text is not False:
                    # replace the full text in the trancription file
                    modified_transcription_file_data['text'] = full_text

                # add the last modified key
                modified_transcription_file_data['last_modified'] = str(time.time()).split('.')[0]

                # the directory where the transcription file is
                transcription_file_dir = os.path.dirname(transcription_file_path)

                # now save the txt file
                # if there is no txt file associated with this transcription
                if 'txt_file_path' not in modified_transcription_file_data \
                        or modified_transcription_file_data['txt_file_path'] == '':

                    txt_file_name = os.path.basename(transcription_file_path).replace('.transcription.json', '.txt')

                else:
                    txt_file_name = modified_transcription_file_data['txt_file_path']

                if txt_file_name is not None and txt_file_name != '':
                    # the txt file should be in the same directory as the transcription file
                    txt_file_path = os.path.join(transcription_file_dir, txt_file_name)

                    # add the file to the transcription file data
                    modified_transcription_file_data['txt_file_path'] = txt_file_name

                    # save the txt file
                    self.toolkit_ops_obj.save_txt_from_transcription(
                        txt_file_path=txt_file_path,
                        transcription_data=modified_transcription_file_data
                    )

                # now save the srt file
                srt_file_name = None

                # if there is no srt file associated with this transcription
                if 'srt_file_path' not in modified_transcription_file_data \
                        or modified_transcription_file_data['srt_file_path'] == '':

                    # ask the user if they want to create an srt file
                    create_srt = messagebox.askyesno('Create SRT file?',
                                                     'An SRT file doesn\'t exist for this transcription.\n'
                                                     'Do you want to create one?')

                    # if the user wants to create an srt file
                    if create_srt:
                        # the name of the srt file is based on the name of the transcription file
                        srt_file_name = os.path.basename(transcription_file_path).replace('.transcription.json', '.srt')

                else:
                    srt_file_name = modified_transcription_file_data['srt_file_path']

                if srt_file_name is not None and srt_file_name != '':

                    # the srt file should be in the same directory as the transcription file
                    srt_file_path = os.path.join(transcription_file_dir, srt_file_name)

                    # add the file to the transcription file data
                    modified_transcription_file_data['srt_file_path'] = srt_file_name

                    # save the srt file
                    self.toolkit_ops_obj.save_srt_from_transcription(
                        srt_file_path=srt_file_path,
                        transcription_data=modified_transcription_file_data
                    )

                # finally, save the transcription file
                self.toolkit_ops_obj.save_transcription_file(transcription_file_path=transcription_file_path,
                                                             transcription_data=modified_transcription_file_data,
                                                             backup='backup')

                return True

            # returning false means that no changes were made
            return False

    class AppItemsUI:

        def __init__(self, toolkit_UI_obj):

            if toolkit_UI_obj is None:
                logger.error('No toolkit_UI_obj provided for AppItemsUI.')
                raise Exception('No toolkit_UI_obj provided.')

            # declare the UI, ops and app objects for easier access
            self.toolkit_UI_obj = toolkit_UI_obj
            self.toolkit_ops_obj = toolkit_UI_obj.toolkit_ops_obj
            self.stAI = toolkit_UI_obj.stAI
            self.UI_menus = toolkit_UI_obj.UImenus

            # the root window inherited from the toolkit_UI_obj
            self.root = toolkit_UI_obj.root

            return

        def open_preferences_window(self):

            # create a window for the transcription settings if one doesn't already exist
            if pref_window := self.toolkit_UI_obj.create_or_open_window(parent_element=self.root, window_id='preferences',
                                           title='Preferences', resizable=True, return_window=True):

                form_grid_and_paddings = {**self.toolkit_UI_obj.input_grid_settings,
                                          **self.toolkit_UI_obj.form_paddings}

                label_settings = self.toolkit_UI_obj.label_settings
                del label_settings['width']

                entry_settings = self.toolkit_UI_obj.entry_settings
                entry_settings_quarter = self.toolkit_UI_obj.entry_settings_quarter

                # the settings for the heading labels
                h1_font = {'font': self.toolkit_UI_obj.default_font_h1, 'justify': 'center',
                           'pady': self.toolkit_UI_obj.form_paddings['pady']}

                pref_form_frame = tk.Frame(pref_window)
                pref_form_frame.pack()

                # these are the app settings that can be changed

                # take all the customizable app settings and create a variable for each one
                default_marker_color_var \
                    = tk.StringVar(pref_form_frame,
                                   value=self.stAI.get_app_setting('default_marker_color', default_if_none='Blue'))

                console_font_size_var \
                    = tk.IntVar(pref_form_frame,
                                   value=self.stAI.get_app_setting('console_font_size', default_if_none=13))

                show_welcome_var \
                    = tk.BooleanVar(pref_form_frame,
                                    value=self.stAI.get_app_setting('show_welcome', default_if_none=True))

                disable_resolve_api_var \
                    = tk.BooleanVar(pref_form_frame,
                                    value=self.stAI.get_app_setting('disable_resolve_api', default_if_none=False))

                open_transcript_groups_window_on_open_var \
                    = tk.BooleanVar(pref_form_frame,
                                    value=self.stAI.get_app_setting('show_welcome', default_if_none=True))

                close_transcripts_on_timeline_change_var \
                    = tk.BooleanVar(pref_form_frame,
                                    value=self.stAI.get_app_setting('close_transcripts_on_timeline_change',
                                                                    default_if_none=True))

                whisper_model_name_var\
                    = tk.StringVar(pref_form_frame,
                                   value=self.stAI.get_app_setting('whisper_model_name', default_if_none='medium'))

                whisper_device_var\
                    = tk.StringVar(pref_form_frame,
                                  value=self.stAI.get_app_setting('whisper_device', default_if_none='auto'))

                transcription_default_language_var\
                    = tk.StringVar(pref_form_frame,
                                   value=self.stAI.get_app_setting('transcription_default_language',
                                                                   default_if_none=''))

                transcription_render_preset_var\
                    = tk.StringVar(pref_form_frame,
                                      value=self.stAI.get_app_setting('transcription_render_preset',
                                                                      default_if_none='transcription_WAV'))

                transcript_font_size_var\
                    = tk.IntVar(pref_form_frame,
                                      value=self.stAI.get_app_setting('transcript_font_size', default_if_none=15))

                transcripts_always_on_top_var\
                    = tk.BooleanVar(pref_form_frame,
                                    value=self.stAI.get_app_setting('transcripts_always_on_top', default_if_none=False))

                #ffmpeg_path_var\
                #    = tk.StringVar(pref_form_frame,
                #                    value=self.stAI.get_app_setting('ffmpeg_path', default_if_none=''))

                # now create the form for all of the above settings
                # general settings
                tk.Label(pref_form_frame, text='General Settings', **h1_font).grid(row=0, column=0, columnspan=2, **form_grid_and_paddings)

                tk.Label(pref_form_frame, text='Default Marker Color', **label_settings).grid(row=1, column=0, **form_grid_and_paddings)

                # the default marker color
                # the dropdown for the default marker color
                default_marker_color_input = tk.OptionMenu(pref_form_frame,
                                                           default_marker_color_var,
                                                           *self.toolkit_UI_obj.resolve_marker_colors)
                default_marker_color_input.grid(row=1, column=1, **form_grid_and_paddings)

                # the font size for the console
                tk.Label(pref_form_frame, text='Console Font Size', **label_settings).grid(row=2, column=0, **form_grid_and_paddings)
                console_font_size_input = tk.Entry(pref_form_frame, textvariable=console_font_size_var, **entry_settings_quarter)
                console_font_size_input.grid(row=2, column=1, **form_grid_and_paddings)

                # show the welcome window on startup
                tk.Label(pref_form_frame, text='Show Welcome Window', **label_settings).grid(row=3, column=0, **form_grid_and_paddings)
                show_welcome_input = tk.Checkbutton(pref_form_frame, variable=show_welcome_var)
                show_welcome_input.grid(row=3, column=1, **form_grid_and_paddings)

                # Integrations
                tk.Label(pref_form_frame, text='Integrations', **h1_font).grid(row=4, column=0, columnspan=2, **form_grid_and_paddings)

                # disable the resolve API
                tk.Label(pref_form_frame, text='Disable Resolve API', **label_settings).grid(row=5, column=0, **form_grid_and_paddings)
                disable_resolve_api_input = tk.Checkbutton(pref_form_frame, variable=disable_resolve_api_var)
                disable_resolve_api_input.grid(row=5, column=1, **form_grid_and_paddings)

                # auto open the transcript groups window on timeline open
                tk.Label(pref_form_frame, text='Open Linked Transcripts', **label_settings).grid(row=6, column=0, **form_grid_and_paddings)
                open_transcript_groups_window_on_open_input = tk.Checkbutton(pref_form_frame, variable=open_transcript_groups_window_on_open_var)
                open_transcript_groups_window_on_open_input.grid(row=6, column=1, **form_grid_and_paddings)

                # close transcripts on timeline change
                tk.Label(pref_form_frame, text='Close Transcripts on Timeline Change', **label_settings).grid(row=7, column=0, **form_grid_and_paddings)
                close_transcripts_on_timeline_change_input = tk.Checkbutton(pref_form_frame, variable=close_transcripts_on_timeline_change_var)
                close_transcripts_on_timeline_change_input.grid(row=7, column=1, **form_grid_and_paddings)


                # transcriptions
                tk.Label(pref_form_frame, text='Transcriptions', **h1_font).grid(row=8, column=0, columnspan=2, **form_grid_and_paddings)

                # the whisper model name
                tk.Label(pref_form_frame, text='Whisper Model', **label_settings).grid(row=9, column=0, **form_grid_and_paddings)
                whisper_model_name_input = tk.OptionMenu(pref_form_frame, whisper_model_name_var, *whisper.available_models())
                whisper_model_name_input.grid(row=9, column=1, **form_grid_and_paddings)

                # the whisper device
                tk.Label(pref_form_frame, text='Whisper Device', **label_settings).grid(row=10, column=0, **form_grid_and_paddings)
                whisper_device_input = tk.OptionMenu(pref_form_frame, whisper_device_var,
                                                     *self.toolkit_ops_obj.get_torch_available_devices())
                whisper_device_input.grid(row=10, column=1, **form_grid_and_paddings)

                # the default language for transcriptions
                # first get the list of languages, but also add an empty string to the list
                available_languages = [''] + self.toolkit_ops_obj.get_whisper_available_languages()

                tk.Label(pref_form_frame, text='Default Language', **label_settings).grid(row=11, column=0, **form_grid_and_paddings)
                transcription_default_language_input = tk.OptionMenu(pref_form_frame, transcription_default_language_var,
                                                                     *available_languages)
                transcription_default_language_input.grid(row=11, column=1, **form_grid_and_paddings)

                # the render preset for transcriptions
                tk.Label(pref_form_frame, text='Render Preset', **label_settings).grid(row=12, column=0, **form_grid_and_paddings)
                transcription_render_preset_input = tk.Entry(pref_form_frame, textvariable=transcription_render_preset_var, **entry_settings)
                transcription_render_preset_input.grid(row=12, column=1, **form_grid_and_paddings)

                # the transcript font size
                tk.Label(pref_form_frame, text='Transcript Font Size', **label_settings).grid(row=13, column=0, **form_grid_and_paddings)
                transcript_font_size_input = tk.Entry(pref_form_frame, textvariable=transcript_font_size_var, **entry_settings_quarter)
                transcript_font_size_input.grid(row=13, column=1, **form_grid_and_paddings)

                # transcripts always on top
                tk.Label(pref_form_frame, text='Transcript Always On Top', **label_settings).grid(row=14, column=0, **form_grid_and_paddings)
                transcripts_always_on_top_input = tk.Checkbutton(pref_form_frame, variable=transcripts_always_on_top_var)
                transcripts_always_on_top_input.grid(row=14, column=1, **form_grid_and_paddings)

                # ffmpeg path
                #tk.Label(pref_form_frame, text='FFmpeg Path', **label_settings).grid(row=14, column=0, **form_grid_and_paddings)
                #ffmpeg_path_input = tk.Entry(pref_form_frame, textvariable=ffmpeg_path_var, **entry_settings)
                #ffmpeg_path_input.grid(row=14, column=1, **form_grid_and_paddings)

                # SAVE BUTTON

                # keep track of all the input variables above
                input_variables = {
                    'default_marker_color': default_marker_color_var,
                     'console_font_size': console_font_size_var,
                     'show_welcome': show_welcome_var,
                     'disable_resolve_api': disable_resolve_api_var,
                     'open_transcript_groups_window_on_open': open_transcript_groups_window_on_open_var,
                     'close_transcripts_on_timeline_change': close_transcripts_on_timeline_change_var,
                     'whisper_model_name': whisper_model_name_var,
                     'whisper_device': whisper_device_var,
                     'transcription_default_language': transcription_default_language_var,
                     'transcription_render_preset': transcription_render_preset_var,
                     'transcript_font_size': transcript_font_size_var,
                     'transcripts_always_on_top': transcripts_always_on_top_var,
                     # 'ffmpeg_path': ffmpeg_path_var
                }


                Label(pref_form_frame, text="", **label_settings).grid(row=20, column=0, **form_grid_and_paddings)
                start_button = tk.Button(pref_form_frame, text='Save')
                start_button.grid(row=20, column=1, **form_grid_and_paddings)
                start_button.config(command=lambda: self.save_preferences(input_variables))

        def save_preferences(self, input_variables: dict) -> bool:
            '''
            Save the preferences stored in the input_variables to the app config file
            :param input_variables:
            :return:
            '''

            # save all the variables to the config file
            for key, value in input_variables.items():
                self.stAI.config[key] = value.get()

            # save the config file
            if self.stAI.save_config():

                # close the window
                self.toolkit_UI_obj.destroy_window_(self.toolkit_UI_obj.windows, 'preferences')

                # let the user know it worked
                self.toolkit_UI_obj.notify_via_messagebox(type='info', title='Preferences Saved',
                                                          message='Preferences saved successfully.\n\n'
                                                                  'Please restart StoryToolkitAI for the new settings '
                                                                  'to take full effect.',
                                                          message_log='Preferences saved, need restart for full effect')

                return True

            else:
                self.toolkit_UI_obj.notify_via_messagebox(type='error', title='Error',
                                                          message='Preferences could not be saved.\n'
                                                                  'Check log for details.',
                                                          message_log='Preferences could not be saved')

                return False

        def open_about_window(self):

            # open the about window

            # create a window for the transcription log if one doesn't already exist
            if about_window := self.toolkit_UI_obj.create_or_open_window(parent_element=self.root,
                                                    window_id='about', title='About StoryToolkitAI', resizable=False,
                                                                          return_window=True):

                # the text justify
                justify = {'justify': tk.LEFT}

                # create a frame for the about window
                about_frame = Frame(about_window)
                about_frame.pack(**self.toolkit_UI_obj.paddings)

                # add the app name text
                app_name = 'StoryToolkitAI version '+self.stAI.version

                # create the app name heading
                app_name_label = Label(about_frame, text=app_name, font=self.toolkit_UI_obj.default_font_h1, **justify)
                app_name_label.grid(column=1, row=1, sticky='w')

                # the made by frame
                made_by_frame = Frame(about_frame)
                made_by_frame.grid(column=1, row=2, sticky='w')

                # create the made by label
                made_by_label = Label(made_by_frame, text='made by', font=self.toolkit_UI_obj.default_font, **justify)
                made_by_label.pack(side=tk.LEFT)

                # create the mots link label
                mots_label = Label(made_by_frame, text='mots', font=self.toolkit_UI_obj.default_font_link, **justify)
                mots_label.pack(side=tk.LEFT)

                # make the made by text clickable
                mots_label.bind('<Button-1>', self.UI_menus.open_mots)

                # the project page frame
                project_page_frame = Frame(about_frame)
                project_page_frame.grid(column=1, row=3, sticky='w', pady=self.toolkit_UI_obj.paddings['pady'])

                # add the project page label
                project_page_label = Label(project_page_frame, text='Project page:',
                                           font=self.toolkit_UI_obj.default_font, **justify)
                project_page_label.pack(side=tk.LEFT)

                # create the project page link label
                project_page_link_label = Label(project_page_frame, text='github.com/octimot/StoryToolkitAI',
                                                font=self.toolkit_UI_obj.default_font_link, **justify)
                project_page_link_label.pack(side=tk.LEFT)

                # make the project page text clickable
                project_page_link_label.bind('<Button-1>', self.UI_menus.open_project_page)

                # add license info
                license_info_label = Label(about_frame, text='For third party software and license information\n'
                                                             'see the project page.',
                                           font=self.toolkit_UI_obj.default_font, **justify)
                license_info_label.grid(column=1, row=4, sticky='w')

                return True

            return


    def __init__(self, toolkit_ops_obj=None, stAI=None, **other_options):

        # make a reference to toolkit ops obj
        self.toolkit_ops_obj = toolkit_ops_obj

        # make a reference to StoryToolkitAI obj
        self.stAI = stAI

        # initialize tkinter as the main GUI
        self.root = tk.Tk()

        # initialize app items object
        self.app_items_obj = self.AppItemsUI(toolkit_UI_obj=self)

        # load menu object
        self.UI_menus = self.UImenus(toolkit_UI_obj=self)

        logger.debug('Running with TK {}'.format(self.root.call("info", "patchlevel")))

        # set the main window title
        self.root.title("StoryToolkitAI v{}".format(stAI.__version__))

        # temporary width and height for the main window
        self.root.config(width=1, height=1)

        # initialize transcript edit object
        self.t_edit_obj = self.TranscriptEdit(toolkit_UI_obj=self)

        # show the update available message if any
        if 'update_available' in other_options and other_options['update_available'] is not None:

            # the url to the releases page
            release_url = 'https://github.com/octimot/StoryToolkitAI/releases/latest'

            goto_projectpage = False

            # if there is a new version available
            # the user will see a different update message
            # depending if they're using the standalone version or not
            if standalone:
                warn_message = 'A new standalone version of StoryToolkitAI is available.'

                # add the question to the pop up message box
                messagebox_message = warn_message+' \n\nDo you want to open the release page?\n'

                # notify the user and ask whether to open the release website or not
                goto_projectpage = messagebox.askyesno(title="Update available",
                                                      message=messagebox_message)
            else:
                warn_message = 'A new version of StoryToolkitAI is available.\n\n' \
                               'Use git pull to update.\n '

                messagebox.showinfo(title="Update available",
                                    message=warn_message)

            # notify the user via console
            logger.warning(warn_message)

            # open the browser and go to the release_url
            if goto_projectpage:
                webbrowser.open(release_url)

        # alert the user if ffmpeg isn't installed
        if 'ffmpeg_status' in other_options and not other_options['ffmpeg_status']:

            self.notify_via_messagebox(title='FFMPEG not found',
                                       message='FFMPEG was not found on this machine.\n'
                                               'Please follow the installation instructions or StoryToolkitAI will '
                                               'not work correctly.',
                                       type='error'
                                       )

        # show welcome message, if it wasn't muted via configs
        # if self.stAI.get_app_setting('show_welcome', default_if_none=True):
        #    self.open_welcome_window()

        # keep all the window references here to find them easy by window_id
        self.windows = {}

        # set some UI styling here
        self.paddings = {'padx': 10, 'pady': 10}
        self.form_paddings = {'padx': 10, 'pady': 5}
        self.button_size = {'width': 150, 'height': 50}
        self.list_paddings = {'padx': 3, 'pady': 3}
        self.label_settings = {'anchor': 'e', 'width': 20}
        self.input_grid_settings = {'sticky': 'w'}
        self.entry_settings = {'width': 30}
        self.entry_settings_half = {'width': 20}
        self.entry_settings_quarter = {'width': 8}

        # scrollbars
        self.scrollbar_settings = {'width': 10}

        # the font size ratio
        if sys.platform == "darwin":
            font_size_ratio = 1.30
        else:
            font_size_ratio = 1

        # we're calculating the size based on the screen size
        screen_width, screen_height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        font_size_ratio *= (screen_width if screen_width>screen_height else screen_height) / 1920

        # set platform independent transcript font
        self.transcript_font = font.Font()

        # first - find out if there is any "courier" font installed
        # and select one of the versions
        available_fonts = font.families()
        if 'Courier' in available_fonts:
            self.transcript_font.configure(family='Courier')
        elif 'Courier New' in available_fonts:
            self.transcript_font.configure(family='Courier New')
        else:
            logger.debug('No "Courier" font found. Using default fixed font.')
            self.transcript_font = font.nametofont(name='TkFixedFont')

        # get transcript font size
        transcript_font_size = self.stAI.get_app_setting('transcript_font_size', default_if_none=15)

        # set the transcript font size based on the font ratio
        self.transcript_font.configure(size=int(transcript_font_size * font_size_ratio))

        #self.transcript_font.configure(size=16)

        # get console font size
        console_font_size = self.stAI.get_app_setting('console_font_size', default_if_none=13)

        # set the platform independent fixed font (for console)
        self.console_font = font.nametofont(name='TkFixedFont')
        self.console_font.configure(size=int(console_font_size * font_size_ratio))

        # set the default font size
        default_font_size = 13
        default_font_size_after_ratio = int(default_font_size * font_size_ratio)

        # set the platform independent default font
        self.default_font = tk.font.Font(font=font.nametofont(name='TkDefaultFont'))
        self.default_font.configure(size=default_font_size_after_ratio)

        # set the platform independent default link font
        self.default_font_link = tk.font.Font(font=self.default_font)
        self.default_font_link.configure(size=default_font_size_after_ratio, underline=True)

        # set the platform independent default font for headings
        self.default_font_h1 = font.nametofont(name='TkHeadingFont')
        self.default_font_h1.configure(size=int(default_font_size_after_ratio+3))

        # define the pixel size for buttons
        pixel = tk.PhotoImage(width=1, height=1)

        self.blank_img_button_settings = {'image': pixel, 'compound': 'c'}

        # these are the marker colors used in Resolve
        self.resolve_marker_colors = {
            "Blue": "#0000FF",
            "Cyan": "#00CED0",
            "Green": "#00AD00",
            "Yellow": "#F09D00",
            "Red": "#E12401",
            "Pink": "#FF44C8",
            "Purple": "#9013FE",
            "Fuchsia": "#C02E6F",
            "Rose": "#FFA1B9",
            "Lavender": "#A193C8",
            "Sky": "#92E2FD",
            "Mint": "#72DB00",
            "Lemon": "#DCE95A",
            "Sand": "#C4915E",
            "Cocoa": "#6E5143",
            "Cream": "#F5EBE1"
        }

        # these are the theme colors used in Resolve
        self.resolve_theme_colors = {
            'white': '#ffffff',
            'supernormal': '#C2C2C2',
            'normal': '#929292',
            'black': '#1F1F1F',
            'superblack': '#000000',
            'dark': '#282828',
            'red': '#E64B3D'
        }

        # CMD or CTRL?
        # use CMD for Mac
        if platform.system() == 'Darwin':
            self.ctrl_cmd_bind = "Command"
            self.alt_bind = "Mod2"
        # use CTRL for Windows
        else:
            self.ctrl_cmd_bind = "Control"
            self.alt_bind = "Alt"

        # use this variable to remember if the user said it's ok that resolve is not available to continue a process
        self.no_resolve_ok = False

    class main_window:
        pass

    def create_or_open_window(self, parent_element: tk.Toplevel = None, window_id: str = None,
                               title: str = None, resizable: bool = False,
                               close_action=None,
                               open_multiple: bool = False, return_window: bool = False) \
            -> tk.Toplevel or str or bool:
        '''
        This function creates a new window or opens an existing one based on the window_id.
        :param parent_element:
        :param window_id:
        :param title:
        :param resizable:
        :param close_action: The function to call when the window is being closed
        :param open_multiple: Allows to open multiple windows of the same type
                             (but adds the timestamp to the window_id for differentiations)
        :param return_window: If false, it just returns the window_id. If true, it returns the window object.
        :return: The window_id, the window object if return_window is True, or False if the window already exists
        '''

        # if the window is already opened somewhere, do this
        # (but only if open_multiple is False)
        if window_id in self.windows and not open_multiple:

            # bring the window to the top
            # self.windows[window_id].attributes('-topmost', 1)
            # self.windows[window_id].attributes('-topmost', 0)
            self.windows[window_id].lift()

            # then focus on it
            self.windows[window_id].focus_set()

            # but return false since we're not creating it
            return False

        else:

            # if the window exists, but we want to have multiple instances of it
            # use the current time as a unique suffix to the window_id
            if window_id in self.windows and open_multiple:
                window_id = window_id + "_" + str(time.time())

            # create a new window
            if parent_element is None:
                parent_element = self.root

            self.windows[window_id] = Toplevel(parent_element)

            # bring the transcription window to top
            # self.windows[window_id].attributes('-topmost', 'true')

            # set the window title
            self.windows[window_id].title(title)

            # is it resizable?
            if not resizable:
                self.windows[window_id].resizable(False, False)

            # use the default destroy_window function in case something else wasn't passed
            if close_action is None:
                close_action = lambda: self.destroy_window_(self.windows, window_id)

            # what happens when the user closes this window
            self.windows[window_id].protocol("WM_DELETE_WINDOW", close_action)

            # return the window_id or the window object
            if return_window:
                return self.windows[window_id]
            else:
                return window_id

    def hide_main_window_frame(self, frame_name):
        '''
        Used to hide main window frames, but only if they're not invisible already
        :param frame_name:
        :return:
        '''

        # only attempt to remove the frame from the main window if it's known to be visible
        if frame_name in self.main_window_visible_frames:
            # first remove it from the view
            self.main_window.__dict__[frame_name].pack_forget()

            # then remove if from the visible frames list
            self.main_window_visible_frames.remove(frame_name)

            return True

        return False

    def show_main_window_frame(self, frame_name):
        '''
        Used to show main window frames, but only if they're not visible already
        :param frame_name:
        :return:
        '''

        # only attempt to show the frame from the main window if it's known not to be visible
        if frame_name not in self.main_window_visible_frames:
            # first show it
            self.main_window.__dict__[frame_name].pack()

            # then add it to the visible frames list
            self.main_window_visible_frames.append(frame_name)

            return True

        return False

    def update_main_window(self):
        '''
        Updates the main window GUI
        :return:
        '''

        # handle resolve related UI stuff
        global resolve

        # if resolve isn't connected or if there's a communication error
        if resolve is None:
            # hide resolve related buttons
            self.hide_main_window_frame('resolve_buttons_frame')

            # update the names of the transcribe buttons
            self.main_window.button5.config(text='Transcribe\nAudio')
            self.main_window.button6.config(text='Translate\nAudio to English')

            # if resolve is connected and the resolve buttons are not visible
        else:
            # show resolve buttons
            if self.show_main_window_frame('resolve_buttons_frame'):
                # but hide other buttons so we can place them back below the resolve buttons frame
                self.hide_main_window_frame('other_buttons_frame')

            # update the names of the transcribe buttons
            self.main_window.button5.config(text='Transcribe\nTimeline')
            self.main_window.button6.config(text='Translate\nTimeline to English')

        # now show the other buttons too if they're not visible already
        self.show_main_window_frame('other_buttons_frame')
        self.show_main_window_frame('footer_frame')

        return

    def create_main_window(self):
        '''
        Creates the main GUI window using Tkinter
        :return:
        '''

        # any frames stored here in the future will be considered visible
        self.main_window_visible_frames = []

        # retrieve toolkit_ops object
        toolkit_ops_obj = self.toolkit_ops_obj

        # set the window size
        # self.root.geometry("350x440")

        # create the frame that will hold the resolve buttons
        self.main_window.resolve_buttons_frame = tk.Frame(self.root)

        # create the frame that will hold the other buttons
        self.main_window.other_buttons_frame = tk.Frame(self.root)

        # add footer frame
        self.main_window.footer_frame = tk.Frame(self.root)

        # draw buttons

        # label1 = tk.Label(frame, text="Resolve Operations", anchor='w')
        # label1.grid(row=0, column=1, sticky='w', padx=10, pady=10)

        # resolve buttons frame row 1
        self.main_window.button1 = tk.Button(self.main_window.resolve_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size,
                                             text="Copy Timeline\nMarkers to Same Clip",
                                             command=lambda: self.toolkit_ops_obj.execute_operation('copy_markers_timeline_to_clip', self))
        self.main_window.button1.grid(row=1, column=1, **self.paddings)

        self.main_window.button2 = tk.Button(self.main_window.resolve_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size,
                                             text="Copy Clip Markers\nto Same Timeline",
                                             command=lambda: self.toolkit_ops_obj.execute_operation('copy_markers_clip_to_timeline', self))
        self.main_window.button2.grid(row=1, column=2, **self.paddings)

        # resolve buttons frame row 2
        self.main_window.button3 = tk.Button(self.main_window.resolve_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size, text="Render Markers\nto Stills",
                                             command=lambda: self.toolkit_ops_obj.execute_operation('render_markers_to_stills', self))
        self.main_window.button3.grid(row=2, column=1, **self.paddings)

        self.main_window.button4 = tk.Button(self.main_window.resolve_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size, text="Render Markers\nto Clips",
                                             command=lambda: self.toolkit_ops_obj.execute_operation('render_markers_to_clips', self))
        self.main_window.button4.grid(row=2, column=2, **self.paddings)

        # Other Frame Row 1
        self.main_window.button5 = tk.Button(self.main_window.other_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size, text="Transcribe\nTimeline",
                                             command=lambda: self.toolkit_ops_obj.prepare_transcription_file(
                                                 toolkit_UI_obj=self))
        # add the shift+click binding to the button
        self.main_window.button5.bind('<Shift-Button-1>',
                                      lambda event: toolkit_ops_obj.prepare_transcription_file(
                                                 toolkit_UI_obj=self, select_files=True))
        self.main_window.button5.grid(row=1, column=1, **self.paddings)

        self.main_window.button6 = tk.Button(self.main_window.other_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size,
                                             text="Translate\nTimeline to English",
                                             command=lambda: self.toolkit_ops_obj.prepare_transcription_file(
                                                 toolkit_UI_obj=self, task='translate'))
        # add the shift+click binding to the button
        self.main_window.button6.bind('<Shift-Button-1>',
                                      lambda event: toolkit_ops_obj.prepare_transcription_file(
                                                 toolkit_UI_obj=self, task='translate', select_files=True))

        self.main_window.button6.grid(row=1, column=2, **self.paddings)

        self.main_window.button7 = tk.Button(self.main_window.other_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size,
                                             text="Open\nTranscript", command=lambda: self.open_transcript())
        self.main_window.button7.grid(row=2, column=1, **self.paddings)

        self.main_window.button8 = tk.Button(self.main_window.other_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size,
                                             text="Open\nTranscription Log",
                                             command=lambda: self.open_transcription_log_window())
        self.main_window.button8.grid(row=2, column=2, **self.paddings)

        # THE ADVANCED SEARCH BUTTON
        self.main_window.button9 = tk.Button(self.main_window.other_buttons_frame, **self.blank_img_button_settings,
                                             **self.button_size,
                                             text="Advanced\nTranscript Search", command=lambda:
                                                            self.open_advanced_search_window())
        # add the shift+click binding to the button
        self.main_window.button9.bind('<Shift-Button-1>',
                                      lambda event: self.open_advanced_search_window(select_dir=True))

        self.main_window.button9.grid(row=3, column=1, **self.paddings)


        # self.main_window.link2 = Label(self.main_window.footer_frame, text="made by mots", font=("Courier", 10), cursor="hand2", anchor='s')
        # self.main_window.link2.grid(row=1, column=1, columnspan=1, padx=10, pady=5, sticky='s')
        # self.main_window.link2.bind("<Button-1>", lambda e: webbrowser.open_new("https://mots.us"))

        # self.main_window.link2 = Label(self.main_window.footer_frame, text="StoryToolkitAI home", font=("Courier", 10), cursor="hand2", anchor='s')
        # self.main_window.link2.grid(row=1, column=2, columnspan=1, padx=10, pady=5, sticky='s')
        # self.main_window.link2.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/octimot/StoryToolkitAI"))

        # Other Frame row 2 (disabled for now)
        # self.main_window.button7 = tk.Button(self.main_window.other_buttons_frame, **self.blank_img_button_settings, **self.button_size, text="Transcribe\nDuration Markers")
        # self.main_window.button7.grid(row=4, column=1, **self.paddings)
        # self.main_window.button8 = tk.Button(self.main_window.other_buttons_frame, **self.blank_img_button_settings, **self.button_size, text="Translate\nDuration Markers to English")
        # self.main_window.button8.grid(row=4, column=1, **self.paddings)

        # self.main_window.button_test = tk.Button(self.main_window.other_buttons_frame, **self.blank_img_button_settings, **self.button_size, text="Test",
        #                        command=lambda: self.open_transcription_window())
        # self.main_window.button_test.grid(row=5, column=2, **self.paddings)

        # Make the window resizable false
        self.root.resizable(False, False)

        # update the window after it's been created
        self.root.after(500, self.update_main_window())

        logger.info("Starting StoryToolkitAI GUI")

        # load menubar items
        self.UI_menus.load_menubar()

        # load Tk mainloop
        self.root.mainloop()

        return

    def open_transcription_settings_window(self, title="Transcription Settings",
                                           audio_file_path=None, name=None, task=None, unique_id=None,
                                           transcription_file_path=False, time_intervals=None,
                                           excluded_time_intervals=None):

        if self.toolkit_ops_obj is None or audio_file_path is None or unique_id is None:
            logger.error('Aborting. Unable to open transcription settings window.')
            return False

        # assign a unique_id for this window depending on the queue unique_id
        ts_window_id = 'ts-' + unique_id

        # what happens when the window is closed
        close_action = lambda ts_window_id=ts_window_id, unique_id=unique_id: \
            self.destroy_transcription_settings_window(ts_window_id, unique_id)

        # create a window for the transcription settings if one doesn't already exist
        if self.create_or_open_window(parent_element=self.root, window_id=ts_window_id, title=title,
                                       resizable=True, close_action=close_action):

            self.toolkit_ops_obj.update_transcription_log(unique_id=unique_id, **{'status': 'waiting user'})

            # place the window on top for a moment so that the user sees that he has to interact
            self.windows[ts_window_id].wm_attributes('-topmost', True)
            self.windows[ts_window_id].wm_attributes('-topmost', False)
            self.windows[ts_window_id].lift()

            ts_form_frame = tk.Frame(self.windows[ts_window_id])
            ts_form_frame.pack()

            # File items start here

            # TRANSCRIPTION FILE PATH (hidden) - for re-transcriptions only
            if transcription_file_path:
                transcription_file_path_var = StringVar(ts_form_frame, str(transcription_file_path))
            else:
                transcription_file_path_var = StringVar(ts_form_frame, '')

            # NAME INPUT
            Label(ts_form_frame, text="Name", **self.label_settings).grid(row=1, column=1,
                                                                          **self.input_grid_settings,
                                                                          **self.form_paddings)
            name_var = StringVar(ts_form_frame)
            name_input = Entry(ts_form_frame, textvariable=name_var, **self.entry_settings)
            name_input.grid(row=1, column=2, **self.input_grid_settings, **self.form_paddings)
            name_input.insert(0, name)

            # FILE INPUT (disabled)
            Label(ts_form_frame, text="File", **self.label_settings).grid(row=2, column=1,
                                                                          **self.input_grid_settings,
                                                                          **self.form_paddings)

            file_path_var = StringVar(ts_form_frame)
            file_path_input = Entry(ts_form_frame, textvariable=file_path_var, **self.entry_settings)
            file_path_input.grid(row=2, column=2, **self.input_grid_settings, **self.form_paddings)
            file_path_input.insert(END, os.path.basename(audio_file_path))
            file_path_input.config(state=DISABLED)

            # SOURCE LANGUAGE INPUT
            Label(ts_form_frame, text="Source Language", **self.label_settings).grid(row=3, column=1,
                                                                                     **self.input_grid_settings,
                                                                                     **self.form_paddings)

            # try to get the languages from tokenizer
            available_languages = self.toolkit_ops_obj.get_whisper_available_languages()

            default_language = self.stAI.get_app_setting('transcription_default_language', default_if_none='')

            language_var = StringVar(ts_form_frame, default_language)
            available_languages = sorted(available_languages)
            language_input = OptionMenu(ts_form_frame, language_var, *available_languages)
            language_input.grid(row=3, column=2, **self.input_grid_settings, **self.form_paddings)

            # TASK DROPDOWN

            # hold the selected task in this variable
            Label(ts_form_frame, text="Task", **self.label_settings).grid(row=4, column=1,
                                                                          **self.input_grid_settings,
                                                                          **self.form_paddings)

            if task is None:
                task = 'transcribe'

            task_var = StringVar(ts_form_frame, value=task)
            available_tasks = ['transcribe', 'translate', 'transcribe+translate']
            task_input = OptionMenu(ts_form_frame, task_var, *available_tasks)
            task_input.grid(row=4, column=2, **self.input_grid_settings, **self.form_paddings)

            # MODEL DROPDOWN
            # as options, use the list of whisper.avialable_models()
            # the selected value will be the whisper_model_name app setting
            Label(ts_form_frame, text="Transcription Model", **self.label_settings).grid(row=5, column=1,
                                                                                         **self.input_grid_settings,
                                                                                         **self.form_paddings)

            model_selected = self.stAI.get_app_setting('whisper_model_name', default_if_none='medium')
            model_var = StringVar(ts_form_frame, model_selected)
            model_input = OptionMenu(ts_form_frame, model_var, *whisper.available_models())
            model_input.grid(row=5, column=2, **self.input_grid_settings, **self.form_paddings)

            # DEVICE DROPDOWN
            Label(ts_form_frame, text="Device", **self.label_settings).grid(row=6, column=1,
                                                                            **self.input_grid_settings,
                                                                            **self.form_paddings)

            available_devices = self.toolkit_ops_obj.get_torch_available_devices()

            # the default selected value will be the whisper_device app setting
            device_selected = self.stAI.get_app_setting('whisper_device', default_if_none='auto')
            device_var = StringVar(ts_form_frame, value=device_selected)

            device_input = OptionMenu(ts_form_frame, device_var, *available_devices)
            device_input.grid(row=6, column=2, **self.input_grid_settings, **self.form_paddings)

            # INITIAL PROMPT INPUT
            Label(ts_form_frame, text="Initial Prompt", **self.label_settings).grid(row=7, column=1,
                                                                            sticky='nw',
                                                                          #**self.input_grid_settings,
                                                                          **self.form_paddings)
            # prompt_var = StringVar(ts_form_frame)
            prompt_input = Text(ts_form_frame, wrap=tk.WORD, height=4, **self.entry_settings)
            prompt_input.grid(row=7, column=2, **self.input_grid_settings, **self.form_paddings)
            prompt_input.insert(END, " - How are you?\n - I'm fine, thank you.")

            # TIME INTERVALS INPUT
            Label(ts_form_frame, text="Time Intervals", **self.label_settings).grid(row=8, column=1,
                                                                            sticky='nw',
                                                                          #**self.input_grid_settings,
                                                                          **self.form_paddings)

            time_intervals_input = Text(ts_form_frame, wrap=tk.WORD, height=4, **self.entry_settings)
            time_intervals_input.grid(row=8, column=2, **self.input_grid_settings, **self.form_paddings)
            time_intervals_input.insert(END, str(time_intervals) if time_intervals is not None else '')

            # EXCLUDE TIME INTERVALS INPUT
            Label(ts_form_frame, text="Exclude Time Intervals", **self.label_settings).grid(row=9, column=1,
                                                                            sticky='nw',
                                                                          #**self.input_grid_settings,
                                                                          **self.form_paddings)

            excluded_time_intervals_input = Text(ts_form_frame, wrap=tk.WORD, height=4, **self.entry_settings)
            excluded_time_intervals_input.grid(row=9, column=2, **self.input_grid_settings, **self.form_paddings)
            excluded_time_intervals_input.insert(END,
                                                str(excluded_time_intervals) \
                                                    if excluded_time_intervals is not None else '')

            # START BUTTON

            # add all the settings entered by the use into a nice dictionary
            # transcription_config = dict(name=name_input.get(), language='English', beam_size=5, best_of=5)

            Label(ts_form_frame, text="", **self.label_settings).grid(row=10, column=1,
                                                                      **self.input_grid_settings, **self.paddings)
            start_button = Button(ts_form_frame, text='Start')
            start_button.grid(row=10, column=2, **self.input_grid_settings, **self.paddings)
            start_button.config(command=lambda audio_file_path=audio_file_path,
                                               transcription_file_path_var=transcription_file_path_var,
                                               unique_id=unique_id,
                                               ts_window_id=ts_window_id:
            self.start_transcription_button(ts_window_id,
                                            audio_file_path=audio_file_path,
                                            unique_id=unique_id,
                                            language=language_var.get(),
                                            task=task_var.get(),
                                            name=name_var.get(),
                                            model=model_var.get(),
                                            device=device_var.get(),
                                            initial_prompt=prompt_input.get(1.0, END),
                                            time_intervals=time_intervals_input.get(1.0, END),
                                            excluded_time_intervals=excluded_time_intervals_input.get(1.0, END),
                                            transcription_file_path=transcription_file_path_var.get()
                                            )
                                )

    def convert_text_to_time_intervals(self, text):
        time_intervals = []

        # split the text into lines
        lines = text.splitlines()

        # for each line
        for line in lines:
            # split the line into two parts, separated by a dash
            parts = line.split('-')

            # if there are two parts
            if len(parts) == 2:
                # remove any spaces
                start = parts[0].strip()
                end = parts[1].strip()

                # convert the start and end times to seconds
                start_seconds = self.convert_time_to_seconds(start)
                end_seconds = self.convert_time_to_seconds(end)

                # if both start and end times are valid
                if start_seconds is not None and end_seconds is not None:
                    # add the time interval to the list
                    time_intervals.append([start_seconds, end_seconds])

                else:
                    # otherwise, show an error message
                    messagebox.showerror("Error", "Invalid time interval: " + line)
                    return False

        if time_intervals == []:
            return True

        return time_intervals

    def convert_time_to_seconds(self, time, fps=None):

        # the text is a string with lines like this:
        # 0:00:00:00 - 0:00:00:00
        # or like this:
        # 0:00:00.000 - 0:00:01.000
        # or like this:
        # 0,0 - 0,01
        # or like this:
        # 0.0 - 0.01

        # if the format is 0:00:00.000 or 0:00:00:00
        if ':' in time:

            time_array = time.split(':')

            # if the format is 0:00:00:00 - assume a timecode was passed
            if len(time_array) == 4:

                if fps is not None:
                    # if the format is 0:00:00:00
                    # convert the time to seconds
                    return int(time_array[0]) * 3600 + int(time_array[1]) * 60 + int(time_array[2]) + \
                           int(time_array[3]) / fps

                else:
                    logger.error('The time format is 0:00:00:00, but the fps is not specified.')

            elif len(time_array) == 3:
                # hours, minutes, seconds
                return int(time_array[0]) * 3600 + int(time_array[1]) * 60 + float(time_array[2])

            elif len(time_array) == 2:
                # minutes, seconds
                return int(time_array[0]) * 60 + float(time_array[1])

            elif len(time_array) == 1:
                # seconds
                return float(time_array[0])

            else:
                return 0

        # if the format is 0,0
        elif ',' in time:
            return float(time.replace(',', '.'))

        # if the format is 0.0
        elif '.' in time:
            return float(time)

        elif time.isnumeric():
            return int(time)

        else:
            logger.error('The time format is not recognized.')
            return None

    def start_transcription_button(self, transcription_settings_window_id=None, **transcription_config):
        '''
        This sends the transcription to the transcription queue via toolkit_ops object,
        but also closes the trancription window forever
        :param transcription_settings_window_id:
        :param transcription_config:
        :return:
        '''

        # validate the transcription settings
        transcription_config['time_intervals'] = \
            self.convert_text_to_time_intervals(transcription_config['time_intervals'])

        if not transcription_config['time_intervals']:
            return False

        # validate the transcription settings
        transcription_config['excluded_time_intervals'] = \
            self.convert_text_to_time_intervals(transcription_config['excluded_time_intervals'])

        if not transcription_config['excluded_time_intervals']:
            return False

        # send transcription to queue
        self.toolkit_ops_obj.add_to_transcription_queue(**transcription_config)

        # destroy transcription config window
        self.destroy_window_(self.windows, window_id=transcription_settings_window_id)

    def destroy_transcription_settings_window(self, window_id, unique_id, parent_element=None):

        if (messagebox.askyesno(title="Cancel Transcription",
                                message='Are you sure you want to cancel this transcription?')):

            # assume the window is references in the windows dict
            if parent_element is None:
                parent_element = self.windows

            self.toolkit_ops_obj.update_transcription_log(unique_id=unique_id, status='canceled')

            # call the default destroy window function
            self.destroy_window_(parent_element=self.windows, window_id=window_id)

        return False

    def destroy_transcription_window(self, window_id):

        # destroy the associated search window (if it exists)
        # - in the future, if were to have multiple search windows, we will need to do it differently
        if window_id+'_search' in self.windows:
            self.destroy_window_(self.windows, window_id=window_id + '_search')

        # also destroy the associated groups window (if it exists)
        # - in the future, if were to have multiple search windows, we will need to do it differently
        if window_id+'_transcript_groups' in self.windows:
            self.destroy_transcript_groups_window(window_id=window_id + '_transcript_groups')

        # remove the transcription segments from the transcription_segments dict
        if window_id in self.t_edit_obj.transcript_segments:
            del self.t_edit_obj.transcript_segments[window_id]

        # remove all the ids from the transcription_segments dict
        if window_id in self.t_edit_obj.transcript_segments_ids:
            del self.t_edit_obj.transcript_segments_ids[window_id]

        # call the default destroy window function
        self.destroy_window_(parent_element=self.windows, window_id=window_id)

    def destroy_window_(self, parent_element, window_id):
        '''
        This makes sure that the window reference is deleted when a user closes a window
        :param parent_element:
        :param window_id:
        :return:
        '''
        # first destroy the window
        parent_element[window_id].destroy()

        logger.debug('Closing window: ' + window_id)

        # then remove its reference
        del parent_element[window_id]

    def open_transcript(self, **options):
        '''
        This prompts the user to open a transcript file and then opens it a transcript window
        :return:
        '''

        # did we ever save a target dir for this project?
        last_target_dir = None
        if resolve and current_project is not None:
            last_target_dir = self.stAI.get_project_setting(project_name=current_project, setting_key='last_target_dir')

        # ask user which transcript to open
        transcription_json_file_path = self.ask_for_target_file(filetypes=[("Json files", "json srt")],
                                                                target_dir=last_target_dir)

        # abort if user cancels
        if not transcription_json_file_path:
            return False


        # if resolve is connected, save the directory where the file is as a last last target dir
        if resolve and transcription_json_file_path and os.path.exists(transcription_json_file_path):
            self.stAI.save_project_setting(project_name=current_project,
                                           setting_key='last_target_dir',
                                           setting_value=os.path.dirname(transcription_json_file_path))

        # if this is an srt file, but a .transcription.json file exists in the same directory,
        # ask the user if they want to open the .transcription.json file instead
        if transcription_json_file_path.endswith('.srt') \
            and os.path.exists(transcription_json_file_path.replace('.srt', '.transcription.json')):

            # ask user
            if messagebox.askyesno(title="Open Transcript",
                                   message='The file you selected is an SRT file, '
                                           'but a transcription.json file with the exact name '
                                           'exists in the same directory.\n\n'
                                           'Do you want to open the transcription.json file instead?'
                                           '\n\n'
                                           'If you answer NO, the transcription.json will be '
                                           'overwritten with the content of the SRT file.'
                                           ''):

                # change the file path
                transcription_json_file_path = transcription_json_file_path.replace('.srt', '.transcription.json')

        # if this is an srt file, ask the user if they want to convert it to json
        if transcription_json_file_path.endswith('.srt'):

            convert_from_srt = messagebox.askyesno(title="Convert SRT?",
                                                   message='Do you want to convert this SRT file '
                                                           'to a transcription file?')

            # if the user wants to convert the srt file to json
            if convert_from_srt:

                # convert the srt file to json
                # (it will overwrite any existing transcription.json with the same name in the same directory)
                transcription_json_file_path \
                    = self.toolkit_ops_obj.convert_srt_to_transcription_json(
                                                        srt_file_path=transcription_json_file_path,
                                                        overwrite=True
                                                        )

        # if the file is not a json file, abort
        if not transcription_json_file_path.endswith('.json'):
            self.notify_via_messagebox(title='Not a transcription',
                                            message='The file \n{}\nis not a transcription file.'
                                                        .format(os.path.basename(transcription_json_file_path)),
                                            message_log='The file {} is not a transcription file.',
                                            type='error')
            return False

        # open the transcript in a transcript window


        # why not open the transcript in a transcription window?
        self.open_transcription_window(transcription_file_path=transcription_json_file_path, **options)

    def open_transcription_window(self, title=None, transcription_file_path=None, srt_file_path=None,
                                  select_line_no=None, add_to_selection=None):

        if self.toolkit_ops_obj is None:
            logger.error('Cannot open transcription window. A toolkit operations object is needed to continue.')
            return False

        # Note: most of the transcription window functions are stored in the TranscriptEdit class

        # only continue if the transcription path was passed and the file exists
        if transcription_file_path is None or os.path.exists(transcription_file_path) is False:
            logger.error('The transcription file {} cannot be found.'.format(transcription_file_path))
            return False

        # now read the transcription file contents
        transcription_json = \
            self.toolkit_ops_obj.get_transcription_file_data(transcription_file_path=transcription_file_path)

        # if no srt_file_path was passed
        if srt_file_path is None:

            # try to use the file path in the transcription json
            if 'srt_file_path' in transcription_json:
                srt_file_path = transcription_json['srt_file_path']

        # try to see if we have a srt path or not
        if srt_file_path is not None:

            # if not we're dealing with an absolute path
            if not os.path.isabs(srt_file_path):
                # assume that the srt is in the same directory as the transcription
                srt_file_path = os.path.join(os.path.dirname(transcription_file_path), srt_file_path)

        # hash the url and use it as a unique id for the transcription window
        t_window_id = hashlib.md5(transcription_file_path.encode('utf-8')).hexdigest()

        # use the transcription file name without the extension as a window title if a title wasn't passed
        if title is None:

            # use the name in the transcription json for the window title
            if 'name' in transcription_json:
                title = transcription_json['name']
            # if there is no name in the transcription json, simply use the name of the file
            else:
                title = os.path.splitext(os.path.basename(transcription_file_path))[0]

        # ask user if they want to add timeline info to the transcription file (if they were not recorded)
        # (but only if ask_for_timeline_info is True in the app settings)
        # if self.stAI.get_app_setting(setting_name='ask_for_timeline_info', default_if_none=False) is True:
        #
        #    # if the transcription file does not containe the timeline fps
        #    if 'timeline_fps' not in transcription_json:
        #         # ask the user if they want to add timeline info to the transcription file
        #         if timeline_fps := simpledialog.askstring(title='Add fps to transcription data?',
        #                                   prompt="The transcription file does not contain timeline fps info.\n"
        #                                          "If you want to add it, please enter the fps value here.\n"
        #                                   ):
        #             print(timeline_fps)


        # create a window for the transcript if one doesn't already exist
        if self.create_or_open_window(parent_element=self.root, window_id=t_window_id, title=title, resizable=True,
                                       close_action=lambda t_window_id=t_window_id: \
                                            self.destroy_transcription_window(t_window_id)
                                       ):

            # add the path to the transcription_file_paths dict in case we need it later
            self.t_edit_obj.transcription_file_paths[t_window_id] = transcription_file_path

            # initialize the transcript_segments_ids for this window
            self.t_edit_obj.transcript_segments_ids[t_window_id] = {}

            # add the transcript groups to the transcript_groups dict
            if 'transcript_groups' in transcription_json:

                self.t_edit_obj.transcript_groups[t_window_id] = transcription_json['transcript_groups']

                # if the transcript groups are not empty
                if transcription_json['transcript_groups']:

                    # open the transcript groups window
                    if self.stAI.get_app_setting(setting_name='open_transcript_groups_window_on_open',
                                                 default_if_none=False) is True:
                        self.open_transcript_groups_window(transcription_window_id=t_window_id,
                                                           transcription_name=title)

            else:
                self.t_edit_obj.transcript_groups[t_window_id] = {}

            # create a header frame to hold stuff above the transcript text
            header_frame = tk.Frame(self.windows[t_window_id])
            header_frame.place(anchor='nw', relwidth=1)

            # THE MAIN TEXT ELEMENT
            # create a frame for the text element
            text_form_frame = tk.Frame(self.windows[t_window_id])
            text_form_frame.pack(pady=50, expand=True, fill='both')

            # does the json file actually contain transcript segments generated by whisper?
            if 'segments' in transcription_json:

                # add everything except the segments and the text to the self.t_edit_obj.transcription_data dict
                self.t_edit_obj.transcription_data[t_window_id] = \
                    {k: v for k, v in transcription_json.items() if k != 'segments' and k != 'text'}

                # set up the text element where we'll add the actual transcript
                text = Text(text_form_frame, name='transcript_text',
                            font=(self.transcript_font), width=45, height=30, padx=5, pady=5, wrap=tk.WORD,
                                                    background=self.resolve_theme_colors['black'],
                                                    foreground=self.resolve_theme_colors['normal'])

                # add a scrollbar to the text element
                scrollbar = Scrollbar(text_form_frame, orient="vertical", **self.scrollbar_settings)
                scrollbar.config(command=text.yview)
                scrollbar.pack(side=tk.RIGHT, fill='y', pady=5)

                # configure the text element to use the scrollbar
                text.config(yscrollcommand=scrollbar.set)

                # we'll need to count segments soon
                segment_count = 0

                # use this to calculate the longest segment (but don't accept anything under 30)
                longest_segment_num_char = 40

                # initialize the segments list for later use
                # this should contain all the segments in the order they appear
                self.t_edit_obj.transcript_segments[t_window_id] = []

                # initialize line numbers
                line = 0

                # take each transcript segment
                for t_segment in transcription_json['segments']:

                    # start counting the lines
                    line = line+1

                    # add a reference for its id
                    if 'id' in t_segment:
                        self.t_edit_obj.transcript_segments_ids[t_window_id][line] = t_segment['id']
                    # throw an error otherwise, it might be a problem on the long run
                    else:
                        logger.error('Line {} in {} doesn\'t have an id.'.format(line, transcription_file_path))

                    # if there is a text element, simply insert it in the window
                    if 'text' in t_segment:

                        # count the segments
                        segment_count = segment_count + 1

                        # add the current segment to the segments list
                        self.t_edit_obj.transcript_segments[t_window_id].append(t_segment)

                        # get the text index before inserting the new segment
                        # (where the segment will start)
                        new_segment_start = text.index(INSERT)

                        # insert the text
                        text.insert(END, t_segment['text'].strip() + ' ')

                        # if this is the longest segment, keep that in mind
                        if len(t_segment['text']) > longest_segment_num_char:
                            longest_segment_num_char = len(t_segment['text'])

                        # get the text index of the last character of the new segment
                        new_segment_end = text.index("end-1c")

                        # keep in mind the segment start and end times of each segment
                        segment_start_time = t_segment['start']
                        end_start_time = t_segment['start']

                        # this works if we're aiming to move away from line based start_end times
                        #tag_id = 'segment-' + str(segment_count)
                        #text.tag_add(tag_id, new_segment_start, new_segment_end)
                        #text.tag_config(tag_id)
                        #text.tag_bind(tag_id, "<Button-1>", lambda e,
                        #                                           segment_start_time=segment_start_time:
                        #                            toolkit_ops_obj.go_to_time(segment_start_time))

                        # bind CMD/CTRL+click events to the text:
                        # on click, select text
                        # text.tag_bind(tag_id, "<"+self.ctrl_cmd_bind+"-Button-1>", lambda e, line_id=line_id,t_window_id=t_window_id:
                        #    self.t_edit_obj.select_text_lines(event=e, text_element=text,
                        #                                      window_id=t_window_id, line_id=line_id)
                        #              )

                        # for now, just add 2 new lines after each segment:
                        text.insert(END, '\n')

                # make the text read only
                # and take into consideration the longest segment to adjust the width of the window
                if longest_segment_num_char > 60:
                    longest_segment_num_char = 60
                text.config(state=DISABLED, width=longest_segment_num_char)

                # add undo/redo
                # this will not work for splitting/merging lines
                # text.config(undo=True)

                # set the top, in-between and bottom text spacing
                text.config(spacing1=0, spacing2=0.2, spacing3=5)

                # then show the text element
                text.pack(anchor='w', expand=True, fill='both')

                # create a footer frame that holds stuff on the bottom of the transcript window
                footer_frame = tk.Frame(self.windows[t_window_id])
                footer_frame.place(relwidth=1, anchor='sw', rely=1)

                # add a status label to print out current transcription status
                status_label = Label(footer_frame, text="", anchor='w', foreground=self.resolve_theme_colors['normal'])
                status_label.pack(side=tk.LEFT, **self.paddings)


                # bind shift click events to the text
                # text.bind("<Shift-Button-1>", lambda e:
                #         self.t_edit_obj.select_text_lines(event=e, text_element=text, window_id=t_window_id))

                select_options = {'window_id': t_window_id, 'text_element': text, 'status_label': status_label}

                # bind all key presses to transcription window actions
                self.windows[t_window_id].bind("<KeyPress>",
                                               lambda e:
                                               self.t_edit_obj.transcription_window_keypress(event=e,
                                                                                             **select_options))

                # bind CMD/CTRL + key presses to transcription window actions
                self.windows[t_window_id].bind("<" + self.ctrl_cmd_bind + "-KeyPress>",
                                               lambda e:
                                               self.t_edit_obj.transcription_window_keypress(event=e, special_key='cmd',
                                                                                             **select_options))

                # bind all mouse clicks on text
                text.bind("<Button-1>", lambda e,
                                               select_options=select_options:
                                                    self.t_edit_obj.transcription_window_mouse(e,
                                                                                               **select_options))

                # bind CMD/CTRL + mouse Clicks to text
                text.bind("<"+self.ctrl_cmd_bind+"-Button-1>",
                          lambda e, select_options=select_options:
                            self.t_edit_obj.transcription_window_mouse(e,
                                                                       special_key='cmd',
                                                                       **select_options))


                # bind ALT/OPT + mouse Click to edit transcript
                text.bind("<"+self.alt_bind+"-Button-1>",
                          lambda e: self.t_edit_obj.edit_transcript(window_id=t_window_id, text=text,
                                                                    status_label=status_label)
                          )

                # bind CMD/CTRL + e to edit transcript
                self.windows[t_window_id].bind("<"+self.ctrl_cmd_bind+"-e>",
                          lambda e: self.t_edit_obj.edit_transcript(window_id=t_window_id, text=text,
                                                                    status_label=status_label)
                          )

                # bind the FocusOut of the text so that we save the new text when done
                # text.bind("<FocusOut>", lambda e: self.t_edit_obj.save_transcript(window_id=t_window_id, text=text))

                #self.windows[t_window_id].bind("<Shift-Up>", lambda e: self.t_edit_obj.select_text_lines(e, special_key='Shift', **select_options))
                #self.windows[t_window_id].bind("<Shift-Down>", lambda e: self.t_edit_obj.select_text_lines(e, special_key='Shift', **select_options))
                # self.windows[t_window_id].bind("<" + self.ctrl_cmd_bind + "-Up>", lambda e: self.t_edit_obj.select_text_lines(e, special_key=self.ctrl_cmd_bind, **select_options))
                # self.windows[t_window_id].bind("<" + self.ctrl_cmd_bind + "-Down>", lambda e: self.t_edit_obj.select_text_lines(e, special_key=self.ctrl_cmd_bind, **select_options))


                # b_test = tk.Button(footer_frame, text='Search', command=lambda: search(),
                #                font=20, bg='white').grid(row=1, column=3, sticky='w', **self.paddings)

                # THE SEARCH FIELD
                # first the label
                Label(header_frame, text="Find:", anchor='w').pack(side=tk.LEFT, **self.paddings)

                # then the search text entry
                # first the string variable that "monitors" what's being typed in the input
                search_str = tk.StringVar()

                # the search input
                search_input = Entry(header_frame, textvariable=search_str)

                # and a callback for when the search_str is changed
                search_str.trace("w", lambda name, index, mode, search_str=search_str, text=text,
                                             t_window_id=t_window_id:
                self.t_edit_obj.search_text(search_str=search_str,
                                            text_element=text, window_id=t_window_id))

                search_input.pack(side=tk.LEFT, **self.paddings)

                search_input.bind('<Return>', lambda e, text=text, t_window_id=t_window_id:
                                self.t_edit_obj.cycle_through_results(text_element=text, window_id=t_window_id))

                search_input.bind('<FocusIn>', lambda e, t_window_id=t_window_id:
                                            self.t_edit_obj.set_typing_in_window(e, t_window_id, typing=True))
                search_input.bind('<FocusOut>', lambda e, t_window_id=t_window_id:
                                            self.t_edit_obj.set_typing_in_window(e, t_window_id, typing=False))

                # ADVANCED SEARCH
                # this button will open a new window with advanced search options
                advanced_search_button = tk.Button(header_frame, text='Advanced Search', command=lambda:
                                            self.open_advanced_search_window(transcription_window_id=t_window_id,
                                                                             transcription_file_path=\
                                                                                transcription_file_path))

                advanced_search_button.pack(side=tk.LEFT, **self.paddings)


                # KEEP ON TOP BUTTON
                on_top_button = tk.Button(header_frame, text="Keep on top", takefocus=False)
                # add the command function here
                on_top_button.config(command=lambda on_top_button=on_top_button, t_window_id=t_window_id:
                                            self.window_on_top_button(button=on_top_button, window_id=t_window_id)
                                                                 )
                on_top_button.pack(side=tk.RIGHT, **self.paddings, anchor='e')

                # keep the transcript window on top or not according to the config
                # and also update the initial text on the respective button
                self.window_on_top_button(button=on_top_button,
                                          window_id=t_window_id,
                                          on_top=stAI.get_app_setting('transcripts_always_on_top',
                                                                      default_if_none=False)
                                          )

                # IMPORT SRT BUTTON
                if srt_file_path:
                    import_srt_button = tk.Button(footer_frame,
                                                  text="Import SRT into Bin",
                                                  takefocus=False,
                                                  command=lambda:
                                                    self.toolkit_ops_obj.resolve_api.import_media(srt_file_path)
                                                  )
                    import_srt_button.pack(side=tk.RIGHT, **self.paddings, anchor='e')


                # SYNC BUTTON

                sync_button = tk.Button(header_frame, takefocus=False)
                sync_button.config(command=lambda sync_button=sync_button, window_id=t_window_id:
                                                self.t_edit_obj.sync_with_playhead_button(
                                                    button=sync_button,
                                                    window_id=t_window_id)
                                                                   )

                # LINK TO TIMELINE BUTTON

                # is this transcript linked to the current timeline?
                global current_timeline
                global current_project

                # prepare an empty link button for now, and only show it when/if resolve starts
                link_button = tk.Button(footer_frame)
                link_button.config(command=lambda link_button=link_button,
                                                  transcription_file_path=transcription_file_path:
                                            self.t_edit_obj.link_to_timeline_button(
                                                button=link_button,
                                                transcription_file_path=transcription_file_path)
                                                               )

                # RE-TRANSCRIBE BUTTON

                # only show this button if we have the original audio file path
                # if 'audio_file_path' in transcription_json:
                #
                #     audio_file_path = transcription_json['audio_file_path']
                #
                #     print(audio_file_path)
                #     print(os.path.join(os.path.dirname(transcription_file_path), audio_file_path))
                #
                #
                #     # but that file is usually stored next to the transcription file
                #     # so check if the audio file is in the same directory as the transcription file
                #     if os.path.exists(os.path.join(os.path.dirname(transcription_file_path), audio_file_path)) :
                #
                #         transcribe_button = tk.Button(footer_frame, text="Re-Transcribe",)
                #         transcribe_button.config(command=lambda audio_file_path=audio_file_path,title=title:
                #                                         self.open_transcription_settings_window(
                #                                             audio_file_path=audio_file_path,
                #                                             name=title
                #                                         )
                #                        )
                #         transcribe_button.pack(side=tk.LEFT, **self.paddings, anchor='e')

                # MARK IN BUTTON
                # mark_in_button = Button(footer_frame, text='Mark In')
                # mark_in_button.pack(side=tk.LEFT, **self.paddings)
                # mark_in_button.config(command= lambda text=text, t_window_id=t_window_id:
                #                  self.toolkit_ops_obj.mark_in(window_id=t_window_id))

                # MARK OUT BUTTON
                # mark_out_button = Button(footer_frame, text='Mark Out')
                # mark_out_button.pack(side=tk.LEFT, **self.paddings)
                # mark_out_button.config(command= lambda text=text, t_window_id=t_window_id:
                #                  self.toolkit_ops_obj.mark_out(window_id=t_window_id))

                # prepare a label to use to send errors to the user
                # error_label = Label(footer_frame, text="", anchor='w').grid(row=2, column=1, sticky='w', **self.paddings)

                # start the transcription window self-updating process
                # here we send the update transcription window function a few items that need to be updated
                self.windows[t_window_id].after(500, lambda link_button=link_button,
                                                            t_window_id=t_window_id,
                                                            transcription_file_path=transcription_file_path:
                    self.update_transcription_window(window_id=t_window_id,
                                                     link_button=link_button,
                                                     sync_button=sync_button,
                                                     transcription_file_path=transcription_file_path,
                                                     text=text)
                                                )

            # if no transcript was found in the json file, alert the user
            else:
                not_a_transcription_message = 'The file {} isn\'t a transcript.'.format(
                    os.path.basename(transcription_file_path))

                self.notify_via_messagebox(title='Not a transcript file',
                                           message=not_a_transcription_message,
                                           type='warning'
                                           )
                self.destroy_window_(self.windows, t_window_id)

        # if select_line_no was passed
        if select_line_no is not None:
            # select the line in the text widget
            self.t_edit_obj.set_active_segment(window_id=t_window_id, line=select_line_no)

        # if add_to_selection was passed
        if add_to_selection is not None and add_to_selection and type(add_to_selection) is list:

            # go through all the add_to_selection items
            for selection_line_no in add_to_selection:
                # and add them to the selection

                # select the line in the text widget
                self.t_edit_obj.segment_to_selection(window_id=t_window_id, line=selection_line_no)

    def update_transcription_window(self, window_id, **update_attr):
        '''
        Auto-updates a transcription window and then calls itself again after a few seconds.
        :param window_id:
        :param update_attr:
        :return:
        '''

        # check if the current timeline is still linked to this transcription window
        global current_timeline
        global current_project
        global resolve
        global current_tc
        global current_timeline_fps

        # only check if resolve is connected
        if resolve and current_timeline is not None:

            # is there a link between the transcription and the resolve timeline?
            link, _ = self.toolkit_ops_obj.get_transcription_to_timeline_link(
                transcription_file_path=update_attr['transcription_file_path'],
                timeline_name=current_timeline['name'],
                project_name=current_project)

            # update the link button text if it was passed in the call
            if 'link_button' in update_attr:

                # the link button text depends on the above link
                if link:
                    link_button_text = 'Unlink from Timeline'
                    # update_attr['error_label'].config(text='')
                else:
                    link_button_text = 'Link to Timeline'

                    # if there's no link, let the user know
                    # update_attr['error_label'].config(text='Timeline mismatch')

                # update the link button on the transcription window
                update_attr['link_button'].config(text=link_button_text)
                update_attr['link_button'].pack(side=tk.RIGHT, **self.paddings, anchor='e')

            if window_id not in self.t_edit_obj.sync_with_playhead:
                self.t_edit_obj.sync_with_playhead[window_id] = False

            # update the sync button if it was passed in the call
            if 'sync_button' in update_attr:
                if self.t_edit_obj.sync_with_playhead[window_id]:
                    sync_button_text = "Don't sync"
                else:
                    sync_button_text = "Sync"

                # update the link button on the transcription window
                update_attr['sync_button'].config(text=sync_button_text)
                update_attr['sync_button'].pack(side=tk.RIGHT, **self.paddings, anchor='e')

            # how many segments / lines does the transcript on this window contain?
            max_lines = len(self.t_edit_obj.transcript_segments[window_id])

            # create the current_window_tc reference if it doesn't exist
            if window_id not in self.t_edit_obj.current_window_tc:
                self.t_edit_obj.current_window_tc[window_id] = ''

            # HOW WE CONVERT THE RESOLVE PLAYHEAD TIMECODE TO TRANSCRIPT LINES

            # only do this if the sync is on for this window
            # and if the timecode in resolve has changed compared to last time
            if self.t_edit_obj.sync_with_playhead[window_id] \
                and self.t_edit_obj.current_window_tc[window_id] != current_tc:

                # initialize the timecode object for the current_tc
                current_tc_obj = Timecode(current_timeline_fps, current_tc)

                # initialize the timecode object for the timeline start_tc
                timeline_start_tc_obj = Timecode(current_timeline_fps, current_timeline['startTC'])

                # subtract the two timecodes to get the corresponding transcript seconds
                if current_tc_obj > timeline_start_tc_obj:
                    transcript_tc = current_tc_obj - timeline_start_tc_obj

                    # so we can now convert the current tc into seconds
                    transcript_sec = transcript_tc.float

                # but if the current_tc_obj is at 0 or less
                else:
                    transcript_sec = 0

                # remove the current_time segment first
                update_attr['text'].tag_delete('current_time')

                # find out on which text segment we are now
                num = 0
                line = 1
                while num < max_lines:

                    # if the transcript timecode in seconds is between the start and the end of this line
                    if float(self.t_edit_obj.transcript_segments[window_id][num]['start']) <= transcript_sec \
                            < float(self.t_edit_obj.transcript_segments[window_id][num]['end'])-0.01:
                        line = num + 1

                        # set the line as the active segment on the timeline
                        self.t_edit_obj.set_active_segment(window_id, update_attr['text'], line)

                    num = num + 1

                update_attr['text'].tag_config('current_time', foreground=self.resolve_theme_colors['white'])

                # highlight current line on transcript
                # update_attr['text'].tag_add('current_time')

                # now remember that we did the update for the current timecode
                self.t_edit_obj.current_window_tc[window_id] = current_tc


        # hide some stuff if resolve isn't connected
        else:
            update_attr['link_button'].grid_forget()
            update_attr['sync_button'].grid_forget()

        # update again after 500ms
        # @todo remove the auto-update and place the call where is needed to prevent constant redrawing of stuff
        self.windows[window_id].after(500, lambda window_id=window_id, update_attr=update_attr:
                self.update_transcription_window(window_id, **update_attr))

    def close_inactive_transcription_windows(self, timeline_transcription_file_paths=None):
        '''
        Closes all transcription windows that are not in the timeline_transcription_file_paths list
        (or all of them if no list is passed)
        :param timeline_transcription_file_paths: list of transcription file paths
        :return: None
        '''

        # get all transcription windows from the self.t_edit_obj.transcription_file_paths
        transcription_windows = self.t_edit_obj.transcription_file_paths.keys()

        # loop through all transcription windows
        for transcription_window in transcription_windows:

            # if the transcription window is not in the timeline_transcription_file_paths
            if timeline_transcription_file_paths is None \
                or timeline_transcription_file_paths == [] \
                or self.t_edit_obj.transcription_file_paths[transcription_window] \
                    not in timeline_transcription_file_paths:

                # close the window
                self.destroy_window_(self.windows, transcription_window)

    def update_transcription_log_window(self):

        # only do this if the transcription window exists
        # and if the log exists
        if self.toolkit_ops_obj.transcription_log and 't_log' in self.windows:

            # first destroy anything that the window might have held
            list = self.windows['t_log'].winfo_children()
            for l in list:
                l.destroy()

            # create a canvas to hold all the log items in the window
            log_canvas = tk.Canvas(self.windows['t_log'], borderwidth=0)

            # create a frame for the log items
            log_frame = tk.Frame(log_canvas)

            # create a scrollbar to use with the canvas
            scrollbar = Scrollbar(self.windows['t_log'], command=log_canvas.yview, **self.scrollbar_settings)

            # attach the scrollbar to the log_canvas
            log_canvas.config(yscrollcommand=scrollbar.set)

            # add the scrollbar to the window
            scrollbar.pack(side=RIGHT, fill=Y)

            # add the canvas to the window
            log_canvas.pack(side=LEFT, fill=BOTH, expand=True)

            # show the frame in the canvas
            log_canvas.create_window((4,4), window=log_frame, anchor="nw")

            # make scroll region adjust each time the canvas changes in size
            # and also adjust the width according to the frame inside it
            log_frame.bind("<Configure>", lambda event, log_canvas=log_canvas:
                                                log_canvas.configure(scrollregion=log_canvas.bbox("all"),
                                                                     width=event.width
                                                                     ))

            # populate the log frame with the transcription items from the transcription log
            num = 0
            for t_item_id, t_item in self.toolkit_ops_obj.transcription_log.items():

                num = num + 1

                if 'name' not in t_item:
                    t_item['name'] = 'Unknown'

                label_name = Label(log_frame, text=t_item['name'], anchor='w', width=40)
                label_name.grid(row=num, column=1, **self.list_paddings, sticky='w')

                if 'status' not in t_item:
                    t_item['status'] = ''

                label_status = Label(log_frame, text=t_item['status'], anchor='w', width=15)
                label_status.grid(row=num, column=2, **self.list_paddings, sticky='w')

                # make the label clickable as soon as we have a file path for it in the log
                if 'json_file_path' in t_item and t_item['json_file_path'] != '':
                    # first assign variables to pass it easily to lambda
                    json_file_path = t_item['json_file_path']
                    name = t_item['name']

                    # now bind the button event
                    # the lambda needs all this code to "freeze" the current state of the variables
                    # otherwise it's going to only use the last value of the variable in the for loop
                    # for eg. instead of having 3 different value for the variable "name",
                    # lambda will only use the last value in the for loop
                    label_name.bind("<Button-1>",
                                    lambda e,
                                           json_file_path=json_file_path,
                                           name=name:
                                    self.open_transcription_window(title=name,
                                                                   transcription_file_path=json_file_path)
                                    )

    def open_transcription_log_window(self):

        # create a window for the transcription log if one doesn't already exist
        if self.create_or_open_window(parent_element=self.root,
                                        window_id='t_log', title='Transcription Log', resizable=True):
            # and then call the update function to fill the window up
            self.update_transcription_log_window()

            return True

    def open_advanced_search_window(self, transcription_window_id=None, transcription_file_path=None,
                                    select_dir=False):

        if self.toolkit_ops_obj is None:
            logger.error('Cannot open advanced search window. A toolkit operations object is needed to continue.')
            return False

        # declare the empty list of transcription file paths
        transcription_file_paths = []

        # check if a transcription file path was passed and if it exists
        if transcription_file_path is not None and not os.path.exists(transcription_file_path):
            logger.error('The transcription file {} cannot be found.'.format(transcription_file_path))
            return False

        # if a transcription window id was passed, get the transcription file path from it
        elif transcription_file_path is None and transcription_window_id is not None:
            transcription_file_path = self.t_edit_obj.transcription_file_paths[transcription_window_id]


        # if we still don't have a transcription file path (or paths), ask the user to manually select thetranscription files
        if transcription_file_path is None and not transcription_file_paths:
            # use the global initial_target_dir
            # global initial_target_dir

            # if resolve is connected, check the last target dir
            global resolve
            global current_project

            if resolve:
                initial_dir = self.stAI.get_project_setting(project_name=current_project,
                                                            setting_key='last_target_dir')

            else:
                initial_dir = '~'

            # if select_dir is true, allow the user to select a directory
            if select_dir:
                # ask the user to select a directory with transcription files
                transcription_file_dirs = filedialog.askdirectory(initialdir=initial_dir,
                                                                   title='Select a directory with transcriptions')

                # now go through all the .transcription.json files in the directory and add them to the list
                if transcription_file_dirs:
                    for root, dirs, files in os.walk(transcription_file_dirs):
                        for file in files:
                            if file.endswith('.transcription.json'):
                                transcription_file_paths.append(os.path.join(root, file))

            else:
                # ask the user to select the transcription files to use in the search corpus
                transcription_file_paths \
                    = filedialog.askopenfilenames(initialdir=initial_dir,
                                                            title='Select transcription files to use in the search',
                                                            filetypes=[('Transcription files', '*.json')])

            # if resolve is connected, save the last target dir
            if resolve and transcription_file_paths \
                and type(transcription_file_paths) is list and os.path.exists(transcription_file_paths[0]):

                self.stAI.save_project_setting(project_name=current_project,
                                               setting_key='last_target_dir',
                                               setting_value=os.path.dirname(transcription_file_paths[0]))


            if not transcription_file_paths:
                logger.info('No transcription files were selected. Aborting.')
                return False

        # init the search window id, the title and the parent element
        # depending if we have a transcription window id or not
        if transcription_window_id is not None and transcription_file_path is not None:

            # read transcription data from transcription file
            transcription_data = self.toolkit_ops_obj.get_transcription_file_data(transcription_file_path)

            # get the name of the transcription
            if transcription_data and type(transcription_data) is dict and 'name' in transcription_data:
                title_name = transcription_data['name']
            else:
                title_name = os.path.basename(transcription_file_path).split('.transcription.json')[0]

            search_window_id = transcription_window_id + '_search'
            search_window_title = 'Search - {}'.format(title_name)
            search_window_parent = self.windows[transcription_window_id]

            # don't open multiple search widows for the same transcription window
            open_multiple = False

            # the transcription_file_paths has only one element
            transcription_file_paths = [transcription_file_path]

        # if there is no transcription window id
        else:
            search_window_id = 'adv_search'
            search_window_title = 'Search'
            search_window_parent = self.root

            # this allows us to open multiple search windows at the same time
            open_multiple = True

        # create a window for the advanced search if one doesn't already exist
        if (search_window_id := self.create_or_open_window(parent_element=search_window_parent,
                                        window_id=search_window_id, title=search_window_title, resizable=True,
                                        open_multiple=open_multiple)):

            # and then call the update function to fill the window up
            #self.update_advanced_search_window()

            current_search_window = self.windows[search_window_id]

            # create a header frame to hold the search inputs
            header_frame = tk.Frame(current_search_window)
            header_frame.place(anchor='nw', relwidth=1)

            # create a frame for the results elements
            results_form_frame = tk.Frame(current_search_window)
            results_form_frame.pack(pady=50, expand=True, fill='both')

            # THE SEARCH FIELD
            # first the label
            Label(header_frame, text="Search:", anchor='w').pack(side=tk.LEFT, **self.paddings)

            # then the search text entry
            # first the string variable that "monitors" what's being typed in the input
            search_str = tk.StringVar()

            # the search input
            search_input = Entry(header_frame, width=60, textvariable=search_str)

            search_input.pack(side=tk.LEFT, **self.paddings)

            # THE SEARCH RESULTS text box
            # (for now this looks like a console, maybe some improvements can be made later)
            results_text = tk.Text(results_form_frame,
                                   font=self.console_font, width=45, height=30, padx=5, pady=5, wrap=tk.WORD,
                                    background=self.resolve_theme_colors['black'],
                                    foreground=self.resolve_theme_colors['normal'])


            results_text.config(spacing1=0, spacing2=0.2, spacing3=5)

            results_text.pack(anchor='w', expand=True, fill='both')

            results_text.insert(tk.END, 'This feature is experimental.\n'
                                        'Check README for details:\n https://github.com/octimot/StoryToolkitAI/')
            results_text.config(state=DISABLED)

            # bind return to the search entry box
            search_input.bind('<Return>', lambda e: self.button_advanced_search(
                                                                    search_window_id,
                                                                    search_str.get(),
                                                                    results_text,
                                                                    transcription_file_paths
                                                                    )
                              )

            return True

    def _get_group_id_from_listbox(self, groups_listbox: tk.Listbox) -> str:
        '''
        Returns the group id of the selected group in the groups listbox

        :param groups_listbox:
        :return:
        '''

        return groups_listbox.get(tk.ANCHOR).strip().lower()

    def _get_selected_group_id(self, t_window_id: str = None, groups_listbox: tk.Listbox = None) \
            -> str or bool or None:
        '''
        Returns the group id of the selected group either from the selected groups dict or from in the group listbox
        :param t_window_id: the id of the transcription window (optional, if groups_listbox is not None)
        :param groups_listbox: the listbox with the groups (optional, if t_window_id is not None)
        :return: group id
        '''

        # this gets the currently selected group id
        # one thing to note is that in the listbox, we are using the group name
        # so this means that we are basically using the group name as a group id (after lowercasing it)
        # this is fine for now, but if things become more complex
        # we need to develop a mapping between the currently selected list item and the group id
        if t_window_id is not None:

            if t_window_id not in self.t_edit_obj.selected_groups:
                logger.error('No group is selected in transcription window {}'.format(t_window_id))
                return None

            if self.t_edit_obj.selected_groups[t_window_id] is None\
                    or len(self.t_edit_obj.selected_groups[t_window_id]) == 0:
                return None

            # get the selected group id from the selected groups dict
            group_id = self.t_edit_obj.selected_groups[t_window_id][0]

        elif groups_listbox is not None:
            # get the selected group id from the listbox
            group_id = self._get_group_id_from_listbox(groups_listbox)

        else:
            logger.error('No transcription window id or groups listbox was provided. Aborting.')
            return False

        print('group_id', group_id.strip().lower())

        return group_id.strip().lower()

    def on_group_update_press(self, t_window_id: str, t_group_window_id: str, group_id: str = None,
                       groups_listbox: tk.Listbox = None):
        '''
        Do stuff and update the group data in the transcription file,
        but only with the update_only_data (everything else will be left untouched in the group dict)
        :param t_window_id:
        :param t_group_window_id:
        :param group_id:
        :param groups_listbox:
        :param update_only_data: The only data to update in the group (everything else is taken
                                    from the group window dict)
        :return:
        '''

        # get the fields from the group window
        # (we're only need the group notes, and we'll update the time intervals based on the selected segments later)
        form_update_data = self._get_form_data(t_group_window_id, inputs=['group_notes'])

        # set the update data correctly
        # (we're using group_notes as an input name, but need notes for the dict)
        update_data = {'notes': form_update_data['group_notes'].strip()}

        # if group_id is None, get it from the listbox
        if group_id is None and groups_listbox is not None:

            # this gets the currently selected group id based on the selected group name
            group_id = self._get_selected_group_id(t_window_id=t_window_id)

            if group_id is None or not group_id:
                logger.debug('No group is selected in transcription window {}'.format(t_window_id))
                return False

        elif group_id is None and groups_listbox is None:
            logger.debug('No group id or group listbox was not provided')
            return False

        # get the current group data from the group window dict
        if t_window_id in self.t_edit_obj.transcript_groups \
            and group_id in self.t_edit_obj.transcript_groups[t_window_id]:

            # get the current group data
            group_data = self.t_edit_obj.transcript_groups[t_window_id][group_id]

            # update the current group data with the update_only_data
            group_data.update(update_data)

            # get the selected segments for the group
            segments_for_group = list(self.t_edit_obj.selected_segments[t_window_id].values())

            # get the transcription file path from the window transcription paths dict
            if t_window_id in self.t_edit_obj.transcription_file_paths:

                transcription_file_path = self.t_edit_obj.transcription_file_paths[t_window_id]

                # save the group data to the transcription file
                # save_return = self.toolkit_ops_obj.t_groups_obj\
                #                .save_transcript_groups(transcription_file_path=transcription_file_path,
                #                                         transcript_groups=group_update_data,
                #                                         group_id=group_id)

                # save the segments to the transcription file
                save_return = self.toolkit_ops_obj.t_groups_obj\
                                        .save_segments_as_group_in_transcription_file(
                                            transcription_file_path=transcription_file_path,
                                            segments=segments_for_group,
                                            group_name=group_data['name'],
                                            group_notes=group_data['notes'],
                                            existing_transcript_groups=self.t_edit_obj.transcript_groups[t_window_id],
                                            overwrite_existing=True)


                if not save_return:
                    logger.error('Could not save group {} data to transcription file {}'
                                 .format(group_id, transcription_file_path))
                    return False

                else:
                    logger.debug('Group {} data updated in transcription file {}'
                                 .format(group_id, transcription_file_path))

                    # replace the group data in the window dict with the updated data
                    self.t_edit_obj.transcript_groups[t_window_id] = save_return

                    logger.info('Group updated')

                return save_return

            else:
                logger.error('No transcription file path was found for the current window id')

        return False



    def on_group_delete_press(self, t_window_id: str, t_group_window_id: str, group_id: str = None,
                       groups_listbox: tk.Listbox = None):
        '''
        Do stuff when the delete group button is pressed:
        this will delete the group from the transcription data
        and update the transcription groups window with the remaining groups

        :param t_window_id:
        :param t_group_window_id:
        :param group_id:
        :param groups_listbox:
        :return:
        '''

        # if group_id is None, get it from the listbox
        if group_id is None and groups_listbox is not None:

            group_id = self._get_selected_group_id(t_window_id=t_window_id)

        else:
            logger.debug('No group id or group listbox was provided')
            return False

        # delete the group from the transcription data
        # (by passing the transcription window id and the group id we're also updating the group window)
        self.t_edit_obj.delete_group(t_window_id, group_id,
                                     t_group_window_id=t_group_window_id, groups_listbox=groups_listbox)

    def on_group_press(self, e, t_window_id: str, t_group_window_id: str, group_id: str = None,
                       groups_listbox: tk.Listbox = None):
        '''
        Do stuff when the user presses a group somewhere
        :param t_window_id:
        :param t_group_window_id:
        :param group_id: The group id (optional, if group_listbox is not None)
        :param groups_listbox: The tk element that contains the groups (optional, if group_id is not None)
        :return:
        '''

        # if group_id is None, get it from the listbox
        if group_id is None and groups_listbox is not None:

            group_id = self._get_group_id_from_listbox(groups_listbox=groups_listbox)

        else:
            logger.debug('No group id or group listbox was provided')
            return False

        # if the group id matches the group id in the selected group
        # it means that we are clicking on a group that was already selected
        # so, deselect the group and all the segments from the window
        if t_window_id in self.t_edit_obj.selected_groups \
                and group_id in self.t_edit_obj.selected_groups[t_window_id]:

            # empty the selected groups
            self.t_edit_obj.selected_groups[t_window_id] = []

            # clear the selected segments
            self.t_edit_obj.clear_selection(t_window_id)

            # clear the selection in the listbox
            groups_listbox.selection_clear(0, tk.END)

            # update the group window
            self.update_transcript_group_form(t_window_id, t_group_window_id, group_id=None)

            # hide the group_details_frame
            self._hide_group_details_frame(t_group_window_id)

        # otherwise it means that we want to select a group
        else:

            # create the selected groups for the transcription window if it doesn't exist
            if t_window_id not in self.t_edit_obj.selected_groups:
                self.t_edit_obj.selected_groups[t_window_id] = []

            # empty the selected groups (deactivate when multiple groups can be selected)
            self.t_edit_obj.selected_groups[t_window_id] = []

            # add the group to the currently selected groups
            self.t_edit_obj.selected_groups[t_window_id].append(group_id)

            # select the segments in the transcription window
            self.select_group_segments(t_window_id, group_id)

            # update the group window
            self.update_transcript_group_form(t_window_id, t_group_window_id, group_id)

            # show the group_details_frame
            self._show_group_details_frame(t_group_window_id)

        return True

    def select_group_segments(self, t_window_id: str, group_id: str, text_element: tk.Text = None):
        '''
        Select the segments in the transcription window according to the time_intervals in the group data
        :param t_window_id:
        :param group_id:
        :param text_element: The text element to select the segments in (optional)
        :return:
        '''

        # get the transcription group data
        # if it exists in the dict
        if t_window_id in self.t_edit_obj.transcript_groups \
                and group_id in self.t_edit_obj.transcript_groups[t_window_id]:

            group_data = self.t_edit_obj.transcript_groups[t_window_id][group_id]

            # get the time intervals
            if 'time_intervals' in group_data:
                time_intervals = group_data['time_intervals']

                # get the transcript segments
                if t_window_id in self.t_edit_obj.transcript_segments:
                    transcript_segments = self.t_edit_obj.transcript_segments[t_window_id]

                    # convert the time intervals to segments
                    group_segments = \
                        self.toolkit_ops_obj.time_intervals_to_transcript_segments(time_intervals, transcript_segments)

                    # if no text element was provided, get it from the transcription window
                    if text_element is None:
                        text_element = self.t_edit_obj.get_transcription_window_text_element(t_window_id)

                        # now clear the selection
                        self.t_edit_obj.clear_selection(t_window_id)

                        group_lines = []

                        # go through the segments and get their line numbers
                        for segment in group_segments:

                            # get the line number
                            group_lines.append(self.t_edit_obj.segment_id_to_line(t_window_id, segment['id']))

                        # and select the segments
                        self.t_edit_obj.segment_to_selection(t_window_id, text_element=text_element, line=group_lines)

                        return True

        # if the above fails, just return False
        return False

    def update_transcript_group_form(self, t_window_id: str, t_group_window_id: str, group_id: str or None):
        '''
        This updates the transcript group form with the data stored in the transcript_groups dict
        :param t_window_id: the id of the transcription window (needed to get the groups data)
        :param t_group_window_id: the id of the group window
        :param group_id: the id of the group to pull data from
        :return:
        '''

        # initialize the group data that dict that will be pass to the populate function
        update_group_data = {'group_notes': ''}

        # get the transcription group data
        # if it exists in the dict
        if group_id is not None and \
                t_window_id in self.t_edit_obj.transcript_groups \
                and group_id in self.t_edit_obj.transcript_groups[t_window_id]:

            # get the group data
            group_data = self.t_edit_obj.transcript_groups[t_window_id][group_id]

            # use the group data to populate the group form (just the notes here)
            update_group_data = {'group_notes': group_data['notes']}

        # populate the transcription group form
        self._populate_form_data(window_id=t_group_window_id, form_data=update_group_data)

    def _get_form_data(self, window_id: str, inputs: list = None) -> dict or bool:
        '''
        This gets the data from the form fields
        :param window_id:
        :param fields: The fields to get the data from (optional)
        :return: A dict with the data from the form fields
        '''

        # keep track of the elements that we have found
        found_inputs = []

        # keep track of the data that we have found
        form_data = {}

        for key in inputs:
            form_data[key] = None

        # the window needs to be registered in the windows dict
        if window_id not in self.windows:
            logger.error('The window id provided was not found in the windows dict')
            return False

        # search through all the elements in the window until we find the elements that we need
        # but since we are expecting the forms to be inside a frame, we'll only look at the second level
        for child in self.windows[window_id].winfo_children():

            # go another level deeper, since we are expecting the forms to be inside a frame
            if len(child.winfo_children()) > 0:

                for child2 in child.winfo_children():

                    # if the child2 name is in the form_input_names dict
                    if child2.winfo_name() in inputs:

                        # add the input to the found inputs list
                        found_inputs.append(child2.winfo_name())

                        # get the tkinter value of the element depending on the type
                        if child2.winfo_class() == 'Entry':

                            # get the value of the entry
                            form_data[child2.winfo_name()] = child2.get()

                        elif child2.winfo_class() == 'Text':

                            # get the whole value of the text input
                            form_data[child2.winfo_name()] = child2.get(0.0, tk.END)

                        else:
                            # this is to let us know that we need to create a procedure for this input type
                            logger.error('The tkinter input type {} for {} is not supported'
                                         .format(child2.winfo_class(), child2.winfo_name()))

        # if we didn't find all the inputs, log it
        if len(found_inputs) != len(form_data):
            logger.debug('Not all requested form inputs were not found in the window')

        return form_data


    def _populate_form_data(self, window_id, form_data):
        '''
        This populates the form data in the form with the data provided

        It will automatically search for the elements in the window and if the elements are found, it will populate them

        form_data needs to be a dict with the element names as keys and the values used to populate the elements

        :param window_id:
        :param form_data:
        :return:
        '''

        # initialize empty inputs until we find them
        form_input_names = {}

        # keep track of the elements that we have found
        all_inputs = list(form_data.keys())
        found_inputs = []

        for key in form_data:
            form_input_names[key] = None

        # the window needs to be registered in the windows dict
        if window_id not in self.windows:
            logger.error('The window id provided was not found in the windows dict')
            return False

        # search through all the elements in the window until we find the elements that we need
        # but since we are expecting the forms to be inside a frame, we'll only look at the second level
        for child in self.windows[window_id].winfo_children():

            # go another level deeper, since we are expecting the forms to be inside a frame
            if len(child.winfo_children()) > 0:

                for child2 in child.winfo_children():

                    # if the child2 name is in the form_input_names dict
                    if child2.winfo_name() in form_input_names:
                        form_input_names[key] = child2

                        # add the input to the found inputs list
                        found_inputs.append(child2.winfo_name())

                        # update the input based on the tkinter input type
                        if child2.winfo_class() == 'Entry':

                            # clear the input
                            child2.delete(0, tk.END)

                            # then populate it with the data
                            form_input_names[key].insert(0.0, form_data[key])

                        elif child2.winfo_class() == 'Text':

                            # clear the text input
                            form_input_names[key].delete(0.0, tk.END)

                            # then populate it with the data
                            form_input_names[key].insert(0.0, form_data[key])

                        else:
                            # this is to let us know that we need to create a procedure for this input type
                            logger.error('The tkinter input type {} for {} is not supported'
                                         .format(child2.winfo_class(), child2.winfo_name()))

        # if we didn't find all the inputs
        if len(found_inputs) != len(all_inputs):

            # get the inputs that we didn't find
            missing_inputs = list(set(all_inputs) - set(found_inputs))

            # log the missing inputs
            # this is to let us know that maybe we need to name the inputs in the form so they're found
            # this could also happen if, for instance, the input is not in the window frame
            logger.error('The following inputs were not found while updating window {}: {}'
                         .format(window_id, missing_inputs))


    def update_transcript_groups_window(self, t_window_id: str, t_group_window_id: str = None,
                                        groups_listbox: tk.Listbox = None):

        # if the group window id is not provided, assume this:
        if t_group_window_id is None:
            t_group_window_id = t_window_id+'_transcript_groups'

        # we'll definitely need the groups notes input
        group_details_frame = None

        # we need a valid groups window id to continue
        if t_group_window_id not in self.windows:
            return False

        # search through all the elements in the window until we find some elements that we might need
        for child in self.windows[t_group_window_id].winfo_children():

            # go another level deeper, since we are expecting the forms to be inside a frame
            if len(child.winfo_children()) > 0:

                for child2 in child.winfo_children():

                    # if no groups listbox was provided remember but we found one, remember it
                    if child2.winfo_name() == 'groups_listbox' \
                            and groups_listbox is None and t_group_window_id in self.windows:
                        groups_listbox = child2

                        # if we found the group notes input, break out from this loop
                        break

            if child.winfo_name() == 'group_details_frame':
                group_details_frame = child

        # if we haven't found the groups notes input or groups listbox, return False
        if group_details_frame is None or groups_listbox is None:
            return False

        # clear the listbox
        groups_listbox.delete(0, tk.END)

        # get the groups data
        if t_window_id in self.t_edit_obj.transcript_groups:
            groups_data = self.t_edit_obj.transcript_groups[t_window_id]

            # create a list with all the group names from the group data
            # the group names are inside the group data dict
            # and sort them alphabetically
            group_names = sorted([group_data['name'] for group_id, group_data in groups_data.items()])

            # then add the transcript groups to the listbox
            for group_name in group_names:
                groups_listbox.insert(END, group_name)

        # clear all the group form inputs
        # but only if no group or more than a group is selected
        if t_window_id not in self.t_edit_obj.selected_groups\
                or len(self.t_edit_obj.selected_groups[t_window_id]) != 1:

            update_group_data = {'group_notes': ''}

            # populate the transcription group form
            self._populate_form_data(window_id=t_group_window_id, form_data=update_group_data)

            self._hide_group_details_frame(t_group_window_id, group_details_frame)

        elif t_window_id in self.t_edit_obj.selected_groups\
                and len(self.t_edit_obj.selected_groups[t_window_id]) == 1:

            self._show_group_details_frame(t_group_window_id, group_details_frame)

        return True

    def _get_group_details_frame(self, t_group_window_id: str):

        # we need a valid groups window id to continue
        if t_group_window_id not in self.windows:
            return False

        # search through all the elements in the window until we find some elements that we might need
        for child in self.windows[t_group_window_id].winfo_children():

            if child.winfo_name() == 'group_details_frame':
                return child

    def _show_group_details_frame(self, t_group_window_id: str, group_details_frame: tk.Frame = None):

        if group_details_frame is None:
            group_details_frame = self._get_group_details_frame(t_group_window_id)

        # or show the group notes label and text input
        group_details_frame.pack(side=tk.BOTTOM, expand=True, fill=tk.X, **self.paddings, anchor=tk.S)

    def _hide_group_details_frame(self, t_group_window_id: str, group_details_frame: tk.Frame = None):

        if group_details_frame is None:
            group_details_frame = self._get_group_details_frame(t_group_window_id)

        # now hide the group notes label and text input
        group_details_frame.pack_forget()

    def destroy_transcript_groups_window(self, window_id: str = None):

        # call the default destroy window function
        self.destroy_window_(parent_element=self.windows, window_id=window_id)

    def open_transcript_groups_window(self, transcription_window_id, transcription_name=None):

        # the transcript groups window id
        transcript_groups_window_id = '{}_transcript_groups'.format(transcription_window_id)

        # the transcript groups window title
        if transcription_name:
            transcript_groups_window_title = 'Groups - {}'.format(transcription_name)
        else:
            transcript_groups_window_title = 'Groups'

        # create a window for the transcript groups if one doesn't already exist
        if self.create_or_open_window(parent_element=self.windows[transcription_window_id],
                                       window_id=transcript_groups_window_id,
                                       title=transcript_groups_window_title, resizable=True,
                                       close_action=
                                            lambda: self.destroy_transcript_groups_window(transcript_groups_window_id)
                                       ):

            # the current transcript groups window object
            current_transcript_groups_window = self.windows[transcript_groups_window_id]

            # use the transcript groups stored in the transcription window
            if transcription_window_id in self.t_edit_obj.transcript_groups:

                transcript_groups = self.t_edit_obj.transcript_groups[transcription_window_id]

            # if they don't exist, create an empty dict
            else:
                self.t_edit_obj.transcript_groups[transcription_window_id] = {}
                transcript_groups = {}

            elements_width = 30

            # add the frame to hold the transcript groups
            transcript_groups_frame = tk.Frame(self.windows[transcript_groups_window_id])
            transcript_groups_frame.pack(expand=True, fill=tk.BOTH, **self.paddings)

            # add a listbox that holds all the transcript groups
            groups_listbox = Listbox(transcript_groups_frame, name="groups_listbox",
                                     width=elements_width, height=10, selectmode='single', exportselection=False)
            groups_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

            # add a scrollbar to the listbox
            scrollbar = Scrollbar(transcript_groups_frame, orient="vertical", **self.scrollbar_settings)
            scrollbar.config(command=groups_listbox.yview)
            scrollbar.pack(side=tk.RIGHT, fill='y')

            # configure the listbox to use the scrollbar
            groups_listbox.config(yscrollcommand=scrollbar.set)

            # add a frame to hold the transcript group details under the listbox
            transcript_group_details_frame = tk.Frame(current_transcript_groups_window, name='group_details_frame')

            # do not pack the frame yet, it will be packed when a group is selected (in the update function)
            # transcript_group_details_frame.pack(side=tk.BOTTOM, expand=True, fill=tk.X, **self.paddings, anchor=tk.S)

            # inside the transcript group details frame, add the inputs
            # for the transcript group name, notes and some buttons

            # the transcript group notes text box
            Label(transcript_group_details_frame, text="Group Notes:", anchor='nw')\
                .pack(side=tk.TOP, expand=True, fill=tk.X)
            transcript_group_notes = tk.StringVar()
            transcript_group_notes_input = Text(transcript_group_details_frame, name='group_notes',
                                                width=elements_width, height=5, wrap=tk.WORD)
            transcript_group_notes_input.pack(side=tk.TOP, expand=True, fill=tk.X, anchor='nw')

            # update the transcript group notes variable when the text box is changed
            #transcript_group_notes_input.bind('<KeyRelease>', lambda e: transcript

            # add a frame to hold the buttons
            transcript_group_buttons_frame = tk.Frame(transcript_group_details_frame)
            transcript_group_buttons_frame.pack(side=tk.TOP, expand=True, fill=tk.X)

            # the transcript group update button
            transcript_group_update = tk.Button(transcript_group_buttons_frame, text='Save',
                                                command=lambda

                                                 transcription_window_id=transcription_window_id,
                                                 transcript_groups_window_id=transcript_groups_window_id,
                                                 group_notes=transcript_group_notes_input.get(0.0, tk.END),
                                                 groups_listbox=groups_listbox:
                                                    self.on_group_update_press(
                                                        transcription_window_id,
                                                        transcript_groups_window_id,
                                                        groups_listbox=groups_listbox
                                                  ))
            transcript_group_update.pack(side=tk.LEFT)


            # the transcript group delete button
            transcript_group_delete = tk.Button(transcript_group_buttons_frame, text="Delete",
                                               command=lambda
                                                   transcription_window_id=transcription_window_id,
                                                   transcript_groups_window_id=transcript_groups_window_id,
                                                   groups_listbox=groups_listbox:
                                                    self.on_group_delete_press(transcription_window_id,
                                                                               transcript_groups_window_id,
                                                                               groups_listbox=groups_listbox))
            transcript_group_delete.pack(side=tk.RIGHT)

            # when a user selects a transcript group from the listbox, update the transcript group details
            groups_listbox.bind('<<ListboxSelect>>',
                                lambda e,
                                       transcription_window_id=transcription_window_id,
                                       transcript_groups_window_id=transcript_groups_window_id,
                                       groups_listbox=groups_listbox:
                                    self.on_group_press(e, t_window_id=transcription_window_id,
                                                             t_group_window_id=transcript_groups_window_id,
                                                             groups_listbox=groups_listbox))

            # place the transcript groups window on top of the transcription window
            self.windows[transcript_groups_window_id].attributes('-topmost', 'true')
            self.windows[transcript_groups_window_id].attributes('-topmost', 'false')
            self.windows[transcript_groups_window_id].lift()

            # and then call the update function to fill the groups listbox up
            self.update_transcript_groups_window(t_window_id=transcription_window_id,
                                                 t_group_window_id=transcript_groups_window_id,
                                                 groups_listbox=groups_listbox)

    def button_advanced_search(self, search_window_id, search_term, results_text_element=None,
                               transcription_file_paths=None):

        if transcription_file_paths is None:
            logger.error('Cannot search. No transcription file path was passed.')
            return False

        results_text_element.config(state=NORMAL)

        # first clear the results text box
        results_text_element.delete('1.0', tk.END)

        logger.info('Searching for "{}"'.format(search_term))

        # remember when we started the search
        start_search_time = time.time()

        # define the default max_results
        # this might be replaced by a user input later
        max_results = 10

        # perform the search
        search_results, max_results \
            = self.toolkit_ops_obj.t_search_obj.t_search(query=search_term,
                                                       transcription_file_paths=transcription_file_paths,
                                                       search_id=search_window_id,
                                                       max_results=max_results
                                                       )

        # how long did the search take?
        total_search_time = time.time() - start_search_time

        # log the search time
        logger.info('Search took {:.2f} seconds.'.format(total_search_time))

        # now add the search results to the search results window
        if len(search_results) > 0:

            # reset the previous search_term
            result_search_term = ''

            for result in search_results:

                # if we've changed the search term, add a new header
                if result['search_term'] != result_search_term:

                    result_search_term = result['search_term']

                    # add the search term header
                    results_text_element.insert(tk.END, 'Searching for: "' + result_search_term + '"\n')
                    results_text_element.insert(tk.END, '--------------------------------------\n')
                    results_text_element.insert(tk.END, 'Top {} closest phrases:\n\n'.format(max_results))


                # remember the current insert position
                current_insert_position = results_text_element.index(tk.INSERT)

                results_text_element.insert(tk.END, str(result['text']).strip() + '\n')

                # color it in blue
                results_text_element.tag_add('white', current_insert_position, tk.INSERT)
                results_text_element.tag_config('white', foreground=self.resolve_theme_colors['supernormal'])

                # add score and segment info to the result
                results_text_element.insert(tk.END, ' -- Score: {:.4f}\n'.format(result['score']))
                results_text_element.insert(tk.END, ' -- Transcript: {}\n'
                                            .format(os.path.basename(result['transcription_file_path'])))
                results_text_element.insert(tk.END, ' -- Line {} (second {:.2f}) \n\n'
                                            .format(result['segment_index'], result['transcript_time']))

                # add a tag to the above text to make it clickable
                tag_name = 'clickable_{}'.format(result['idx'])
                results_text_element.tag_add(tag_name, current_insert_position, tk.INSERT)

                # add the transcription file path and segment index to the tag
                # so we can use it to open the transcription window with the transcription file and jump to the segment
                results_text_element.tag_bind(tag_name, '<Button-1>',
                                              lambda event, transcription_file_path=result['transcription_file_path'],
                                                     line_no=result['line_no']:
                                              self.open_transcription_window(
                                                  transcription_file_path=transcription_file_path,
                                                  select_line_no=line_no))

                # bind mouse clicks press events on the results text box
                # bind CMD/CTRL + mouse Clicks to text
                results_text_element.tag_bind(tag_name, "<"+self.ctrl_cmd_bind+"-Button-1>",
                                              lambda event, transcription_file_path=result['transcription_file_path'],
                                                     line_no=result['line_no'],
                                                     all_lines=result['all_lines']:
                                              self.open_transcription_window(
                                                  transcription_file_path=transcription_file_path,
                                                  select_line_no=line_no,
                                                  add_to_selection=all_lines)
                                              )


            # update the results text element
            results_text_element.insert(tk.END, '--------------------------------------\n')
            results_text_element.insert(tk.END, 'Search took {:.2f} seconds\n'.format(total_search_time))

            results_text_element.config(state=DISABLED)

        return True

    def ask_for_target_dir(self, title=None, target_dir=None):

        # use the global initial_target_dir
        global initial_target_dir

        # if an initial target dir was passed
        if target_dir is not None:
            # assign it as the initial_target_dir
            initial_target_dir = target_dir

        # put the UI on top
        # self.root.wm_attributes('-topmost', True)
        self.root.lift()

        # ask the user via os dialog where can we find the directory
        if title == None:
            title = "Where should we save the files?"
        target_dir = filedialog.askdirectory(title=title, initialdir=initial_target_dir)

        # what happens if the user cancels
        if not target_dir:
            return False

        # remember which directory the user selected for next time
        initial_target_dir = target_dir

        return target_dir

    def ask_for_target_file(self, filetypes=[("Audio files", ".mov .mp4 .wav .mp3")], target_dir=None, multiple=False):
        global initial_target_dir

        # if an initial target_dir was passed
        if target_dir is not None:
            # assign it as the initial_target_dir
            initial_target_dir = target_dir

        # put the UI on top
        # self.root.wm_attributes('-topmost', True)
        self.root.lift()

        # ask the user via os dialog which file to use
        if not multiple:
            target_file = filedialog.askopenfilename(title="Choose a file", initialdir=initial_target_dir,
                                                     filetypes=filetypes)
        else:
            target_file = filedialog.askopenfilenames(title="Choose the files", initialdir=initial_target_dir,
                                                     filetypes=filetypes)

        # what happens if the user cancels
        if not target_file:
            return False

        # remember what the user selected for next time
        initial_target_dir = os.path.dirname(target_file if isinstance(target_file, str) else target_file[0])

        return target_file

    def window_on_top(self, window_id=None, on_top=None):

        if window_id is not None:

            # does the window exist?
            if window_id in self.windows:

                # keep the window on top if on_top is true
                if on_top is not None and on_top:
                    self.windows[window_id].wm_attributes("-topmost", 1)
                    return True
                # don't keep the window on top if on top is false
                elif on_top is not None:
                    self.windows[window_id].wm_attributes("-topmost", 0)
                    return False
                # if the on top variable wasn't passed
                else:
                    # toggle between on and off
                    topmost = self.windows[window_id].wm_attributes("-topmost")
                    self.windows[window_id].wm_attributes("-topmost", not topmost)

                    # and return the current state
                    return self.windows[window_id].wm_attributes("-topmost")

    def window_on_top_button(self, button=None, window_id=None, on_top=None):

        # ask the UI to keep (or not) the window with this window_id on_top
        if self.window_on_top(window_id=window_id, on_top=on_top):

            # if the reply is true, it means that the window will be kept on top
            # therefore the button needs to read the opposite action
            button.config(text="Don't keep on top")
            return True
        else:
            # and the opposite if the window will not be kept on top
            button.config(text="Keep on top")
            return False

    def notify_via_os(self, title, text, debug_message):
        """
        Uses OS specific tools to notify the user

        :param title:
        :param text:
        :param debug_message:
        :return:
        """

        # log and print to console first
        logger.info(debug_message)

        # notify the user depending on which platform they're on
        if platform.system() == 'Darwin':  # macOS
            os.system("""
                                                    osascript -e 'display notification "{}" with title "{}"'
                                                    """.format(text, title))

        # @todo OS notifications on other platforms
        elif platform.system() == 'Windows':  # Windows
            return
        else:  # linux variants
            return

    def notify_via_messagebox(self, type='info', message_log=None, message=None, **options):

        if message_log is None:
            message_log = message

        # alert the user using the messagebox according to the type
        # and log the message
        if type == 'error':
            messagebox.showerror(message=message, **options)
            logger.error(message_log)

        elif type == 'info':
            messagebox.showinfo(message=message, **options)
            logger.info(message_log)

        elif type == 'warning':
            messagebox.showwarning(message=message, **options)
            logger.warning(message_log)

        # if no type was passed, just log the message
        else:
            logger.debug(message_log)


class ToolkitOps:

    def __init__(self, stAI=None, disable_resolve_api=False):

        # this will be used to store all the transcripts that are ready to be transcribed
        self.transcription_queue = {}

        # keep a reference to the StoryToolkitAI object here if one was passed
        self.stAI = stAI

        # define the path to the transcription queue file relative to the user_data_path
        if self.stAI is not None:
            self.TRANSCRIPTION_QUEUE_FILE_PATH = os.path.join(stAI.user_data_path, 'transcription_queue.json')

        # use a relative path for the transcription queue file, if no stAI was passed
        else:
            self.TRANSCRIPTION_QUEUE_FILE_PATH = 'transcription_queue.json'

        # initialize the toolkit search engine
        self.t_search_obj = self.ToolkitSearch(toolkit_ops_obj=self)

        # initialize the TranscriptGroups object
        self.t_groups_obj = self.TranscriptGroups(toolkit_ops_obj=self)

        # transcription queue thread - this will be useful when trying to figure out
        # if there's any transcription thread active or not
        self.transcription_queue_thread = None

        # use these attributes for the transcription items (both queue and log)
        # this will be useful in case we need to add additional attributes to the transcription items
        # so that we don't have to update every single function that is using the transcription items
        # @todo make sure this is correctly implemented across the toolkit
        self.transcription_item_attr = ['name', 'audio_file_path', 'translate', 'info', 'status',
                                        'json_file_path', 'srt_file_path', 'txt_file_path']

        # transcription log - this keeps a track of all the transcriptions
        self.transcription_log = {}

        # this is used to get fast the name of what is being transcribed currently
        self.transcription_queue_current_name = None

        # this is to keep track of the current transcription item
        # the format is {unique_id: transcription_item_attributes}
        self.transcription_queue_current_item = {}

        # declare this as none for now so we know it exists
        self.toolkit_UI_obj = None

        # use this to store the whisper model later
        self.whisper_model = None

        # load the whisper model from the config
        # we're recommending the medium model for better accuracy vs. time it takes to process
        # if in doubt use the large model but that will need more time
        self.whisper_model_name = self.stAI.get_app_setting(setting_name='whisper_model_name', default_if_none='medium')

        # get the whisper device setting
        # currently, the setting may be cuda, cpu or auto
        self.whisper_device = stAI.get_app_setting('whisper_device', 'auto')

        self.whisper_device = self.whisper_device_select(self.whisper_device)

        # now let's deal with the sentence transformer model
        # this is the transformer model name that we will use to search semantically
        self.s_semantic_search_model_name \
            = self.stAI.get_app_setting(setting_name='s_semantic_search_model_name',
                                        default_if_none='all-MiniLM-L6-v2')

        # for now define an empty model here which should be loaded the first time it's needed
        self.s_semantic_search_model = None

        # init Resolve (if resolve API isn't disabled via config or parameter)
        if not self.stAI.get_app_setting('disable_resolve_api', default_if_none=False) \
                and not disable_resolve_api:
            self.resolve_api = MotsResolve(logger=logger)

            # start the resolve thread
            # with this, resolve should be constantly polled for data
            self.poll_resolve_thread()

        else:
            self.resolve_api = None
            logger.debug('Resolve API disabled via config')

        # resume the transcription queue if there's anything in it
        if self.resume_transcription_queue_from_file():
            logger.info('Resuming transcription queue from file')

        # toolkit_UI_obj.create_transcription_settings_window()
        # time.sleep(120)
        # return

    class ToolkitSearch:

        def __init__(self, toolkit_ops_obj):

            # load the toolkit ops object
            self.toolkit_ops_obj = toolkit_ops_obj

            # load the stAI object
            self.stAI = self.toolkit_ops_obj.stAI

            # keep all the search_corpuses here to find them easy by search_id
            # this also optimizes the search so that the corpus is only compiled once per search session
            self.search_corpuses = {}

        def load_transcription_paths_to_search_dict(self, transcription_file_paths):
            '''
            Loads the transcription file paths to a dictionary that can be used for searching
            :param transcription_file_paths: this can be a list of file paths or a single file path
            :return:
            '''

            # if no transcription file paths were provided
            if transcription_file_paths is None or len(transcription_file_paths) == 0:
                # throw an error if no transcription file was passed
                logger.error('Cannot search. No transcription file path was passed.')

            # otherwise use all the transcription files in the target dir
            # else:
            #
            #    # get the list of transcription files in the target dir using os.walk
            #    transcription_files = os.walk

            # if only one transcription file path is given, make it a list
            if type(transcription_file_paths) is str:
                transcription_file_paths = [transcription_file_paths]

            # define the transcriptions dict
            search_transcriptions = {}

            # take all the transcription file paths and load them into the search_transcriptions dictionary
            for transcription_file_path in transcription_file_paths:

                # if a specific transcription file was passed, use that in the search
                if transcription_file_path is not None:

                    # don't include the file if it doesn't exist
                    if not os.path.isfile(transcription_file_path):
                        logger.error('Transcription file {} not found. Skipping.'.format(transcription_file_path))
                        continue

                    # now read the transcription file contents
                    search_transcriptions[transcription_file_path] = \
                        self.toolkit_ops_obj.get_transcription_file_data(
                            transcription_file_path=transcription_file_path)

            return search_transcriptions

        def prepare_search_corpus(self, search_transcriptions, search_id):
            '''
            Takes all the segments from the search_transcriptions and turns them into a search corpus
            :param search_transcriptions:
            :param search_id:
            :return:
            '''

            # re-organize the search corpus into a dictionary of phrases
            # with the transcription file path as the key
            # and the value being a list of phrases compiled from the transcription file text using
            # the punctuation as dividers.
            # this will make it easier to search for phrases in the transcription files
            search_corpus_phrases = []

            # use this to keep track of the transcription file path and the phrase index
            search_corpus_assoc = {}

            # and if the hasn't already been created, just create it
            if search_id not in self.toolkit_ops_obj.t_search_obj.search_corpuses:

                logger.info('Clustering search corpus by phrases.')

                # loop through all the transcription files in the search_transcriptions dictionary
                for transcription_file_path, transcription_file_data in search_transcriptions.items():

                    logger.debug('Adding {} to the search corpus.'.format(transcription_file_path))

                    if type(transcription_file_data) is not dict:
                        logger.warning('Transcription file {} is not in the right format. Skipping.'
                                       .format(transcription_file_path))

                    elif type(transcription_file_data) is dict \
                        and 'segments' in transcription_file_data \
                        and type(transcription_file_data['segments']) is list:

                        # group the segment texts into phrases using punctuation as dividers
                        # instead of how they're currently segmented
                        # once they are grouped, add them to the search corpus
                        # plus add them to the search corpus association list so we know
                        # from which transcription file and from which segment they came from originally

                        # initialize the current phrase
                        current_phrase = ''

                        # loop through the segments of this transcription file
                        for segment_index, segment in enumerate(transcription_file_data['segments']):

                            # first remember the transcription file path and the segment index
                            # if this is a new phrase (i.e. the current phrase is empty)
                            if current_phrase == '':
                                # this is the segment index relative to the whole search corpus that
                                # contains all the transcription file segments (not just the current transcription file)
                                general_segment_index = len(search_corpus_phrases)

                                search_corpus_assoc[general_segment_index] = {'transcription_file_path':
                                                                                  transcription_file_path,
                                                                              'segment': segment['text'],
                                                                              'segment_index':
                                                                                  segment_index,
                                                                              'start':
                                                                                  segment['start'],
                                                                              'all_lines':
                                                                                  [int(segment_index)+1],
                                                                              }

                            # otherwise, if this is not a new phrase
                            else:
                                # just append the current segment index to the list of all lines
                                search_corpus_assoc[general_segment_index]['all_lines'].append(int(segment_index)+1)


                            # add the segment text to the current phrase
                            # but only if it's longer than 2 characters to avoid adding stuff that is most likely meaningless
                            # like punctuation marks
                            # also ignore the words that are in the ignore list
                            if 'text' in segment and type(segment['text']) is str:

                                # keep adding segments to the current phrase until we find a punctuation mark

                                # first get the segment text
                                segment_text = str(segment['text'])

                                # add the segment to the current phrase
                                current_phrase += segment_text.strip() + ' '

                                # if a punctuation mark exists in the last 5 characters of the segment text
                                # it means that the current phrase is complete
                                if re.search(r'[\.\?\!]{1}$', segment_text[-5:]):
                                    # "close" the current phrase by adding it to the search corpus
                                    search_corpus_phrases.append(current_phrase.strip())

                                    # then empty the current phrase
                                    current_phrase = ''

                # add the corpus to the search corpus dict, so we don't have to re-create it every time we search
                # we're going to use the search window id as the key
                self.search_corpuses[search_id] = {'corpus': {}, 'assoc': {}}
                self.search_corpuses[search_id]['corpus'] = search_corpus_phrases
                self.search_corpuses[search_id]['assoc'] = search_corpus_assoc

            return self.search_corpuses[search_id]['corpus'], self.search_corpuses[search_id]['assoc']

        def t_search(self, query, transcription_file_paths, search_id, max_results=10):
            '''
            Searches the transcription files for the query using the search type passed by the user
            :param query:
            :param transcription_file_paths:
            :param search_id:
            :param max_results:
            :return:
            '''

            # define the possible search types here
            search_types = ['semantic']

            # the default search type is semantic
            search_type = 'semantic'

            # the users can include a "[search_type]" in the query to specify the search type
            # if they do, then use that search type instead of the default
            if re.search(r'\[(.+?)\]', query):
                query_search_type = re.search(r'\[(.+?)\]', query).group(1)

                # if the query search type is just a number, then it's a max results value
                if query_search_type.isdigit():
                    query_max_results = str(query_search_type)

                    # but that means that the user didn't specify a search type
                    # so use the default search type
                    query_search_type = search_type

                    just_max_results = True

                # if the search type also contains a comma, then it means that the user also specified a max results
                # so extract that too
                elif not query_search_type.isdigit() and re.search(r',', query_search_type):
                    query_search_type_list = query_search_type.split(',')
                    query_search_type = query_search_type_list[0]
                    query_max_results = str(query_search_type_list[1]).strip()
                else:
                    query_max_results = str(max_results)

                # if the search type is valid, use it
                if query_search_type in search_types:
                    search_type = query_search_type

                # if the max results is valid, use it
                if query_max_results.isdigit():
                    max_results = int(query_max_results)

                # remove the search type and max results from the query
                query = re.sub(r'\[(.+?)\]', '', query).strip()

            # the user can divide multiple search terms with a | character
            # if that is the case, split them into multiple queries
            # so that we can search for each of them separately later
            if '|' in query:
                # split the query into multiple queries
                query = query.split('|')

            # first load the transcription file paths to a dictionary that can be used for searching
            search_transcriptions = self.load_transcription_paths_to_search_dict(transcription_file_paths)

            # prepare the search corpus based on the passed transcriptions
            search_corpus, search_corpus_assoc \
                = self.prepare_search_corpus(search_transcriptions=search_transcriptions, search_id=search_id)

            # now let's search the corpus based on the search type
            if search_type == 'semantic':
                results, max_results = self.search_semantic(query=query,
                                                            search_corpus_phrases=search_corpus,
                                                            search_corpus_assoc=search_corpus_assoc,
                                                            max_results=max_results)

            elif search_type == 'similar':
                results, max_results = self.search_similar(query=query,
                                                            search_corpus_phrases=search_corpus,
                                                            search_corpus_assoc=search_corpus_assoc,
                                                            max_results=max_results)
            # return the results
            return results, max_results

        def search_similar(self, query, search_corpus_phrases, search_corpus_assoc, max_results=10):

            # WORK IN PROGRESS

            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch

            # reset the search results
            search_results = []

            top_k = max_results

            model = SentenceTransformer('all-MiniLM-L6-v2')

            paraphrase_results = []

            # take each phrase in the search corpus and compare it to the query
            paraphrases = util.paraphrase_mining(model, search_corpus_phrases, top_k=max_results)

            for paraphrase in paraphrases:
                score, i, j = paraphrase
                if score < 1.0:
                    print("{} \t\t {} \t\t Score: {:.4f}".format(search_corpus_phrases[i], search_corpus_phrases[j], score))


            return search_results, top_k

        def search_semantic(self, query, search_corpus_phrases, search_corpus_assoc, max_results=10):
            '''
            This function searches for a search term in a search corpus and returns the results.
            :param search_term:
            :param search_corpus_phrases:
            :param search_corpus_assoc:
            :param max_results: the maximum number of results to return (default: 10, maximum = corpus len)
            :return:
            '''

            # if the corpus is empty, abort
            if not search_corpus_phrases:
                logger.warning('Search corpus empty.')
                return [], 0

            logger.debug('Performing semantic search on {} phrases.'.format(len(search_corpus_phrases)))

            # load the sentence transformer model if it hasn't been loaded yet
            if self.toolkit_ops_obj.s_semantic_search_model is None:
                logger.info(
                    'Loading sentence transformer model {}.'.format(self.toolkit_ops_obj.s_semantic_search_model_name))

                # if the sentence transformer model was never downloaded, log that we're downloading it
                model_downloaded_before = True
                if self.stAI.get_app_setting(setting_name='s_semantic_search_model_downloaded_{}'
                        .format(self.toolkit_ops_obj.s_semantic_search_model_name),
                                             default_if_none=False
                                             ) is False:
                    logger.warning('The sentence transformer model {} may need to be downloaded and could take a while '
                                   'depending on the Internet connection speed. '
                                   .format(self.toolkit_ops_obj.s_semantic_search_model_name)
                                   )
                    model_downloaded_before = False

                self.toolkit_ops_obj.s_semantic_search_model \
                    = SentenceTransformer(self.toolkit_ops_obj.s_semantic_search_model_name)

                # once the model has been loaded, we can note that in the app settings
                # this is a wat to keep track if the model has been downloaded or not
                # but it's not 100% reliable and we may need to find a better way to do this in the future
                if not model_downloaded_before:
                    self.stAI.save_config(setting_name='s_semantic_search_model_downloaded_{}'
                                          .format(self.toolkit_ops_obj.s_semantic_search_model_name),
                                          setting_value=True)

            # define the model into this variable for easier access
            embedder = self.toolkit_ops_obj.s_semantic_search_model

            # encode the search corpus
            corpus_embeddings = embedder.encode(search_corpus_phrases, convert_to_tensor=True)

            # if the query is string, consider that the query consists of a single search term
            # otherwise, consider that the query is a list of search terms
            queries = [query] if isinstance(query, str) else query

            # reset the search results
            search_results = []

            # Find the closest 5 sentences of the corpus for each query sentence based on cosine similarity
            logger.info('Finding the closest sentences in the corpus for the query {}.'.format(queries))

            # the top_k parameter defines how many results to return
            # it's either the max_results parameter or the length of the search corpus,
            # whatever is smaller
            top_k = min(max_results, len(search_corpus_phrases))
            for query in queries:

                # remove whitespaces from the query
                query = query.strip()

                query_embedding = embedder.encode(query, convert_to_tensor=True)

                # we use cosine-similarity and torch.topk to find the highest 5 scores
                cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
                top_results = torch.topk(cos_scores, k=top_k, sorted=True)

                for score, idx in zip(top_results[0], top_results[1]):

                    if str(search_corpus_phrases[idx]) != '':
                        transcription_file_path = search_corpus_assoc[int(idx)]['transcription_file_path']
                        segment_index = search_corpus_assoc[int(idx)]['segment_index']
                        transcript_time = search_corpus_assoc[int(idx)]['start']
                        line_no = int(segment_index) + 1
                        all_lines = search_corpus_assoc[int(idx)]['all_lines']

                        # compile the results into the search results dict
                        search_results.append({
                            'search_term': query,
                            'transcription_file_path': transcription_file_path,
                            'idx': int(idx),
                            'segment_index': segment_index,
                            'line_no': line_no,
                            'all_lines': all_lines,
                            'transcript_time': transcript_time,
                            'score': score,
                            'text': search_corpus_phrases[idx]
                        })

            return search_results, top_k

    class TranscriptGroups:
        '''
        This class contains functions for working with transcript groups.
        '''

        def __init__(self, toolkit_ops_obj):

            # define the toolkit operations object
            self.toolkit_ops_obj = toolkit_ops_obj

            # and the stAI object
            self.stAI = toolkit_ops_obj.stAI

        def get_all_transcript_groups(self, transcription_file_path: str) -> dict or None:
            '''
            This function returns a list of transcript groups for a given transcription file.

            :param: transcription_file_path: the path to the transcription file
            :return: a dict of transcript groups or None if the transcription file doesn't exist
            '''

            # load the transcription file
            # get the contents of the transcription file
            transcription_file_data = \
                self.toolkit_ops_obj.get_transcription_file_data(
                    transcription_file_path=transcription_file_path)

            # if the transcription file data was cannot be loaded, return None
            if transcription_file_data is False:
                return None

            # check if the transcription has any transcript groups
            # and return accordingly
            if 'transcript_groups' not in transcription_file_data:
                return {}
            else:
                logger.debug('Transcript groups found in transcription {}'.format(transcription_file_path))
                return transcription_file_data['transcript_groups']

        def get_transcript_group(self, transcription_file_path: str, transcript_group_id: str) -> dict or None:
            '''
            Get a transcript group by its name from a given transcription file.

            The groups are stored in a list in the transcription file.

            :param transcription_file_path:
            :param transcript_group_id:
            :return: a list of transcript groups or None if the transcription file doesn't exist
            '''

            # get the transcript groups
            transcript_groups = self.get_all_transcript_groups(transcription_file_path=transcription_file_path)

            # if the previous call returned None it's likely that the transcription file cannot be loaded
            if transcript_groups is None:
                return None

            # loop through the transcript groups
            # the groups are stored in a list, and each group is a dict, with the group name as the key
            for transcript_group in transcript_groups:

                # if the transcript group name matches the one we're looking for, return it
                if transcript_group_id in transcript_group:
                    return transcript_group[transcript_group_id]

            # if we get here, the transcript group was not found
            return {}

        def save_transcript_groups(self, transcription_file_path: str, transcript_groups: dict,
                                   group_id: str=None) -> dict or bool or None:
            '''
            This function saves transcript groups to a transcription file.

            It will overwrite any existing transcript groups in the transcription file.

            :param transcription_file_path:
            :param transcript_groups:
            :param group_id: If this is passed, we will only save the transcript group with this group id
            :return: The group dict if the groups were saved successfully, False otherwise
                    or None if there were other problems transcription file
            '''

            # first, get the transcription file data
            transcription_file_data = \
                self.toolkit_ops_obj.get_transcription_file_data(
                    transcription_file_path=transcription_file_path)

            # if the transcription file data was cannot be loaded, return None
            if transcription_file_data is None:
                return None

            # if no group id was passed, overwrite all transcript groups
            if group_id is None:

                # overwrite the transcript groups with the passed transcript_groups
                transcription_file_data['transcript_groups'] = transcript_groups

            # otherwise, only focus on the passed group id
            else:

                # one final strip and lower to make sure that the group_id is in the right format
                group_id = group_id.strip().lower()

                # but make sure that it was passed correctly in the transcript_groups dict
                if group_id not in transcript_groups:
                    logger.error('The transcript group id {} was not found in the transcript_groups dict.'
                                 .format(group_id))
                    return False

                # if the transcript groups key doesn't exist, create it
                if 'transcript_groups' not in transcription_file_data:
                    transcription_file_data['transcript_groups'] = {}

                # if the group with the group_id exists, remove it
                if group_id in transcription_file_data['transcript_groups']:
                    del transcription_file_data['transcript_groups'][group_id]

                # now add the transcript group to the transcript groups
                transcription_file_data['transcript_groups'][group_id] = transcript_groups[group_id]

            # save the transcription file data
            saved = self.toolkit_ops_obj.save_transcription_file(
                transcription_file_path=transcription_file_path,
                transcription_data=transcription_file_data,
                backup='backup')

            if not saved:
                return False

            # return the saved transcript groups
            return transcription_file_data['transcript_groups']

        def prepare_transcript_group(self, group_name: str, time_intervals: list,
                                     group_id: str = None, group_notes: str = '',
                                     existing_transcript_groups: list = None,
                                     overwrite_existing: bool = False) -> dict:
            '''
            This function prepares a transcript group dict.

            Each group is a dict with the following keys: name, notes, time_intervals

            The purpose is to be able to group together segments of a transcription, although the start and end times
            of the groups are not necessarily always the same as the start and end times of the segments.

            :param group_name:
            :param time_intervals:
            :param group_id:
            :param group_notes:
            :param existing_transcript_groups: if a transcript group is being updated, pass its contents here
            :param overwrite_existing: if the same group_id is found in the existing transcript groups, overwrite it
            :return: the transcript group dict or None if something went wrong
            '''

            # trim the group name and group notes
            group_name = group_name.strip()
            group_notes = group_notes.strip()

            # if the group id is not provided, use the group name
            if group_id is None:

                # generate a group id
                group_id = str(group_name).lower()

            group_id = group_id.lower()

            # if we're not overwriting an existing group, see if the group id already exists in existing groups
            if not overwrite_existing \
                    and existing_transcript_groups is not None \
                    and type(existing_transcript_groups) is list \
                    and len(existing_transcript_groups) > 0:

                # keep coming up with group id suffixes until we find one that doesn't exist
                group_name_suffix = 1
                while True:

                    # first try the group name as is
                    if group_name_suffix != 1:

                        # but after the first iteration, add a suffix (should start at 2)
                        group_id = group_name.lower() + '_' + str(group_name_suffix)

                    # if the group id doesn't exist in the existing groups, break out of the loop
                    # (convert all to lowercase for comparison to avoid any sort of case sensitivity issues)
                    if str(group_id).lower() not in list(map(str.lower, existing_transcript_groups)):
                        break

                    # if the group id already exists, increment the suffix and try again
                    group_name_suffix += 1

            # return the prepared transcript group
            return {
                group_id: {
                    'name': group_name,
                    'notes': group_notes,
                    'time_intervals': time_intervals
                }
            }

        def segments_to_groups(self, segments: list, group_name: str, group_id: str = None,
                               group_notes: str = '', existing_transcript_groups: list = None,
                               overwrite_existing: bool = False) -> dict or None:
            '''
            This function converts a list of transcript segments to a transcript group

            :param segments: a list of transcript segments
            :param group_name: the name of the transcript group
            :param group_id: the id of the transcript group
            :param group_notes: the notes of the transcript group
            :param existing_transcript_groups: if a transcript group is being updated, pass its contents here
            :param overwrite_existing: if the same group_id is found in the existing transcript groups, overwrite it
            :return: the transcript group dict or None if something went wrong
            '''

            # first, get the time intervals from the segments
            group_time_intervals = []

            # if the segments are empty or not a list, return None
            if segments is None or type(segments) is not list:
                return None

            # get a proper list of time intervals based on the segments
            group_time_intervals = self.toolkit_ops_obj.transcript_segments_to_time_intervals(segments=segments)

            if group_time_intervals is None:
                return None

            # if the time intervals are empty, return None
            if len(group_time_intervals) == 0:
                return None

            # prepare the transcript group
            transcript_group = \
                self.prepare_transcript_group(
                    group_name=group_name,
                    time_intervals=group_time_intervals,
                    group_id=group_id,
                    group_notes=group_notes,
                    existing_transcript_groups=existing_transcript_groups,
                    overwrite_existing=overwrite_existing)

            return transcript_group

        def save_segments_as_group_in_transcription_file(self,
                                                         transcription_file_path: str,
                                                         segments: list,
                                                         group_name: str,
                                                         group_id: str = None,
                                                         group_notes: str = '',
                                                         existing_transcript_groups: list = None,
                                                         overwrite_existing: bool = False) -> str or None:
            '''
            This function saves a list of transcript segments as a group in a transcription file

            The transcription file must already exist in order to save the transcript group.

            :param transcription_file_path:
            :param segments: a list of transcript segments
            :param group_name: the name of the transcript group
            :param group_id: the id of the transcript group
            :param group_notes: the notes of the transcript group
            :param existing_transcript_groups: if a transcript group is being updated, pass its contents here
            :param overwrite_existing: if the same group_id is found in the existing transcript groups, overwrite it
            :return: the transcript group id or None if something went wrong
            '''

            # first, prepare the transcript group
            transcript_group = self.segments_to_groups(segments=segments, group_name=group_name, group_id=group_id,
                                                       group_notes=group_notes,
                                                       existing_transcript_groups=existing_transcript_groups,
                                                       overwrite_existing=overwrite_existing)

            if transcript_group is None or type(transcript_group) is not dict:
                logger.debug('Could not prepare transcript group from segments for saving')
                return None

            # get the group id that may have been generated while creating the transcript group
            group_id = list(transcript_group.keys())[0]

            # finally, save the transcript group
            saved = self.save_transcript_groups(transcription_file_path=transcription_file_path,
                                                transcript_groups=transcript_group, group_id=group_id)

            if not saved:
                logger.debug('Could not save to transcription file {} the following transcript group: {}'.
                    format(transcription_file_path, transcript_group))

            #elif :
            #    saved = group_id

            logger.debug('Saved transcript groups {} to transcription file {}'
                         .format(list(transcript_group.keys()), transcription_file_path))
            return saved

    def time_intervals_to_transcript_segments(self, time_intervals: list, segments: list) -> list or None:
        '''
        This function converts a list of time intervals to a list of transcript segments

        :param time_intervals: a list of time intervals
        :param segments: a dict of transcript segments
        :return: a list of transcript segments
        '''

        # if the time intervals or segments are empty or not a list/dict, return None
        if time_intervals is None or type(time_intervals) is not list \
                or segments is None or type(segments) is not list:
            return None

        # if the time intervals are empty, return None
        if len(time_intervals) == 0:
            return []

        # take all time intervals and check if they overlap with any of the segments
        # if they do, add the segment to the list of segments to return
        segments_to_return = []

        # first sort the time intervals by start time
        time_intervals = sorted(time_intervals, key=lambda x: x['start'])

        # then sort the segments by start time
        segments = sorted(segments, key=lambda x: x['start'])

        # now take all the time intervals and check if they overlap with any of the segments
        for current_time_interval in time_intervals:

            # test this time interval against all segments
            for current_segment in segments:

                # if the current time interval overlaps with the current segment, add it to the list of segments
                if current_segment['start'] >= current_time_interval['start'] \
                        and current_segment['end'] <= current_time_interval['end']:

                    segments_to_return.append(current_segment)

                # otherwise, if the current segment is after the current time interval, break
                # this only works if the segments and time intervals have been sorted
                elif current_segment['start'] > current_time_interval['end']:
                    break

        return segments_to_return




    def transcript_segments_to_time_intervals(self, segments: list) -> list or None:
        '''
        This function takes a list of transcript segments, groups them together if they don't have
        any gaps between them.
        :param segments:
        :return: the list of time intervals or None if something went wrong
        '''

        # if the segments are not empty or not a dict, return None
        if segments is None or type(segments) is not list or len(segments) == 0:
            logger.debug('Could not convert transcript segments to time intervals '
                         'because the segments are empty or not a list')
            return None

        # these are the group time intervals that we'll return eventually
        # this group will consist of multiple time intervals taken from transcript segments that
        # are next to each other (end_time of previous segment matches the start_time of current segment)
        time_intervals = [{}]

        time_interval_num = 0

        # remove duplicates from segments
        # this is important because if there are duplicates, the time intervals might repeat
        segments_unique = []
        [segments_unique.append(x) for x in segments if x not in segments_unique]

        # place the unique segments back into the original list
        segments = segments_unique

        # sort the segments by start time
        segments = sorted(segments, key=lambda x: x['start'])

        # loop through the segments
        for current_segment in segments:

            # print('current segment {}-{}: {}'
            #       .format(current_segment['start'], current_segment['end'], current_segment['text']))

            # if the current time interval doesn't have a start time, add it
            # (i.e. this segment is the first in this time interval)
            if 'start' not in time_intervals[time_interval_num]:
                time_intervals[time_interval_num]['start'] = current_segment['start']

            # if the end time of the current time_interval matches the start time of the current segment,
            # it means that there's no gap between the current time_interval and the current segment,
            # so add the current segment to the current time interval, by simply updating the end time
            # this extends the time interval to include the current segment too
            if 'end' not in time_intervals[time_interval_num] or \
                    time_intervals[time_interval_num]['end'] == current_segment['start']:

                time_intervals[time_interval_num]['end'] = current_segment['end']

            # otherwise, it means that the current segment is not next to the current time interval,
            # so start a new time interval containing the current segment
            else:
                time_interval_num += 1
                time_intervals.append({
                    'start': current_segment['start'],
                    'end': current_segment['end']
                })

        return time_intervals

    def get_whisper_available_languages(self) -> list or None:

        available_languages = whisper_tokenizer.LANGUAGES.values()

        if not available_languages or available_languages is None:
            available_languages = []

        return sorted(available_languages)

    def get_torch_available_devices(self) -> list or None:

        # prepare a list of available devices
        available_devices = ['auto', 'cpu']

        # and add cuda to the available devices, if it is available
        if torch.cuda.is_available():
            available_devices.append('CUDA')

        return available_devices

    def whisper_device_select(self, device):
        '''
        A standardized way of selecting the right whisper device
        :param device:
        :return:
        '''

        # if the whisper device is set to cuda
        if self.whisper_device in ['cuda', 'CUDA', 'gpu', 'GPU']:
            # use CUDA if available
            if torch.cuda.is_available():
                self.whisper_device = device = torch.device('cuda')
            # or let the user know that cuda is not available and switch to cpu
            else:
                logger.error('CUDA not available. Switching to cpu.')
                self.whisper_device = device = torch.device('cpu')
        # if the whisper device is set to cpu
        elif self.whisper_device in ['cpu', 'CPU']:
            self.whisper_device = device = torch.device('cpu')
        # any other setting, defaults to automatic selection
        else:
            # use CUDA if available
            self.whisper_device = device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        logger.info('Using {} for Torch / Whisper.'.format(device))

        return self.whisper_device

    def prepare_transcription_file(self, toolkit_UI_obj=None, task=None, unique_id=None,
                                   retranscribe=False, time_intervals=None, select_files=False):
        '''
        This asks the user where to save the transcribed files,
         it chooses between transcribing an existing timeline (and first starting the render process)
         and then passes the file to the transcription config

        :param toolkit_UI_obj:
        :param task:
        :param audio_file:
        :return: bool
        '''

        # check if there's a UI object available
        if not self.is_UI_obj_available(toolkit_UI_obj):
            logger.error('No UI object available, aborting')
            return False

        # get info from resolve
        try:
            resolve_data = self.resolve_api.get_resolve_data()
        # in case of exception still create a dict with an empty resolve object
        except:
            resolve_data = {'resolve': None}

        # set an empty target directory for future use
        target_dir = ''

        # if retranscribe is True, we're going to use an existing transcription item
        if retranscribe:

            # hope that the retranscribe attribute is the transcription file path too
            if os.path.isfile(str(retranscribe)):

                transcription_file_path = str(retranscribe)

                # open the transcription file
                transcription_data = self.get_transcription_file_data(transcription_file_path)

                # prepare an empty audio file path
                audio_file_path = None

                # make sure the audio file path is in the transcription data and that the audio file exists
                if 'audio_file_path' in transcription_data:

                    # set the target directory to the transcription file path
                    target_dir = os.path.dirname(transcription_file_path)

                    # set the audio file path
                    audio_file_path = os.path.join(target_dir, transcription_data['audio_file_path'])

                    # check if the audio file exists
                    if not os.path.isfile(audio_file_path):
                        audio_file_path = None


                # if no audio file was found, notify the user
                if audio_file_path is None:
                    audio_file_error = 'The audio file path is not in the transcription file ' \
                                       'or the audio file cannot be found.'
                    if self.is_UI_obj_available():
                        self.toolkit_UI_obj.notify_via_messagebox(type='error',
                                                                  message=audio_file_error)
                    else:
                        logger.error(audio_file_error)
                    return False


                # get the transcription name from the transcription file
                name = transcription_data['name'] if 'name' in transcription_data else ''

                # a unique id is also useful to keep track of stuff
                unique_id = self._generate_transcription_unique_id(name=name)

                # now open up the transcription settings window
                self.start_transcription_config(audio_file_path=audio_file_path,
                                                name=name,
                                                task=task,
                                                unique_id=unique_id,
                                                transcription_file_path=transcription_file_path,
                                                time_intervals=time_intervals)

        # if Resolve is available and the user has an open timeline, render the timeline to an audio file
        # but only if select files is False
        elif not select_files and resolve_data['resolve'] != None and 'currentTimeline' in resolve_data and \
                resolve_data['currentTimeline'] != '' and resolve_data['currentTimeline'] is not None:

            # reset any potential yes that the user might have said when asked to continue without resolve
            toolkit_UI_obj.no_resolve_ok = False

            # did we ever save a target dir for this project?
            last_target_dir = self.stAI.get_project_setting(project_name=current_project, setting_key='last_target_dir')

            # ask the user where to save the files
            while target_dir == '' or not os.path.exists(os.path.join(target_dir)):
                logger.info("Prompting user for render path.")
                target_dir = toolkit_UI_obj.ask_for_target_dir(target_dir=last_target_dir)

                # remember this target_dir for the next time we're working on this project
                # (but only if it was selected by the user)
                if target_dir and target_dir != last_target_dir:
                    self.stAI.save_project_setting(project_name=current_project,
                                                   setting_key='last_target_dir', setting_value=target_dir)

                # cancel if the user presses cancel
                if not target_dir:
                    logger.info("User canceled transcription operation.")
                    return False

            # get the current timeline from Resolve
            currentTimelineName = resolve_data['currentTimeline']['name']

            # generate a unique id to keep track of this file in the queue and transcription log
            if unique_id is None:
                unique_id = self._generate_transcription_unique_id(name=currentTimelineName)

            # update the transcription log
            # @todo this doesn't work - maybe because resolve polling is hanging the main thread
            self.add_to_transcription_log(unique_id=unique_id, name=currentTimelineName, status='rendering')

            # use transcription_WAV render preset if it exists
            # transcription_WAV is an audio only custom render preset that renders Linear PCM codec in a Wave format
            # instead of Quicktime mp4; this is just to work with wav files instead of mp4 to improve compatibility.
            # but the user needs to add it manually to resolve in order for it to work since the Resolve API
            # doesn't permit choosing the audio format (only the codec)
            render_preset = self.stAI.get_app_setting(setting_name='transcription_render_preset',
                                                      default_if_none='transcription_WAV')

            # let the user know that we're starting the render
            toolkit_UI_obj.notify_via_os("Starting Render", "Starting Render in Resolve",
                                         "Saving into {} and starting render.".format(target_dir))

            # render the timeline in Resolve
            rendered_files = self.resolve_api.render_timeline(target_dir, render_preset, True, False, False, True)

            if not rendered_files:
                self.update_transcription_log(unique_id=unique_id, **{'status': 'failed'})
                logger.error("Timeline render failed.")
                return False

            # now open up the transcription settings window
            for rendered_file in rendered_files:
                self.start_transcription_config(audio_file_path=rendered_file,
                                                name=currentTimelineName,
                                                task=task, unique_id=unique_id)

        # if resolve is not available or select_files is True, ask the user to select an audio file
        else:

            # ask the user if they want to simply transcribe a file from the drive
            if select_files or toolkit_UI_obj.no_resolve_ok \
                    or messagebox.askyesno(message='A Resolve Timeline is not available.\n\n'
                                                    'Do you want to transcribe existing audio files instead?'):

                # remember that the user said it's ok to continue without resolve
                toolkit_UI_obj.no_resolve_ok = True

                # ask the user for the target files
                target_files = toolkit_UI_obj.ask_for_target_file(multiple=True)

                # add it to the transcription list
                if target_files:

                    for target_file in target_files:

                        # the file name also becomes currentTimelineName for future use
                        file_name = os.path.basename(target_file)

                        # a unique id is also useful to keep track
                        unique_id = self._generate_transcription_unique_id(name=file_name)

                        # now open up the transcription settings window
                        self.start_transcription_config(audio_file_path=target_file,
                                                        name=file_name,
                                                        task=task, unique_id=unique_id)

                    return True

                # or close the process if the user canceled
                else:
                    return False

            # close the process if the user doesn't want to transcribe an existing file
            else:
                return False

    def start_transcription_config(self, audio_file_path=None, name=None, task=None,
                                   unique_id=None, transcription_file_path=False,
                                   time_intervals=None, excluded_time_intervals=None):
        '''
        Opens up a window to allow the user to configure and start the transcription process for each file
        :return:
        '''

        # check if there's a UI object available
        if not self.is_UI_obj_available():
            logger.error('No UI object available.')
            return False

        # if no transcription_file_path was passed, start a new transcription
        if not transcription_file_path:
            title = "Transcription Settings: " + name

        # if a transcription_file_path was passed, we're going to perform a re-transcription
        else:
            title = "Transcription Settings: " + name + " (re-transcribe)"

        # open up the transcription settings window via Toolkit_UI
        return self.toolkit_UI_obj.open_transcription_settings_window(title=title,
                                                                      name=name,
                                                                      audio_file_path=audio_file_path, task=task,
                                                                      unique_id=unique_id,
                                                                      transcription_file_path=transcription_file_path,
                                                                      time_intervals=time_intervals,
                                                                      excluded_time_intervals=excluded_time_intervals
                                                                      )

    def add_to_transcription_log(self, unique_id=None, **attribute):
        '''
        This adds items to the transcription log and opens the transcription log window
        :param toolkit_UI_obj:
        :param unique_id:
        :param attribute:
        :return:
        '''
        # if a unique id was passed, add the file to the log
        if unique_id:

            # then simply update the item by passing everything to the update function
            self.update_transcription_log(unique_id, **attribute)

            # finally open or focus the transcription log window
            if self.is_UI_obj_available():
                self.toolkit_UI_obj.open_transcription_log_window()

            return True

        else:
            logger.warning('Missing unique id when trying to add item to transcription log.')
            return False

    def update_transcription_log(self, unique_id=None, **attributes):
        '''
        Updates items in the transcription log (or adds them if necessary)
        The items are identified by unique_id and only the passed attributes will be updated
        :param unique_id:
        :param options:
        :return:
        '''
        if unique_id:

            # add the item to the transcription log if it's not already in there
            if unique_id not in self.transcription_log:
                self.transcription_log[unique_id] = {}

        # the transcription log items will contain things like
        # name, status, audio_file_path etc.
        # these attributes are set using the self.transcription_item_attr variable

        # use the passed attribute to populate the transcription log entry
        if attributes:
            for attribute in attributes:
                # but only use said option if it was mentioned in the transcription_item_attr
                if attribute in self.transcription_item_attr:
                    # populate the transcription log
                    self.transcription_log[unique_id][attribute] = attributes[attribute]

        # whenever the transcription log is updated, make sure you update the window too
        # but only if the UI object exists
        if self.is_UI_obj_available():
            self.toolkit_UI_obj.update_transcription_log_window()

    def transcription_queue_attr(self, attributes):
        '''
        Cleans up the attributes passed to the transcription queue
        :param attributes:
        :return:
        '''

        # define the permitted attributes
        permitted_attributes = ['task', 'audio_file_path', 'name', 'language', 'model', 'device', 'unique_id',
                                'transcription_file_path', 'time_intervals', 'excluded_time_intervals', 'initial_prompt'
                                ]

        clean_attributes = {}

        # re-create the attributes dict with only the permitted attributes
        for attribute in attributes:
            if attribute in permitted_attributes:
                clean_attributes[attribute] = attributes[attribute]

        return clean_attributes

    def add_to_transcription_queue(self, task=None, audio_file_path=None,
                                   name=None, language=None, model=None, device=None,
                                   unique_id=None, initial_prompt=None,
                                   time_intervals=None, excluded_time_intervals=None, transcription_file_path=None,
                                   save_queue=True):
        '''
        Adds files to the transcription queue and then pings the queue in case it's sleeping.
        It also adds the files to the transcription log
        :param toolkit_UI_obj:
        :param translate:
        :param audio_file_path:
        :param name:
        :return:
        '''

        # check if there's a UI object available
        # if not self.is_UI_obj_available(toolkit_UI_obj):
        #     return False

        # select the transcribe task automatically if neither transcribe or translate was passed
        if task is None or task not in ['transcribe', 'translate', 'transcribe+translate']:
            task = 'transcribe'

        # if it's a regular transcribe or translate task
        if task in ['transcribe', 'translate']:

            # just do that task
            tasks = [task]

        # if the user is asking for a transcribe+translate
        elif task == 'transcribe+translate':
            # add both tasks
            tasks = ['transcribe', 'translate']

        # we will never get to this, but let's have it
        else:
            return False

        # to count tasks we need an int
        task_num = 0

        # add all the above tasks to the queue
        for c_task in tasks:

            task_num = task_num+1

            # generate a unique id if one hasn't been passed
            if unique_id is None:
                next_queue_id = self._generate_transcription_unique_id(name=name)
            else:

                # if a unique id was passed, only use it for the first task
                next_queue_id = unique_id

                # then reset it
                unique_id = None

            # add numbering to names, but starting with the second task
            if task_num > 1:
                c_name = name + ' ' + str(task_num)
            else:
                c_name = name

            # add to transcription queue if we at least know the path and the name of the timeline/file
            if next_queue_id and audio_file_path and os.path.exists(audio_file_path) and name:

                file_dict = {'name': c_name, 'audio_file_path': audio_file_path, 'task': c_task,
                             'language': language, 'model': model, 'device': device,
                             'initial_prompt': initial_prompt,
                             'time_intervals': time_intervals,
                             'excluded_time_intervals': excluded_time_intervals,
                             'transcription_file_path': transcription_file_path,
                             'status': 'waiting', 'info': None}

                # add to transcription queue
                self.transcription_queue[next_queue_id] = file_dict

                # write transcription queue to file
                if save_queue:
                    self.save_transcription_queue()

                # add the file to the transcription log too (the add function will check if it's already there)
                self.add_to_transcription_log(unique_id=next_queue_id, **file_dict)

                # now ping the transcription queue in case it's sleeping
                self.ping_transcription_queue()

            else:
                logger.error('Missing parameters to add file to transcription queue')
                return False

            # throttle for a bit to avoid unique id unique id collisions
            time.sleep(0.01)

        return True

    def resume_transcription_queue_from_file(self):
        '''
        Reads the transcription queue from file and adds all the items to the queue
        :return:
        '''

        # if the file exists, read it
        try:
            if os.path.exists(self.TRANSCRIPTION_QUEUE_FILE_PATH):
                with open(self.TRANSCRIPTION_QUEUE_FILE_PATH, 'r') as f:
                    transcription_queue = json.load(f)

                resume = False

                if transcription_queue and len(transcription_queue) > 0:

                    # add each element to the transcription queue
                    for unique_id in transcription_queue:

                        # clean up the attributes
                        transcription_queue_attributes = self.transcription_queue_attr(transcription_queue[unique_id])

                        # add item to the transcription queue
                        # but do not save the queue to the file again (since we're reading everything from the file) -
                        #  - this is also to prevent deleting the items that are currently being transcribed, but are
                        #    no longer in the app memory queue (self.transcription_queue)
                        self.add_to_transcription_queue(unique_id=unique_id, save_queue=False,
                                                        **transcription_queue_attributes)

                        resume = True

                return resume

            else:
                return False

        except Exception as e:
            logger.error('Error reading transcription queue from file: {}'.format(e))
            return False

    def save_transcription_queue(self):
        '''
        Saves the transcription queue to a file
        :return:
        '''

        transcription_queue = {}

        # first add the current item in the dictionary that will be saved to file
        # this is to prevent losing track of the item that is currently being transcribed if the app crashes
        # because normally, it's not in the queue memory anymore (self.transcription_queue), but it's also not done yet
        if self.transcription_queue_current_item is not None and self.transcription_queue_current_item != {}:
            transcription_queue = self.transcription_queue_current_item

        # then add the rest of the items in the queue
        transcription_queue = transcription_queue | self.transcription_queue

        # save the transcription queue as json to a file
        try:
            with open(self.TRANSCRIPTION_QUEUE_FILE_PATH, 'w') as f:
                json.dump(transcription_queue, f, indent=4)
                return True

        except Exception as e:
            logger.error('Could not save transcription queue to file: {}'.format(e))
            return False

    def _generate_transcription_unique_id(self, name=None):
        if name:
            return name + '-' + str(int(time.time()))
        else:
            return str(int(time.time()))

    def ping_transcription_queue(self):
        '''
        Checks if there are files waiting in the transcription queue and starts the transcription queue thread,
        if there isn't a thread already running
        :return:
        '''

        # if there are files in the queue
        if self.transcription_queue:
            # logger.info('Files waiting in queue for transcription:\n {} \n'.format(self.transcription_queue))

            # check if there's an active transcription thread
            if self.transcription_queue_thread is not None:
                logger.info('Currently transcribing: {}'.format(self.transcription_queue_current_name))

            # if there's no active transcription thread, start it
            else:
                # take the first file in the queue:
                next_queue_id = list(self.transcription_queue.keys())[0]

                # update the status of the item in the transcription log
                self.update_transcription_log(unique_id=next_queue_id, **{'status': 'preparing'})

                # and now start the transcription thread with it
                self.transcription_queue_thread = Thread(target=self.transcribe_from_queue,
                                                         args=(next_queue_id,)
                                                         )
                self.transcription_queue_thread.start()

                # delete this file from the queue
                # (but we will write the changed queue to the transcription queue file
                #  only after the transcription of this file is done - this way, if the process crashes,
                #  on restart, the app will start the queue with this file)
                del self.transcription_queue[next_queue_id]

            return True

        # if there are no more files left in the queue, stop until something pings it again
        else:
            logger.info('Transcription queue empty. Going to sleep.')
            return False

    def transcribe_from_queue(self, queue_id):

        # define queue attributes
        queue_attr = {}

        # get file info from queue
        queue_attr['name'], \
        queue_attr['audio_file_path'], \
        queue_attr['task'], \
        queue_attr['language'], \
        queue_attr['model'], \
        queue_attr['device'], \
        queue_attr['initial_prompt'], \
        queue_attr['time_intervals'], \
        queue_attr['excluded_time_intervals'], \
        queue_attr['transcription_file_path'],\
        info \
            = self.get_queue_file_info(queue_id)

        logger.info("Starting to transcribe {}".format(queue_attr['name']))

        # keep track of the name of the item that is currently being transcribed
        self.transcription_queue_current_name = queue_attr['name']

        # keep track of the item that is currently being transcribed
        self.transcription_queue_current_item = {queue_id: queue_attr}

        import traceback

        # transcribe the file via whisper
        try:
            self.whisper_transcribe(queue_id=queue_id, **queue_attr)

        # in case the transcription process crashes
        except Exception:
            # show error
            logger.error(traceback.format_exc())
            # update the status of the item in the transcription log
            self.update_transcription_log(unique_id=queue_id, **{'status': 'failed'})

        # reset the transcription thread and name:
        self.transcription_queue_current_name = None
        self.transcription_queue_thread = None
        self.transcription_queue_current_item = {}

        # re-write the transcription queue to file if the file was transcribed
        self.save_transcription_queue()

        # then ping the queue again
        self.ping_transcription_queue()

        return False

    def get_queue_file_info(self, queue_id):
        '''
        Returns the file info stored in a queue given the correct queue_id
        :param queue_id:
        :return: list or False
        '''
        if self.transcription_queue and queue_id in self.transcription_queue:
            queue_file = self.transcription_queue[queue_id]
            return [queue_file['name'], queue_file['audio_file_path'], queue_file['task'],
                    queue_file['language'], queue_file['model'], queue_file['device'],
                    queue_file['initial_prompt'],
                    queue_file['time_intervals'],
                    queue_file['excluded_time_intervals'],
                    queue_file['transcription_file_path'],
                    queue_file['info']]

        return False

    def split_audio_by_intervals(self, audio_array, time_intervals=None, sr=16_000):
        """
        Splits the audio_array according to the time_intervals
        and returns a audio_segments list with multiple audio_arrays
        together with the time_intervals passed to the function
        """

        # reset the audio segments list
        audio_segments = []

        # if there are time segments
        if time_intervals is not None and time_intervals \
                and type(time_intervals) == list and len(time_intervals) > 0:

            # sort the audio segments by start time
            time_intervals = sorted(time_intervals, key=lambda x: x[0])

            # take each time segment
            for time_interval in time_intervals:
                # calculate duration based on start and end times!!

                # and add it to an audio segments list
                # the format is [start_time, end_time, audio_array]
                audio_segment = [time_interval[0],
                                 time_interval[1],
                                 audio_array[int(time_interval[0] * sr): int(time_interval[1] * sr)]
                                 ]

                audio_segments.append(audio_segment)
            return audio_segments, time_intervals

        # if time_intervals is empty, define it as a single segment,
        # from the beginning to the end (i.e. we're transcribing the full audio)
        time_intervals = [[0, len(audio_array) / sr]]
        audio_segments = [[0, len(audio_array / sr), audio_array]]
        return audio_segments, time_intervals

    def whisper_transcribe_segments(self, audio_segments, task, next_segment_id, other_whisper_options):
        """
        Transcribes only the passed audio segments
        and offsets the transcription segments start and end times

        Only returns the transcription segments
        """

        results = {'segments': []}

        # this will be counted up for each segment to provide a unique id
        id_count = 0

        # transcribe each audio segment
        for audio_segment in audio_segments:

            # run whisper transcribe on the audio segment
            result = self.whisper_model.transcribe(audio_segment[2],
                                                   task=task,
                                                   verbose=True,
                                                   **other_whisper_options
                                                   )

            # now process the result and add the original start time offset
            # to each transcript segment start and end times

            # if there are segments in the result
            if 'segments' in result and result['segments']:

                # take each segment and add the offset to the start and end time
                for i, transcript_segment in enumerate(result['segments']):
                    transcript_segment['start'] += audio_segment[0]
                    transcript_segment['end'] += audio_segment[0]

                    # avoid end time being larger than the interval end time
                    # - there seems to be an issue in the whisper model:
                    #   https://github.com/openai/whisper/discussions/357
                    if transcript_segment['end'] > audio_segment[1]:
                        transcript_segment['end'] = audio_segment[1]

                    # also avoid start time being smaller than the interval start time
                    if transcript_segment['start'] < audio_segment[0]:
                        transcript_segment['start'] = audio_segment[0]

                    transcript_segment['id'] = next_segment_id + id_count
                    id_count += 1

                    # update the segment in the result
                    #result['segments'][i] = transcript_segment

                    # add the transcription of the audio segment to the results list
                    results['segments'].append(transcript_segment)

        return results

    def exclude_segments_by_intervals(self, audio_array, time_intervals, excluded_time_intervals, sr):
        """
        Excludes certain audio segments from audio_array according to the excluded_time_intervals
        and returns a new audio_array with the excluded segments removed
        """

        # if there are exclusion time segments and time_intervals
        if excluded_time_intervals and type(excluded_time_intervals) == list and len(excluded_time_intervals) > 0\
                and time_intervals and type(time_intervals) == list and len(time_intervals) > 0:

            # sort the excluded segments by start time
            excluded_time_intervals = \
                sorted(excluded_time_intervals, key=lambda x: x[0])

            # take each time segment
            for excluded_time_interval in excluded_time_intervals:

                # and check it against each of the time segments we selected for transcription
                for time_interval in time_intervals:

                    # if the exclusion is outside the current segment times
                    if excluded_time_interval[1] <= time_interval[0] \
                            or excluded_time_interval[0] >= time_interval[1]:
                        continue

                    # if the exclusion is exactly as the current segment times
                    elif time_interval[0] == excluded_time_interval[0] \
                            and time_interval[1] == excluded_time_interval[1]:

                        # simply remove the whole segment
                        time_intervals.remove(time_interval)

                    else:

                        # if the exclusion start time is equal to the segment start time
                        if excluded_time_interval[0] == time_interval[0]:

                            # cut out the beginning of the segment
                            # by using the end time of the exclusion as its start
                            time_interval[0] = excluded_time_interval[1]


                        # if the exclusion end time is equal to the segment end time
                        elif excluded_time_interval[1] == time_interval[1]:

                            # cut out the end of the segment
                            # by using the start time of the exclusion as its end
                            time_interval[1] = excluded_time_interval[0]


                        # if the exclusion is in the middle of the segment
                        elif excluded_time_interval[0] > time_interval[0] \
                                and excluded_time_interval[1] < time_interval[1]:

                            # remove the segment from the list
                            time_intervals.remove(time_interval)

                            # but then split it into two segments
                            # first the segment until the exclusion
                            time_intervals.append([time_interval[0], excluded_time_interval[0]])

                            # then the segment from the exclusion
                            time_intervals.append([excluded_time_interval[1], time_interval[1]])

            # sort the selection by start time
            time_intervals = sorted(time_intervals, key=lambda x: x[0])

        # now split the audio using the newly created intervals
        audio_segments, time_intervals = self.split_audio_by_intervals(audio_array, time_intervals, sr)

        return audio_segments, time_intervals

    def whisper_transcribe(self, name=None, audio_file_path=None, task=None,
                           target_dir=None, queue_id=None, **other_whisper_options):

        # don't continue unless we have a queue_id
        if audio_file_path is None or not audio_file_path:
            return False

        # use the name of the file in case the name wasn't passed
        if name is None:
            name = os.path.basename(audio_file_path)

        # use the directory where the file is stored if another one wasn't passed
        if target_dir is None:
            target_dir = os.path.dirname(audio_file_path)

        # what is the name of the audio file
        audio_file_name = os.path.basename(audio_file_path)

        # select the device that was passed (if any)
        if 'device' in other_whisper_options:
            # select the new whisper device
            self.whisper_device = self.whisper_device_select(other_whisper_options['device'])
            del other_whisper_options['device']

        # load OpenAI Whisper model
        # and hold it loaded for future use (unless another model was passed via other_whisper_options)
        if self.whisper_model is None \
                or ('model' in other_whisper_options and self.whisper_model_name != other_whisper_options['model']):

            # update the status of the item in the transcription log
            self.update_transcription_log(unique_id=queue_id, **{'status': 'loading model'})

            # use the model that was passed in the call (if any)
            if 'model' in other_whisper_options and other_whisper_options['model']:
                self.whisper_model_name = other_whisper_options['model']

            # if the Whisper transformer model was never downloaded, log that we're downloading it
            model_downloaded_before = True
            if self.stAI.get_app_setting(setting_name='whisper_model_downloaded_{}'
                    .format(self.whisper_model_name),
                                         default_if_none=False
                                         ) is False:
                logger.warning('The whisper {} model may need to be downloaded and could take a while '
                               'depending on the Internet connection speed. '
                               .format(self.whisper_model_name)
                               )
                model_downloaded_before = False

            logger.info('Loading Whisper {} model.'.format(self.whisper_model_name))
            try:
                self.whisper_model = whisper.load_model(self.whisper_model_name)
            except Exception as e:
                logger.error('Error loading Whisper {} model: {}'.format(self.whisper_model_name, e))

                # update the status of the item in the transcription log
                self.update_transcription_log(unique_id=queue_id, **{'status': 'failed'})

            # once the model has been loaded, we can note that in the app settings
            # this is a wat to keep track if the model has been downloaded or not
            # but it's not 100% reliable and we may need to find a better way to do this in the future
            if not model_downloaded_before:
                self.stAI.save_config(setting_name='whisper_model_downloaded_{}'.format(self.whisper_model_name),
                                      setting_value=True)

            # let the user know if the whisper model is multilingual or english-only
            logger.info('Selected Whisper model is {}.'.format(
                'multilingual' if self.whisper_model.is_multilingual else 'English-only'
            ))

        # delete the model reference so we don't pass it again in the transcribe function below
        if 'model' in other_whisper_options:
            del other_whisper_options['model']

        # update the status of the item in the transcription log
        self.update_transcription_log(unique_id=queue_id, **{'status': 'transcribing'})

        # let the user know the transcription process has started
        notification_msg = "Transcribing {}.\nThis may take a while.".format(name)
        if self.is_UI_obj_available():
            self.toolkit_UI_obj.notify_via_os("Starting Transcription",
                                              notification_msg,
                                              debug_message="Transcribing {}. This may take a while.".format(name))
        else:
            logger.info(notification_msg)

        start_time = time.time()

        # remove empty language
        if 'language' in other_whisper_options and other_whisper_options['language'] == '':
            del other_whisper_options['language']

        # remove empty initial prompt
        if 'initial_prompt' in other_whisper_options and other_whisper_options['initial_prompt'] == '':
            del other_whisper_options['initial_prompt']

        # load audio file as array using librosa
        # this should work for most audio formats (so ffmpeg might not be needed at all)
        audio_array, sr = librosa.load(audio_file_path, sr=16_000)

        # if time_intervals was passed, only transcribe those time intervals from the audio file
        if 'time_intervals' in other_whisper_options:
            time_intervals = other_whisper_options['time_intervals']
            del other_whisper_options['time_intervals']

        # otherwise assume no time intervals
        else:
            time_intervals = None

        # split the audio into segments according to the time intervals
        # in case no time intervals were passed, this will just return one audio segment with the whole audio
        audio_segments, time_intervals = self.split_audio_by_intervals(audio_array, time_intervals, sr)

        # exclude time intervals that need to be excluded
        if 'excluded_time_intervals' in other_whisper_options:
            audio_segments, time_intervals = self.exclude_segments_by_intervals(
                audio_array, time_intervals, other_whisper_options['excluded_time_intervals'], sr=sr
            )
            del other_whisper_options['excluded_time_intervals']

        # create an empty list to load existing transcription data (or to save the new data)
        transcription_data = {}

        existing_transcription = False

        # ignore the transcription file path if it's empty
        if 'transcription_file_path' in other_whisper_options \
            and other_whisper_options['transcription_file_path'] is None:

            del other_whisper_options['transcription_file_path']

        # load the transcription data from the file if a path was passed
        elif 'transcription_file_path' in other_whisper_options:

            if other_whisper_options['transcription_file_path'].strip() != '':

                transcription_file_path = other_whisper_options['transcription_file_path']

                # load the transcription data from the file
                transcription_data = self.get_transcription_file_data(transcription_file_path)

                # mark that we're using existing transcription data (re-transcribing)
                # and remember the name of the transcription file
                existing_transcription = transcription_file_path

                # change the status of the item in the transcription log to re-transcribing
                self.update_transcription_log(unique_id=queue_id, **{'status': 're-transcribing'})

            del other_whisper_options['transcription_file_path']

        # get the next id based on the largest id from transcription_data segments
        if type(transcription_data) == dict and 'segments' in transcription_data:
            next_segment_id = max([int(segment['id']) for segment in transcription_data['segments']]) +1
        else:
            next_segment_id = 0

        # transcribe the audio segments
        # (or just one audio segment with the whole audio if no time intervals were passed)
        try:
            result = self.whisper_transcribe_segments(audio_segments=audio_segments,
                                                      task=task,
                                                      next_segment_id=next_segment_id,
                                                      other_whisper_options=other_whisper_options
                                                      )
        except Exception as e:
            logger.error('Error transcribing audio using Whisper: {}'.format(e))

            # update the status of the item in the transcription log
            self.update_transcription_log(unique_id=queue_id, **{'status': 'failed'})

        # update the transcription data with the new segments
        # but first remove all the segments between the time intervals that were passed
        if type(transcription_data) is dict and 'segments' in transcription_data:

            # for each time interval, remove all the segments that are between the start and end of the interval
            for time_interval in time_intervals:

                # get the start and end of the time interval
                start_time = time_interval[0]
                end_time = time_interval[1]

                # remove all the segments that are between the start and end of the time interval
                transcription_data['segments'] = [segment for segment in transcription_data['segments'] if
                                                  segment['start'] < start_time or segment['end'] > end_time]

                # if we have segments in result, add them to the transcription data
                if type(result) is dict and 'segments' in result:

                    # add the new segments to the transcription data
                    transcription_data['segments'] += [segment for segment in result['segments']
                                                        if  segment['start'] >= start_time
                                                        and segment['end'] <= end_time]

            # now make sure that the segments are sorted by start time
            transcription_data['segments'] = sorted(transcription_data['segments'], key=lambda k: k['start'])

        # perform speaker diarization if requested
        # self.speaker_diarization(audio_file_path)

        # let the user know that the speech was processed
        notification_msg = "Finished transcription for {} in {} seconds".format(name,
                                                                                round(time.time() - start_time))

        if self.is_UI_obj_available():
            self.toolkit_UI_obj.notify_via_os("Finished Transcription", notification_msg, notification_msg)
        else:
            logger.info(notification_msg)

        # update the status of the item in the transcription log
        self.update_transcription_log(unique_id=queue_id, **{'status': 'saving files'})

        # WHAT HAPPENS FROM HERE

        # Once a transcription is completed, you should see 4 or 5 files:
        # - the original audio file used for transcription (usually WAV)
        # - if the file was rendered from resolve, a json file - which is kind of like a report card for what was
        #   rendered from where (see mots_resolve.py render())
        # - the resulting transcription.json file with the actual transcription
        # - the plain text transcript in TXT format - transcript.txt
        # - the transcript in SRT format, ready to be imported in Resolve (or other apps)
        #
        # Once these are written, the transcription.json file should be used to gather any further information saved
        # within the tool, therefore it's important to also mention the 3 other files within it (txt, srt, wav). But,
        # with this approach we need to keep in mind to always keep the other 3 files next to the transcription.json
        # to ensure that the files can migrate between different machines and the links won't break.
        #
        # Furthermore, the same file will be used to save any other information related to the transcription.)

        # if we're not updating an older transcription file
        if not existing_transcription or type(existing_transcription) is not str:

            # first determine if there's another transcription.json file with the same name
            # and keep adding numbers to it until the name is free
            file_name = audio_file_name
            file_num = 2
            while os.path.exists(os.path.join(target_dir, file_name + '.transcription.json')):
                file_name = audio_file_name + "_{}".format(file_num)
                file_num = file_num+1

            # also create the transcription data dictionary
            transcription_data = result

        else:
            # for the file name we'll use the name of the existing transcription file,
            # but remove '.transcription.json' from the end
            file_name = os.path.basename(existing_transcription).replace('.transcription.json', '')

        # take the full text from the transcription segments since whisper might have given us a text
        # that is incomplete due to interval splitting
        # this also takes into account the segments that were passed before transcription
        #   (in case of re-transcriptions)
        transcription_data['text'] = ' '.join([segment['text'] for segment in transcription_data['segments']])

        txt_file_path = self.save_txt_from_transcription(file_name=file_name, target_dir=target_dir,
                                                         transcription_data=transcription_data)

        # only save the filename without the absolute path to the transcript json
        transcription_data['txt_file_path'] = os.path.basename(txt_file_path)

        # save the SRT file next to the transcription file
        srt_file_path = self.save_srt_from_transcription(file_name=file_name, target_dir=target_dir,
                                                         transcription_data=transcription_data)

        # only the basename is needed here too
        transcription_data['srt_file_path'] = os.path.basename(srt_file_path)

        # remember the audio_file_path this transcription is based on too
        transcription_data['audio_file_path'] = os.path.basename(audio_file_path)

        # don't forget to add the name of the transcription
        transcription_data['name'] = name

        # and some more info about the transription
        transcription_data['task'] = task
        transcription_data['model'] = self.whisper_model_name

        # add the transcription unique id
        transcription_data['transcription_id'] = queue_id

        # if the transcription data doesn't contain the fps, the timeline name or the start_tc,
        # try to get them from a render.json file
        # these files are saved by the render() function in mots_resolve.py
        if 'timeline_fps' not in transcription_data or transcription_data['timeline_fps'] == '' \
            or 'timeline_start_tc' not in transcription_data or transcription_data['timeline_start_tc'] == '' \
            or 'timeline_name' not in transcription_data or transcription_data['timeline_name'] == '':

            # the render.json file path should be next to the audio file
            # and will have the same name as the audio file, but with .json at the end
            render_json_file_path = os.path.join(os.path.dirname(audio_file_path), file_name+'.json')

            # if the render.json file exists, try to get the data from it
            if os.path.exists(render_json_file_path):
                with open(render_json_file_path, 'r') as render_json_file:
                    render_data = json.load(render_json_file)
                    if 'timeline_fps' not in transcription_data:
                        transcription_data['timeline_fps'] = render_data['fps']
                    if 'timeline_start_tc' not in transcription_data:
                        transcription_data['timeline_start_tc'] = render_data['timeline_start_tc']
                    if 'timeline_name' not in transcription_data:
                        transcription_data['timeline_name'] = render_data['timeline_name']

                logger.debug('Getting timeline data from render json file: {}'.format(render_json_file_path))

            else:
                logger.debug('No render json file found at {}'.format(render_json_file_path))

        # save the transcription file with all the added data
        transcription_json_file_path = self.save_transcription_file(file_name=file_name, target_dir=target_dir,
                                                                    transcription_data=transcription_data)

        # when done, change the status in the transcription log
        # and also add the file paths to the transcription log
        self.update_transcription_log(unique_id=queue_id, status='done',
                                      srt_file_path=transcription_data['srt_file_path'],
                                      txt_file_path=transcription_data['txt_file_path'],
                                      json_file_path=transcription_json_file_path)

        # why not open the transcription in a transcription window if the UI is available?
        if self.is_UI_obj_available():
            self.toolkit_UI_obj.open_transcription_window(title=name,
                                                          transcription_file_path=transcription_json_file_path,
                                                          srt_file_path=srt_file_path)

        return True

    def save_transcription_file(self, transcription_file_path=None, transcription_data=None,
                                file_name=None, target_dir=None, backup=None) -> str or bool:
        '''
        Saves the transcription file either to the transcription_file_path
        or to the "target_dir/name.transcription.json" path

        :param transcription_file_path:
        :param transcription_data:
        :param file_name: This is usually the audio file name
        :param target_dir:
        :param backup: If True, the existing transcription file will be backed up to a .backups folder
                        in the same directory as the transcription file. The backup string will be used as a suffix
                        to the backup file name
        :return: False or transcription_file_path
        '''

        # if no full path was passed
        if transcription_file_path is None:

            # try to use the name and target dir attributes
            if file_name is not None and target_dir is not None:
                # the path should contain the name and the target dir, but end with transcription.json
                transcription_file_path = os.path.join(target_dir, file_name + '.transcription.json')

            # if the name and target_dir were not passed, throw an error
            else:
                logger.error('No transcription file path, name or target dir were passed.')
                return False

        if transcription_file_path:

            # if backup_original is enabled, it will save a copy of the transcription file to
            # originals/[filename].backup.json (if one doesn't exist already)
            if backup and os.path.exists(transcription_file_path):

                import shutil

                # format the name of the backup file
                backup_transcription_file_path = \
                    os.path.splitext(os.path.basename(transcription_file_path))[0]+'.'+str(backup)+'.json'

                backups_dir = os.path.join(os.path.dirname(transcription_file_path), '.backups')

                # if the backups directory doesn't exist, create it
                if not os.path.exists(backups_dir):
                    os.mkdir(backups_dir)

                # copy the existing file to the backups directory
                # if it doesn't already exist
                if not os.path.exists(os.path.join(backups_dir, backup_transcription_file_path)):
                    shutil.copyfile(transcription_file_path,
                                    os.path.join(backups_dir, backup_transcription_file_path))

            # Finally,
            # save the whole whisper result in the transcription json file
            # don't question what is being passed, simply save everything
            with open(transcription_file_path, 'w', encoding='utf-8') as outfile:
                json.dump(transcription_data, outfile)

            return transcription_file_path


        return False

    def get_transcription_file_data(self, transcription_file_path):

        # make sure the transcription exists
        if not os.path.exists(transcription_file_path):
            logger.warning("Transcription file {} not found".format(transcription_file_path))
            return False

        # get the contents of the transcription file
        with codecs.open(transcription_file_path, 'r', 'utf-8-sig') as json_file:
            transcription_json = json.load(json_file)

        # make sure that it's a transcription file
        if 'segments' not in transcription_json:
            logger.warning("The file {} is not a valid transcription file (segments missing)".format(transcription_file_path))
            return False

        return transcription_json

    def time_str_to_seconds(self, time_str: str) -> float:
        '''
        Converts 00:00:00.000 time formats to seconds.
        :param time_str: 00:00:00.000 (string)
        :return:
        '''

        # use regex to get the hours, minutes, seconds and milliseconds
        # from the time string
        time_regex = re.compile(r'(\d{2}):(\d{2}):(\d{2}).(\d)')
        time_match = time_regex.match(time_str)

        # if the time string matches the regex
        if time_match:

            # calculate the seconds
            seconds = int(time_match.group(1)) * 3600 + \
                        int(time_match.group(2)) * 60 + \
                        int(time_match.group(3)) + \
                        int(time_match.group(4)) / 1000

        # otherwise, throw an error
        else:
            exception = 'The passed time string {} is not formatted correctly.'.format(time_str)
            logger.error(exception)

            # throw exception
            raise ValueError(exception)

        return seconds

    def convert_srt_to_transcription_json(self, srt_file_path: str, transcription_file_path: str = None,
                                          overwrite: bool = False):
        '''
        Converts an srt file to a transcription json file, saves it in the same directory
         and returns the name of the transcription file.

        If it's impossible to convert or save the srt file, it will return None

        If overwrite is True, it will overwrite any existing transcription file from the same directory.

        :param srt_file_path:
        :param transcription_file_path:
        :param overwrite:
        :return:
        '''

        # make sure the srt file exists
        if not os.path.exists(srt_file_path):
            logger.warning("SRT file {} doesn't exist.".format(srt_file_path))
            return None

        # get the contents of the srt file
        with codecs.open(srt_file_path, 'r', 'utf-8-sig') as srt_file:
            srt_contents = srt_file.read()

        srt_segments = []
        full_text = ''

        # if properly formatted, the srt file should have 2 new lines between each subtitle
        # so go through all of them
        for line_string in srt_contents.split('\r\n'):

            if line_string != '':

                # if the line is a number, it's the subtitle number
                if line_string.isdigit():
                    idx = int(line_string)

                    # so create a new subtitle segment
                    srt_segments.append({'id': str(idx), 'start': 0.0, 'end': 0.0, 'text': ''})

                # if the line is not a number, it's either the time or the text
                else:
                    # if the line contains '-->', it's the time
                    if '-->' in line_string:
                        # split the line in the middle to get the start and end times
                        start_time, end_time = line_string.split('-->')

                        # add these to the last subtitle segment
                        srt_segments[-1]['start'] = self.time_str_to_seconds(start_time.strip())
                        srt_segments[-1]['end'] = self.time_str_to_seconds(end_time.strip())

                    # if the line doesn't contain '-->', it's the text
                    else:

                        # add the text to the last subtitle segment
                        # but also a white space if there's already a string inside the segment text
                        srt_segments[-1]['text'] += \
                            ' '+line_string if len(srt_segments[-1]['text']) > 0 else line_string

                        # add the text to the full text
                        full_text += ' '+line_string if len(full_text) > 0 else line_string

        # initialize the transcription_data for the transcription_file
        transcription_data = {'text': full_text,
                              'segments': srt_segments,
                              'task': 'convert_srt_to_transcription_json',
                              'audio_file_path': '',
                              'srt_file_path': os.path.basename(srt_file_path),
                              'name': os.path.splitext(os.path.basename(srt_file_path))[0]
                              }

        # if no transcription file path was passed, create one based on the srt file name
        if transcription_file_path is None:
            transcription_file_path = os.path.splitext(srt_file_path)[0] + '.transcription.json'

        if not overwrite and os.path.exists(transcription_file_path):
            logger.error("Transcription file {} already exists. Cannot overwite.".format(transcription_file_path))
            return None

        # if the transcription file already exists, log that we're overwriting it
        elif overwrite and os.path.exists(transcription_file_path):
            logger.info("Overwritting {} with transcription from SRT.".format(transcription_file_path))

        else:
            logger.info("Saving transcription from SRT to {}.".format(transcription_file_path))

        # save the full text to a text file
        transcription_txt_file_path = os.path.splitext(transcription_file_path)[0] + '.txt'
        self.save_txt_from_transcription(transcription_txt_file_path, transcription_data)

        # save the transcription data to the transcription file
        self.save_transcription_file(transcription_file_path, transcription_data)

        return transcription_file_path






    def process_transcription_data(self, transcription_segments=None, transcription_data=None):
        '''
        This takes the passed segments and puts them into a dict ready to be passed to a transcription file.

        It's important that if the contents of any transcription segment was edited, to see that reflected in
        other variables as well. It also adds the key 'modified' so we later know that the tokens might not
        correspond to the segment contents anymore.

        :param transcription_segments:
        :return:
        '''

        # take each transcription segment
        if transcription_segments is not None and transcription_segments and transcription_data is not None and 'segments' in transcription_data:

            # first empty the text variable
            transcription_data['text'] = ''

            for segment in transcription_segments:
                print(segment)

                # take each segment and insert it into the text variable
                transcription_data['text'] = segment + ' '

            # make it known that this transcription was modified
            transcription_data['modified'] = time.time()

            return transcription_data

    def save_srt_from_transcription(self, srt_file_path=None, transcription_segments=None,
                                    file_name=None, target_dir=None, transcription_data=None):
        '''
        Saves an SRT file next to the transcription file.

        You can either pass the transcription segments or the full transcription data. When both are passed,
        the transcription_segments will be used.

        :param srt_file_path: The full path to the SRT file
        :param transcription_segments:
        :param file_name: The name of the SRT file
        :param target_dir:
        :param transcription_data:
        :return: False or srt_file_path
        '''

        # if no full path was passed
        if srt_file_path is None:

            # try to use the name and target dir attributes
            if file_name is not None and target_dir is not None:
                # the path should contain the name and the target dir, but end with transcription.json
                srt_file_path = os.path.join(target_dir, file_name + '.srt')

            # if the name and target_dir were not passed, throw an error
            else:
                logger.error('No transcription file path, name or target dir were passed.')
                return False

        if srt_file_path and srt_file_path != '':

            # if the transcription segments were not passed
            # try to find them in transcription_data (if that was passed too)
            if transcription_segments is None and transcription_data and 'segments' in transcription_data:
                transcription_segments = transcription_data['segments']

            # otherwise, stop the process
            else:
                return False

            if transcription_segments:
                with open(srt_file_path, "w", encoding="utf-8") as srt:
                    whisper.utils.write_srt(transcription_segments, file=srt)

                return srt_file_path

        return False

    def save_txt_from_transcription(self, txt_file_path=None, transcription_text=None,
                                    file_name=None, target_dir=None, transcription_data=None):
        '''
        Saves an txt file next to the transcription file.

        You can either pass the transcription text or the full transcription data. When both are passed,
        the transcription_text will be used.

        :param txt_file_path:
        :param transcription_text:
        :param file_name:
        :param target_dir:
        :param transcription_data:
        :return: False or txt_file_path
        '''

        # if no full path was passed
        if txt_file_path is None:

            # try to use the name and target dir attributes
            if file_name is not None and target_dir is not None:
                # the path should contain the name and the target dir, but end with transcription.json
                txt_file_path = os.path.join(target_dir, file_name + '.txt')

            # if the name and target_dir were not passed, throw an error
            else:
                logger.error('No transcription file path, name or target dir were passed.')
                return False

        if txt_file_path and txt_file_path != '':

            # if the transcription segments were not passed
            # try to find them in transcription_data (if that was passed too)
            if transcription_text is None and transcription_data and 'text' in transcription_data:
                transcription_text = transcription_data['text']

            # otherwise, stop the process
            else:
                return False

            # save the text in the txt file
            if transcription_text:
                with open(txt_file_path, 'w', encoding="utf-8") as txt_outfile:
                    txt_outfile.write(transcription_text)

                return txt_file_path

        return False

    def get_timeline_transcriptions(self, timeline_name=None, project_name=None):
        '''
        Gets a list of all the transcriptions associated with a timeline
        :param timeline_name:
        :param project_name:
        :return:
        '''
        if timeline_name is None:
            return None

        # get all the transcription files associated with the timeline
        # by requesting the timeline setting named 'transcription_files'
        timeline_transcription_files = self.stAI.get_timeline_setting(project_name=project_name,
                                                                      timeline_name=timeline_name,
                                                                      setting_key='transcription_files')

        return timeline_transcription_files

    def get_transcription_to_timeline_link(self, transcription_file_path=None, timeline_name=None, project_name=None):
        '''
        Checks if a transcription linked with a timeline but also returns all the transcription files
        associated with that timeline

        :param transcription_file_path:
        :param timeline_name:
        :param project_name:
        :return: bool, timeline_transcription_files
        '''
        if transcription_file_path is None or timeline_name is None:
            return None

        # get all the transcription files associated with the timeline
        timeline_transcription_files = self.get_timeline_transcriptions(timeline_name=timeline_name,
                                                                        project_name=project_name)

        # if the settings of our timeline were found
        if timeline_transcription_files and timeline_transcription_files is not None:

            # check if the transcription is linked to the timeline
            if transcription_file_path in timeline_transcription_files:
                return True, timeline_transcription_files
            # if it's not just say so
            else:
                return False, timeline_transcription_files

        # give None and an empty transcription list
        return None, []

    def link_transcription_to_timeline(self, transcription_file_path=None, timeline_name=None, link=None,
                                       project_name=None):
        '''
        Links transcription files to timelines.
        If the link parameter isn't passed, it first checks if the transcription is linked and then toggles the link
        If no timeline_name is passed, it tries to use the timeline of the currently opened timeline in Resolve

        :param transcription_file_path:
        :param timeline_name:
        :param link:
        :return:
        '''

        # abort if no transcript file was passed
        if transcription_file_path is None:
            logger.error('No transcript path was passed. Unable to link transcript to timeline.')
            return None

        # if no timeline name was passed
        if timeline_name is None:

            # try to get the timeline currently opened in Resolve
            global current_timeline
            if current_timeline and current_timeline is not None and 'name' in current_timeline:

                # and use it as timeline name
                timeline_name = current_timeline['name']


            else:
                logger.error('No timeline was passed. Unable to link transcript to timeline.')
                return None

        # if no project was passed
        if project_name is None:

            # try to get the project opened in Resolve
            global current_project
            if current_project and current_project is not None:

                # use that as a project name
                project_name = current_project

            else:
                logger.error('No project name was passed. Unable to link transcript to timeline.')

        # check the if the transcript is currently linked with the transcription
        current_link, timeline_transcriptions = self.get_transcription_to_timeline_link(
            transcription_file_path=transcription_file_path,
            timeline_name=timeline_name, project_name=project_name)

        # if the link action wasn't passed, decide here whether to link or unlink
        # basically toggle between true or false by choosing the opposite of whether the current_link is true or false
        if link is None and current_link is True:
            link = False
        elif link is None and current_link is not None and current_link is False:
            link = True
        else:
            link = True

        # now create the link if we should
        if link:

            logger.info('Linking to current timeline: {}'.format(timeline_name))

            # but only create it if it isn't in there yet
            if transcription_file_path not in timeline_transcriptions:
                timeline_transcriptions.append(transcription_file_path)

        # or remove the link if we shouldn't
        else:
            logger.info('Unlinking from current timeline: {}'.format(timeline_name))

            # but only remove it if it is in there currently
            if transcription_file_path in timeline_transcriptions:
                timeline_transcriptions.remove(transcription_file_path)

        # if we made it so far, get all the project settings
        self.stAI.project_settings = self.stAI.get_project_settings(project_name=project_name)

        # if there isn't a timeline dict in the project settings, create one
        if 'timelines' not in self.stAI.project_settings:
            self.stAI.project_settings['timelines'] = {}

        # if there isn't a reference to this timeline in the timelines dict
        # add one, including the transcription files list
        if timeline_name not in self.stAI.project_settings['timelines']:
            self.stAI.project_settings['timelines'][timeline_name] = {'transcription_files': []}

        # overwrite the transcription file settings of the timeline
        # within the timelines project settings of this project
        self.stAI.project_settings['timelines'][timeline_name]['transcription_files'] \
            = timeline_transcriptions

        # print(json.dumps(self.stAI.project_settings, indent=4))

        self.stAI.save_project_settings(project_name=project_name,
                                        project_settings=self.stAI.project_settings)

        return link

    def is_UI_obj_available(self, toolkit_UI_obj=None):

        # if there's no toolkit_UI_obj in the object or one hasn't been passed, abort
        if toolkit_UI_obj is None and self.toolkit_UI_obj is None:
            return False
        # if there was a toolkit_UI_obj passed, update the one in the object
        elif toolkit_UI_obj is not None:
            self.toolkit_UI_obj = toolkit_UI_obj
            return True
        # if there simply is a self.toolkit_UI_obj just return True
        else:
            return True

    def calculate_sec_to_resolve_timecode(self, seconds=0):
        global resolve
        if resolve:

            # poll resolve for some info
            # @todo avoid polling resolve for this info and use the existing current_timeline_fps
            #   and current_timeline_startTC
            resolve_data = self.resolve_api.get_resolve_data()

            # get the framerate of the current timeline
            timeline_fps = resolve_data['currentTimelineFPS']

            if timeline_fps is None:
                return False

            # get the start timecode of the current timeline
            timeline_start_tc = resolve_data['currentTimeline']['startTC']

            # initialize the timecode object for the start tc
            timeline_start_tc = Timecode(timeline_fps, timeline_start_tc)

            # only do timecode math if seconds > 0
            if seconds > 0:

                # init the timecode object based on the passed seconds
                tc_from_seconds = Timecode(timeline_fps, start_seconds=float(seconds))

                # calculate the new timecode
                new_timeline_tc = timeline_start_tc + tc_from_seconds

            # otherwise use the timeline start tc
            else:
                new_timeline_tc = timeline_start_tc

            return new_timeline_tc

        else:
            return False

    def calculate_resolve_timecode_to_sec(self, timecode=None):
        global resolve
        if resolve:

            # poll resolve for some info
            # @todo avoid polling resolve for this info and use the existing current_timeline_fps
            #   and current_timeline_startTC
            resolve_data = self.resolve_api.get_resolve_data()

            # get the framerate of the current timeline
            timeline_fps = resolve_data['currentTimelineFPS']

            # get the start timecode of the current timeline
            timeline_start_tc = resolve_data['currentTimeline']['startTC']

            # initialize the timecode object for the start tc
            timeline_start_tc = Timecode(timeline_fps, timeline_start_tc)

            # if no timecode was passed, get it from the variable
            if timecode is None:
                timecode = current_tc

            # if we still don't have a timecode, abort and return None
            if timecode is None:
                return None

            # initialize the timecode object for the passed timecode
            tc = Timecode(timeline_fps, timecode)

            # calculate the difference between the start tc and the passed tc
            tc_diff = tc - timeline_start_tc

            # calculate the seconds from the timecode frames
            tc_diff_seconds = tc_diff.frames / timeline_fps

            # return the seconds which is the previous calculated difference
            return tc_diff_seconds

        else:
            return None

    def go_to_time(self, seconds=0):

        if resolve:

            new_timeline_tc = self.calculate_sec_to_resolve_timecode(seconds)

            # move playhead in resolve
            self.resolve_api.set_resolve_tc(str(new_timeline_tc))

    def on_resolve(self, event_name):
        '''
        Process resolve events
        :param event_name:
        :return:
        '''

        # FOR NOW WE WILL KEEP THE UI UPDATES HERE AS WELL

        # print(event_name)

        # when resolve connects / re-connects
        if event_name == 'resolve_changed':

            # update the main window
            if self.is_UI_obj_available():
                self.toolkit_UI_obj.update_main_window()

        # when the timeline has changed
        elif event_name == 'timeline_changed':

            global current_timeline

            if current_timeline is not None:
                # get the transcription_paths linked with this timeline
                timeline_transcription_file_paths = self.get_timeline_transcriptions(
                    timeline_name=current_timeline['name'],
                    project_name=current_project
                )

                # and open a transcript window for each of them
                if timeline_transcription_file_paths \
                        and timeline_transcription_file_paths is not None\
                        and self.toolkit_UI_obj is not None:
                    for transcription_file_path in timeline_transcription_file_paths:
                        self.toolkit_UI_obj.open_transcription_window(transcription_file_path=transcription_file_path)

                # and close all the transcript windows that aren't linked with this timeline
                if self.stAI.get_app_setting('close_transcripts_on_timeline_change'):
                    if self.toolkit_UI_obj is not None:
                        self.toolkit_UI_obj.close_inactive_transcription_windows(timeline_transcription_file_paths)


    def poll_resolve_thread(self):
        '''
        This keeps resolve polling in a separate thread
        '''

        # wrap poll_resolve_data into a thread
        poll_resolve_thread = Thread(target=self.poll_resolve_data)

        # stop the thread when the main thread stops
        poll_resolve_thread.daemon = True

        # start the thread
        poll_resolve_thread.start()

    def poll_resolve_data(self):
        '''
        Polls resolve and returns either the data passed from resolve, or False if any exceptions occurred
        :return:
        '''

        global current_project
        global current_timeline
        global current_tc
        global current_bin
        global current_timeline_fps
        global resolve

        global resolve_error

        # do this continuously
        while True:

            polling_start_time = time.time()

            # try to poll resolve
            try:

                # first, check if the API module is available on this machine
                if not self.resolve_api.api_module_available:
                    logger.debug('Resolve API module not available on this machine. '
                                 'Aborting Resolve API polling until restart.')
                    return None

                resolve_data = self.resolve_api.get_resolve_data(silent=True)

                #print(resolve)
                #print(resolve_data['resolve'])

                if type(resolve) != type(resolve_data['resolve']):
                    # update the global resolve variable with the resolve object
                    resolve = resolve_data['resolve']
                    self.on_resolve('resolve_changed')

                if current_project != resolve_data['currentProject']:
                    current_project = resolve_data['currentProject']
                    self.on_resolve('project_changed')
                    # logger.info('Current Project: {}'.format(current_project))

                if current_timeline != resolve_data['currentTimeline']:

                    # if the names or the types differ, then the timeline has changed
                    # otherwise timeline_change will be triggered on any setting change
                    if type(current_timeline) != type(resolve_data['currentTimeline']) \
                       or 'name' in current_timeline and not 'name' in resolve_data['currentTimeline'] \
                        or not 'name' in current_timeline and 'name' in resolve_data['currentTimeline'] \
                        or current_timeline['name'] != resolve_data['currentTimeline']['name']:

                        # update the current timeline
                        current_timeline = resolve_data['currentTimeline']

                        self.on_resolve('timeline_changed')

                    else:
                        # nevertheless update the current timeline
                        current_timeline = resolve_data['currentTimeline']

                    # self.on_resolve_timeline_changed()
                    # logger.info("Current Timeline: {}".format(current_timeline))

                #  updates the currentBin
                if current_bin != resolve_data['currentBin']:
                    current_bin = resolve_data['currentBin']
                    self.on_resolve('bin_changed')
                    # logger.info("Current Bin: {}".format(current_bin))

                # update current playhead timecode
                if current_tc != resolve_data['currentTC']:
                    current_tc = resolve_data['currentTC']
                    self.on_resolve('tc_changed')

                # update current playhead timecode
                if current_timeline_fps != resolve_data['currentTimelineFPS']:
                    current_timeline_fps = resolve_data['currentTimelineFPS']
                    self.on_resolve('fps_changed')

                # was there a previous error?
                if resolve is not None and resolve_error > 0:
                    # first let the user know that the connection is back on
                    logger.warning("Resolve connection re-established.")

                    # reset the error counter since the Resolve API worked fine
                    resolve_error = 0

                elif resolve is None:
                    resolve_error += 1

                #return resolve_data

            # if an exception is thrown while trying to work with Resolve, don't crash, but continue to try to poll
            except:

                import traceback
                print(traceback.format_exc())

                # count the number of errors
                resolve_error += 1

                # resolve is now None in the global variable
                # resolve = None

                #return False

            # how often do we poll resolve?
            polling_interval = 500

            # if any errors occurred
            if resolve_error:

                # let the user know that there's an error, and throttle the polling_interval

                # after 15+ errors, deduce that Resolve will not be started this session, so stop polling
                if resolve_error > 15:
                        logger.warning("Resolve not reachable after 15 tries. "
                                     "Disabling Resolve API polling until tool restart.")

                        polling_interval = None

                # after 10+ tries, assume the user is no longer paying attention and reduce the frequency of tries
                elif resolve_error > 10:

                    # only show this error one more time
                    if resolve_error == 11:
                        logger.warning('Resolve is still not reachable. '
                                       'Now retrying every 15 seconds only a few more times.')

                    # and increase the polling interval to 30 seconds
                    polling_interval = 15000

                # if the error has been triggered more than 5 times, do this
                elif resolve_error > 5:

                    if resolve_error == 11:
                        logger.warning('Resolve is still not reachable. Now retrying every 5 seconds or so.')

                    # increase the polling interval to 5 seconds
                    polling_interval = 5000

                else:
                    if resolve_error == 1:
                        logger.warning('Resolve is not reachable. Retrying every few seconds.')

                    # increase the polling interval to 1 second
                    polling_interval = 1000

                # calculate the time that has passed since the polling started
                polling_time = time.time() - polling_start_time

                # if the polling time takes longer than 1 second, throttle the polling interval
                if polling_interval is not None and polling_time > 1:
                    polling_interval = polling_interval + polling_time


                #logger.debug('Polling time: {} seconds'.format(round(time.time() - polling_start_time), 2))

            if polling_interval is None:
                return False

            # take a short break before continuing the loop
            time.sleep(polling_interval/1000)

    def speaker_diarization(self, audio_path, add_speakers_to_segments):

        # WORK IN PROGRESS
        # print("Detecting speakers.")

        # from pyannote.audio import Pipeline
        # pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")

        # apply pretrained pipeline
        # diarization = pipeline(audio_path)

        # print the result
        # for turn, _, speaker in diarization.itertracks(yield_label=True):
        #    print(f"start={turn.start:.1f}s stop={turn.end:.1f}s speaker_{speaker}")
        return False


    def resolve_check_timeline(self, resolve_data, toolkit_UI_obj):
        '''
        This checks if a timeline is available and returns bool
        :param resolve:
        :return:
        '''

        # trigger warning if there is no current timeline
        if resolve_data['currentTimeline'] is None:
            toolkit_UI_obj.notify_via_messagebox(
                message='Timeline not available. Make sure that you\'ve opened a Timeline in Resolve.',
                type='warning')
            return False

        else:
            return True

    def execute_operation(self, operation, toolkit_UI_obj):
        if not operation or operation == '':
            return False

        global stAI

        # get info from resolve for later
        resolve_data = self.resolve_api.get_resolve_data()

        # copy markers operation
        if operation == 'copy_markers_timeline_to_clip' or operation == 'copy_markers_clip_to_timeline':

            # set source and destination depending on the operation
            if operation == 'copy_markers_timeline_to_clip':
                source = 'timeline'
                destination = 'clip'

            elif operation == 'copy_markers_clip_to_timeline':
                source = 'clip'
                destination = 'timeline'

            # this else will never be triggered but let's leave it here for safety for now
            else:
                return False

            # trigger warning and stop if there is no current timeline
            if not self.resolve_check_timeline(resolve_data, toolkit_UI_obj):
                return False

            # trigger warning and stop if there are no bin clips
            if resolve_data['binClips'] is None:
                toolkit_UI_obj.notify_via_messagebox(
                    message='Bin clips not available. Make sure that a bin is opened in Resolve.\n\n'
                            'This doesn\'t work if multiple bins or smart bins are selected due to API.',
                    type='warning')
                return False

            # execute operation without asking for any prompts
            # this will delete the existing clip/timeline destination markers,
            # but the user can undo the operation from Resolve
            return self.resolve_api.copy_markers(source, destination,
                                             resolve_data['currentTimeline']['name'],
                                             resolve_data['currentTimeline']['name'],
                                             True)

        # render marker operation
        elif operation == 'render_markers_to_stills' or operation == 'render_markers_to_clips':

            # ask user for marker color

            # but first make a list of all the available marker colors based on the timeline markers
            current_timeline_marker_colors = []
            if self.resolve_check_timeline(resolve_data, toolkit_UI_obj) and \
                    current_timeline and 'markers' in current_timeline:

                # take each marker from timeline and get its color
                for marker in current_timeline['markers']:

                    # only append the marker to the list if it wasn't added already
                    if current_timeline['markers'][marker]['color'] not in current_timeline_marker_colors:
                        current_timeline_marker_colors.append(current_timeline['markers'][marker]['color'])

            # if no markers exist, cancel operation and let the user know that there are no markers to render
            if current_timeline_marker_colors:
                marker_color = simpledialog.askstring(title="Markers Color",
                                                      prompt="What color markers should we render?\n\n"
                                                             "These are the marker colors on the current timeline:\n"
                                                             + ", ".join(current_timeline_marker_colors))
            else:
                no_markers_alert = 'The timeline doesn\'t contain any markers'
                logger.warning(no_markers_alert)
                return False

            if not marker_color:
                logger.debug("User canceled Resolve render operation by not selecting a marker color")
                return False

            if marker_color not in current_timeline_marker_colors:
                toolkit_UI_obj.notify_via_messagebox(title='Unavailable marker color',
                                                     message='The marker color you\'ve entered doesn\'t exist on the timeline.',
                                                     message_log="Aborting. User entered a marker color that doesn't exist on the timeline.",
                                                     type='error'
                                                     )

                return False

            render_target_dir = toolkit_UI_obj.ask_for_target_dir()

            if not render_target_dir or render_target_dir == '':
                logger.debug("User canceled Resolve render operation")
                return False

            if operation == 'render_markers_to_stills':
                stills = True
                render = True
                render_preset = "Still_TIFF"
            else:
                stills = False
                render = False
                render_preset = False

            self.resolve_api.render_markers(marker_color, render_target_dir, False, stills, render, render_preset)

        return False


current_project = ''
current_timeline = ''
current_tc = '00:00:00:00'
current_timeline_fps = ''
current_bin = ''
resolve_error = 0
resolve = None


class StoryToolkitAI:
    def __init__(self, server=False):
        # import version.py - this holds the version stored locally
        import version

        # check if standalone exists in globals
        if 'standalone' in globals():
            global standalone
        else:
            global standalone
            standalone = False

        # keep the version in memory
        self.__version__ = self.version = version.__version__

        # this is where all the user files should be stored
        # if it's not absolute, make sure it's relative to the app.py script location
        # to make it easier for the users to find it
        # (and to prevent paths relative to possible virtual environment paths)
        if not os.path.isabs(USER_DATA_PATH):
            self.user_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), USER_DATA_PATH)
        else:
            self.user_data_path = USER_DATA_PATH

        # the config file should be in the user data directory
        self.config_file_path = os.path.join(self.user_data_path, APP_CONFIG_FILE_NAME)

        # create a config variable
        self.config = None

        # the projects directory is always inside the user_data_path
        # this is where we will store all the stuff related to specific projects
        self.projects_dir_path = os.path.join(self.user_data_path, 'projects')

        # create a project settings variable
        self.project_settings = {}

        # define the api variables
        self.api_possible = False
        self.api_user = None
        self.api_token = None
        self.api_host = None
        self.api = None

        logger.info(Style.BOLD+Style.UNDERLINE+"Running StoryToolkitAI{} version {} {}"
                    .format(' SERVER' if server else '',
                            self.__version__,
                            '(standalone)' if standalone else ''))

    def user_data_dir_exists(self, create_if_not=True):
        '''
        Checks if the user data dir exists and creates one if asked to
        :param create_if_not:
        :return:
        '''

        # if the directory doesn't exist
        if not os.path.exists(self.user_data_path):
            logger.warning('User data directory {} doesn\'t exist.'
                           .format(os.path.abspath(self.user_data_path)))

            if create_if_not:
                logger.warning('Creating user data directory.')

                # and create the whole path to it if it doesn't
                os.makedirs(self.user_data_path)

                # for users of versions prior to 0.16.14, the user data directory was at OLD_USER_DATA_PATH
                # so make sure we copy everything from the old path to the new directory
                old_user_data_path_abs = os.path.join(os.path.dirname(os.path.abspath(__file__)), OLD_USER_DATA_PATH)

                # we first check if the old_user_data_path_abs exists
                if os.path.exists(old_user_data_path_abs):
                    import shutil
                    from datetime import date
                    import platform

                    logger.warning('Old user data directory found.\n\n')

                    # let the user know that we are moving the files
                    move_user_data_path_msg = \
                                    'Starting with version 0.16.14, '\
                                    'the user data directory on {} has moved to {}.\n'\
                                    'This means that any existing configuration and project ' \
                                    'settings files will be copied there.\n'\
                                    'If the files are at the new location, feel free to delete {}\n' \
                                    .format(platform.node(),
                                            self.user_data_path, old_user_data_path_abs, old_user_data_path_abs)

                    logger.warning(move_user_data_path_msg)

                    logger.warning('Copying user data files to new location.')

                    # copy all the contents of the OLD_USER_DATA_PATH to the new path
                    for item in os.listdir(old_user_data_path_abs):
                        s = os.path.join(old_user_data_path_abs, item)
                        d = os.path.join(self.user_data_path, item)

                        logger.warning((' - {}'.format(item)))

                        if os.path.isdir(s):
                            shutil.copytree(s, d, False, None)
                        else:
                            shutil.copy2(s, d)

                    logger.warning('Finished copying user data files to {}'.format(self.user_data_path))

                    # reload the config file
                    self.config = self.get_config()

                    # leave a readme file in the OLD_USER_DATA_PATH so that the user knows that stuff was moved
                    with open(os.path.join(old_user_data_path_abs, 'README.txt'), 'a') as f:
                        f.write('\n'+str(date.today())+'\n')
                        f.write(move_user_data_path_msg)


            else:
                return False

        return True

    def project_dir_exists(self, project_settings_path=None, create_if_not=True):

        if project_settings_path is None:
            return False

        # if the directory doesn't exist
        if not os.path.exists(os.path.dirname(project_settings_path)):
            logger.warning('Project settings directory {} doesn\'t exist.'
                           .format(os.path.abspath(os.path.dirname(project_settings_path))))

            if create_if_not:
                logger.warning('Creating project settings directory.')

                # and create the whole path to it if it doesn't
                os.makedirs(os.path.dirname(project_settings_path))

            else:
                return False

        return True

    def get_app_setting(self, setting_name=None, default_if_none=None):
        '''
        Returns a specific app setting or None if it doesn't exist
        If default if none is passed, the app will also save the setting to the config for future use
        :param setting_name:
        :param default_if_none:
        :return:
        '''

        if setting_name is None or not setting_name or setting_name == '':
            logger.error('No setting was passed.')
            return False

        # if the config doesn't exist, create it
        # this means that the configurations are only loaded once per session
        # or when the user changes them during the session
        if self.config is None:
            self.config = self.get_config()

        # look for the requested setting
        if setting_name in self.config:

            # and return it
            return self.config[setting_name]

        # if the requested setting doesn't exist in the config
        # but a default was passed
        elif default_if_none is not None:

            logger.info('Config setting {} saved as "{}" '.format(setting_name, default_if_none))

            # save the default to the config
            self.save_config(setting_name=setting_name, setting_value=default_if_none)

            # and then return the default
            return default_if_none

        # otherwise simple return none
        else:
            return None

    def save_config(self, setting_name=None, setting_value=None):
        '''
        Saves a setting to the app configuration file
        :param config_key:
        :param config_value:
        :return:
        '''

        # if a setting name and value was passed
        if setting_name is not None and setting_value is not None:

            # get existing configuration
            self.config = self.get_config()

            logger.info('Updated config file {} with {} data.'
                           .format(os.path.abspath(self.config_file_path), setting_name))
            self.config[setting_name] = setting_value

        # if the config is empty something might be wrong
        if self.config is None:
            logger.error('Config file needs to be loaded before saving')
            return False

        # before writing the configuration to the config file
        # check if the user data directory exists (and create it if not)
        self.user_data_dir_exists(create_if_not=True)

        # then write the config to the config json
        with open(self.config_file_path, 'w') as outfile:
            json.dump(self.config, outfile, indent=3)

            logger.info('Config file {} saved.'.format(os.path.abspath(self.config_file_path)))

        # and return the config back to the user
        return self.config

    def get_config(self):
        '''
        Gets the app configuration from the config file (if one exists)
        :return:
        '''

        # read the config file if it exists
        if os.path.exists(self.config_file_path):
            logger.debug('Loading config file {}.'.format(self.config_file_path))

            # read the app config
            with open(self.config_file_path, 'r') as json_file:
                self.config = json.load(json_file)

            # and return the config
            return self.config

        # if the config file doesn't exist, return an empty dict
        else:
            logger.debug('No config file found at {}.'.format(self.config_file_path))
            return {}

    def _project_settings_path(self, project_name=None):

        # the full path to the project settings file
        if project_name is not None and project_name != '':
            return os.path.join(self.projects_dir_path, project_name, 'project.json')

    def get_project_settings(self, project_name=None):
        '''
        Gets the settings of a specific project
        :return:
        '''

        if project_name is None:
            logger.error('Unable to get project settings if no project name was passed.')

        # the full path to the project settings file
        project_settings_path = self._project_settings_path(project_name=project_name)

        # read the project settings file if it exists
        if os.path.exists(project_settings_path):

            # read the project settings from the project.json
            with open(project_settings_path, 'r') as json_file:
                self.project_settings = json.load(json_file)

            # and return the project settings
            return self.project_settings

        # if the project settings file doesn't exist, return an empty dict
        else:
            return {}

    def save_project_settings(self, project_name=None, project_settings=None):
        '''
        Saves the settings of a specific project.
        This will OVERWRITE any existing project settings so make sure you include the whole project settings dictionary
        in the call!
        :param project_name:
        :return:
        '''

        if project_name is None or project_name == '' or project_settings is None:
            logger.error('Insufficient data. Unable to save project settings.')
            return False

        # the full path to the project settings file
        project_settings_path = self._project_settings_path(project_name=project_name)

        # before writing the project settings
        # check if the project directory exists (and create it if not)
        if (self.project_dir_exists(project_settings_path=project_settings_path, create_if_not=True)):
            # but make sure it also contains the correct project name
            project_settings['name'] = project_name

            # then overwrite the settings to the project settings json
            with open(project_settings_path, 'w') as outfile:
                json.dump(project_settings, outfile, indent=3)

            logger.info('Updated project settings file {}.'
                           .format(os.path.abspath(project_settings_path)))

            # and return the config back to the user
            return project_settings

        return False

    def get_project_setting(self, project_name=None, setting_key=None):

        # get all the project settings first
        self.project_settings = self.get_project_settings(project_name=project_name)

        if self.project_settings:

            # is there a setting_key in the project settings
            if setting_key in self.project_settings:
                # then return the setting value
                return self.project_settings[setting_key]

        # if the setting key wasn't found
        return None

    def save_project_setting(self, project_name=None, setting_key=None, setting_value=None):
        '''
        Saves only a specific project setting, by getting the saved project settings and only overwriting
        the setting that was passed (setting_key)
        :param project_name:
        :param setting_key:
        :param setting_value:
        :return:
        '''

        if project_name is None or project_name == '' or setting_key is None:
            logger.error('Insufficient data. Unable to save project setting.')
            return False

        # get the current project settings
        self.project_settings = self.get_project_settings(project_name=project_name)

        # convert None values to False
        if setting_value is None:
            setting_value = False

        # only overwrite the passed setting_key
        self.project_settings[setting_key] = setting_value

        # now save them to file
        self.save_project_settings(project_name=project_name, project_settings=self.project_settings)

        return True

    def get_timeline_setting(self, project_name=None, timeline_name=None, setting_key=None):
        '''
        This gets a specific timeline setting from the project.json by looking into the timelines dictionary
        :param project_name:
        :param timeline_name:
        :param setting_key:
        :return:
        '''

        # get all the project settings first
        self.project_settings = self.get_project_settings(project_name=project_name)

        if self.project_settings:

            # is there a timeline dictionary?
            # is there a reference regarding the passed timeline?
            # is there a reference regarding the passed setting key?
            if 'timelines' in self.project_settings \
                    and timeline_name in self.project_settings['timelines'] \
                    and setting_key in self.project_settings['timelines'][timeline_name]:
                # then return the setting value
                return self.project_settings['timelines'][timeline_name][setting_key]

        # if the setting key, or any of the stuff above wasn't found
        return None

    def check_update(self, release=False):
        '''
        This checks if there's a new version of the app on GitHub and returns True if it is and the version number

        :param: release: if True, it will only check for standalone releases, and ignore the version.py file
        :return: [bool, str online_version]
        '''

        from requests import get

        # get the latest release from GitHub if release is True
        if release:

            try:
                # get the latest release from GitHub
                latest_release = get('https://api.github.com/repos/octimot/storytoolkitai/releases/latest').json()

                # remove the 'v' from the release version (tag)
                online_version_raw = latest_release['tag_name'].replace('v', '')

            # show exception if it fails, but don't crash
            except Exception as e:
                logger.warning('Unable to check the latest release version of StoryToolkitAI: {}. '
                               '\nIs your Internet connection working?'.format(e))

                # return False - no update available and None instead of an online version number
                return False, None

        # otherwise get the latest version from the GitHub repo version.py file
        else:
            version_request = "https://raw.githubusercontent.com/octimot/StoryToolkitAI/main/version.py"

            # retrieve the latest version number from github
            try:
                r = get(version_request, verify=True)

                # extract the actual version number from the string
                online_version_raw = r.text.split('"')[1]

            # show exception if it fails, but don't crash
            except Exception as e:
                logger.warning('Unable to check the latest version of StoryToolkitAI: {}. '
                               '\nIs your Internet connection working?'.format(e))

                # return False - no update available and None instead of an online version number
                return False, None

        # get the numbers in the version string
        local_version = self.__version__.split(".")
        online_version = online_version_raw.split(".")

        # did the use choose to ignore the update?
        ignore_update = self.get_app_setting(setting_name='ignore_update', default_if_none=False)

        # if they did, is the online version the same as the one they ignored?
        if ignore_update and ignore_update.split(".") == online_version:

            logger.info('Ignoring the new update (version {}) according to app settings.'.format(ignore_update))

            # return False - no update available and the local version number instead of what's online
            return False, self.__version__


        # take each number in the version string and compare it with the local numbers
        for n in range(len(online_version)):

            # only test for the first 3 numbers in the version string
            if n < 3:
                # if there's a number larger online, return true
                if int(online_version[n]) > int(local_version[n]):
                    return True, online_version_raw

                # continue the search if there's no version mismatch
                if int(online_version[n]) == int(local_version[n]):
                    continue
                break

        # return false (and the online version) if the local and the online versions match
        return False, online_version_raw

    def check_ffmpeg(self):

        # check if ffmpeg is installed

        try:

            # first, check if the user added the ffmpeg path to the app settings
            ffmpeg_path_custom = self.get_app_setting(setting_name='ffmpeg_path')

            # if the ffmpeg path is not empty
            if ffmpeg_path_custom is not None and ffmpeg_path_custom != '':

                logger.debug('Found ffmpeg path in app config: {}'.format(ffmpeg_path_custom))

                if os.path.isfile(ffmpeg_path_custom):

                    # add it to the environment variables
                    os.environ['FFMPEG_BINARY'] = ffmpeg_path_custom

                else:
                    logger.warning('The ffmpeg path {} found in app config is not valid.'
                                   .format(ffmpeg_path_custom))

                    ffmpeg_path_custom = None

            # otherwise try to find the binary next to the app
            if ffmpeg_path_custom is None:

                # and if it exists, define the environment variable for ffmpeg for this session
                if os.path.exists('ffmpeg'):
                    logger.debug('Found ffmpeg in current working directory.')
                    os.environ['FFMPEG_BINARY'] = 'ffmpeg'

            # and check if it's working

            logger.debug('Looking for ffmpeg in env variable.')

            # get the FFMPEG_BINARY variable
            ffmpeg_binary = os.getenv('FFMPEG_BINARY')

            # if the variable is empty, try to find ffmpeg in the PATH
            if ffmpeg_binary is None or ffmpeg_binary == '':
                logger.debug('FFMPEG_BINARY env variable is empty. Looking for ffmpeg in PATH.')
                import shutil
                ffmpeg_binary = ffmpeg_binary if ffmpeg_binary else shutil.which('ffmpeg')

            # if ffmpeg is still not found in the path either, try to brute force it
            if ffmpeg_binary is None:
                logger.debug('FFMPEG_BINARY environment variable not set. Trying to use "ffmpeg".')
                ffmpeg_binary = 'ffmpeg'

            cmd = [
                ffmpeg_binary]

            logger.debug('Checking ffmpeg binary: {}'.format(ffmpeg_binary))

            # check if ffmpeg answers the call
            exit_code = subprocess.call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            logger.debug('FFMPEG exit code: {}'.format(exit_code))

            if exit_code == 1:
                logger.info('FFMPEG found at {}'.format(ffmpeg_binary))

            else:
                logger.error('FFMPEG not found on this machine, some features will not work')

            # if it does, just return true
            return True

        except FileNotFoundError:

            # print the exact exception
            import traceback
            traceback_str = traceback.format_exc()

            logger.error(traceback_str)

            # if the ffmpeg binary wasn't found, we presume that ffmpeg is not installed on the machine
            return False

    def check_API_credentials(self):
        '''
        Checks if the API credentials are set in the app settings
        :return:
        '''

        # get the API token from the app settings
        api_token = self.get_app_setting(setting_name='api_token', default_if_none=False)

        # get the API username from the app settings
        api_user = self.get_app_setting(setting_name='api_user', default_if_none=False)

        # get the API host from the app settings
        api_host = self.get_app_setting(setting_name='api_host', default_if_none=False)

        # if the API token and username are not False or empty
        if api_token and api_user and api_token is not None and api_user is not None:
            logger.info('Found API username and token in config')
            self.api_user = api_user
            self.api_token = api_token
            self.api_host = api_host
            self.api_possible = True

        else:
            logger.debug('No API username and token found in config, so API connection not possible')
            self.api_user = None
            self.api_token = None
            self.api_host = None
            self.api_possible = False
            return None

    def connect_API(self):
        '''
        Connects to the API
        :return:
        '''

        # if the API credentials are not set, return False
        if not self.api_possible:
            logger.error('API credentials not set, so API connection not possible')
            return False

        # if the API credentials are set, try to connect to the API
        try:

            logger.info('Trying to connect to the API')

            import socket
            import ssl

            # get the host and ip from self.api_host
            host = self.api_host.split(':')[0]
            port = int(self.api_host.split(':')[1])

            # connect to API using sockets, ssl and user and token
            self.api = socket.create_connection((host, port))

            # wrap the socket in an SSL context
            #self.api = ssl.wrap_socket(self.api, ssl_version=ssl.PROTOCOL_TLSv1_2)

            # send the username and token to the API
            self.api.send(bytes('login:{}:{}'.format(self.api_user, self.api_token), 'utf-8'))

            # get the response from the API
            response = self.api.recv(1024).decode('utf-8')

            # if the response is not 'ok', return False
            if response != 'ok':
                logger.error('API connection failed: {}'.format(response))
                return False

            logger.info('API authenticated')
            self.api_connected = True

            while True:
                # ping the server every 2 seconds
                time.sleep(2)
                self.send_API_command(command='ping')

            # send the ping command
            #self.send_API_command(command='transcribe:file_path')

            return True

        # if the connection fails, return False
        except Exception as e:
            logger.error('Unable to connect to the API: {}'.format(e))
            self.api_connected = False
            return False

    def send_API_command(self, command):

        if self.api is None:
            logger.error('API not connected, so no command can be sent')
            return False

        try:
            self.api.send(bytes(command, 'utf-8'))
            logger.debug('Sending command to API: {}'.format(command))

            response = self.api.recv(1024).decode('utf-8')

            logger.debug('Received response from API: {}'.format(response))
            return response

        except Exception as e:
            logger.error('Unable to send command to API: {}'.format(e))
            return False



if __name__ == '__main__':

    # keep a global StoryToolkitAI object for now
    global stAI
    global standalone

    # are we running the standalone version?
    if getattr(sys, 'frozen', False):
        standalone = True
    else:
        standalone = False

    # init StoryToolkitAI object
    stAI = StoryToolkitAI()

    # check if a new version of the app exists on GitHub
    # but use either the release version number or version.py,
    # depending on standalone is True or False
    [update_exists, online_version] = stAI.check_update(release=standalone)

    # if an update exists, let the user know about it
    update_available = None
    if update_exists:
        update_available = online_version

    # connect to the API
    # stAI.check_API_credentials()
    # stAI.connect_API()

    # initialize operations object
    toolkit_ops_obj = ToolkitOps(stAI=stAI)

    # initialize GUI
    app_UI = toolkit_UI(toolkit_ops_obj=toolkit_ops_obj, stAI=stAI,
                        update_available=update_available)

    # connect app UI to operations object
    toolkit_ops_obj.toolkit_UI_obj = app_UI

    # create the main window
    app_UI.create_main_window()
