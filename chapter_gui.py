# -*- coding:utf-8 -*-
"""
CIG @ CQT
BY MM 10th Feb 2021
"""
from PyQt6 import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt
#from guibyte import Ui_Dialog
# from guibyte_scroll_v2 import Ui_TimeSeqWindow
from guibyte_scroll import Ui_TimeSeqWindow, UI_ChapterWindow
from fpgaseq import FPGA_Seq, SeqLine
from DD_seq import DD_ui_dialog
from Classifier_cfg import CF_ui_dialog
from sideband_seq import sideband_ui_dialog
from channel_labels import ChannelLabel
import pickle
import sys, math
import traceback
from functools import partial
import numpy as np
import pathlib

BITWIDTH  = 28 # Width of a bit button in pixels
BITHEIGHT = 28 # Height of a bit button in pixels
NBITS     = 40 # Number of bits
PIXWIDTH = 200 + BITWIDTH * NBITS # Width of the screen in pixels

# Button group for the scan radio buttons
scangroup = QtWidgets.QButtonGroup()

# Bit for the GUI
class MyBit():
    def __init__(self, widget, layout, x, y):

        self.layout = layout
        self.widget = widget
        self.button = QtWidgets.QToolButton(widget)
        self.button.setMinimumSize(QtCore.QSize(20, 20))
        self.button.setObjectName("bit")
        layout.addWidget(self.button, y, x, 1, 1)

        self.color     = {}
        self.color[-1] = "* { background-color: rgb(255,125,100) }"
        self.color[1]  = "* { background-color: rgb(125,255,100) }"
        self.color[0]  = "* { background-color: rgb(125,110,100) }"
        self.bit       = 0

        self.button.setStyleSheet(self.color[self.bit])
        self.button.clicked.connect(self.bit_clicked)

    # Slot to click the button
    def bit_clicked(self):
        self.bit = self.bit + 1
        if (self.bit == 2):
            self.bit = -1
        self.display()

    # Set the button value
    def set(self, bit):
        self.bit = bit
        self.display()

    # Changes color of the button accouding to the bit
    def display(self):
        self.button.setStyleSheet(self.color[self.bit])


    # Enable or disable button
    def setActive(self, active):
        self.button.setEnabled(active)

    # Delete bit button
    def delete(self):
        self.layout.removeWidget(self.button)
        self.button.setParent(None)


# one line of output bit pattern for the GUI
class Pattern():
    def __init__(self, widget, layout, y, length = NBITS):
        self.bits = {}
        self.layout = layout
        self.widget = widget
        self.row    = y
        self.length = length
        for i in range(length):
            self.bits[i] = MyBit(self.widget, self.layout, i + 5, self.row)

    def copyBits(self, original):
        original_bits = original.getPattern()
        for i in range(self.length):
            self.bits[i].set(original_bits.get(i, -1))

    # Activate or reactivate bits buttons
    def setActive(self, active):
        for i in self.bits:
            self.bits[i].setActive(active)

    # Deletes row of bits for the user interface and memory
    def delete(self):
        for i in self.bits:
            self.bits[i].delete()

    # get the pattn array
    def getPattern(self):
        bitarray = {}
        for i in self.bits:
            bitarray[i] = self.bits[i].bit
        return bitarray

    # set the bit array according to the seqline
    def setPattern(self, seqline):
        if ( len(seqline.bitarray) != len(self.bits)):
            return
        for i in seqline.bitarray:
            self.bits[i].set(seqline.bitarray[i])

# Data from chapter
class ChapterData():
    def __init__(self, nrow = 2, active = True, lines = [], name = "Default chapter"):
        self.name   = name
        self.nrow   = nrow
        self.active = active
        self.lines  = lines[:]

# Class that draws labels on top of the time sequence pattern
class Labels():
    def __init__(self, widget, rows = 1):
        self.widget = widget
        self.nrow  = rows+1

        # self.widget.setGeometry(QtCore.QRect(50, 20, PIXWIDTH, self.nrow * BITWIDTH))
        self.widget.setMinimumSize(QtCore.QSize(PIXWIDTH, self.nrow * BITWIDTH))
        # self.widget.setMinimumSize(QtCore.QSize(PIXWIDTH, self.nrow * 32))

        self.layout = QtWidgets.QGridLayout(widget)
        self.layout.setObjectName("gridLayout")

        self.buttonLabel = QtWidgets.QLabel(self.widget)
        self.buttonLabel.setText("Chapter name")
#        self.buttonLabel.setStyleSheet("* { background-color: rgb(200,127,127) }")
        self.buttonLabel.setGeometry(QtCore.QRect(0, 0, 44, 20))
        self.buttonLabel.setMinimumSize(QtCore.QSize(44, 20))
#        self.buttonLabel.setMaximumSize(QtCore.QSize(44, 20))
        self.layout.addWidget(self.buttonLabel, 1, 0, 1, 1)

        self.plusLabel   = QtWidgets.QLabel(self.widget)
        self.plusLabel.setText("+/-")
#        self.plusLabel.setStyleSheet("* { background-color: rgb(127,200,127) }")
        self.plusLabel.setGeometry(QtCore.QRect(0, 0, 18, 18))
        self.plusLabel.setMinimumSize(QtCore.QSize(18, 18))
        self.plusLabel.setMaximumSize(QtCore.QSize(18, 18))
        self.layout.addWidget(self.plusLabel, 1, 1, 1, 1)

        self.delayLabel   = QtWidgets.QLabel(self.widget)
        self.delayLabel.setText("Delay, us")
#        self.delayLabel.setStyleSheet("* { background-color: rgb(127,127,200) }")
        self.delayLabel.setGeometry(QtCore.QRect(0, 0, 80, 22))
        self.delayLabel.setMinimumSize(QtCore.QSize(80, 22))
        self.delayLabel.setMaximumSize(QtCore.QSize(80, 22))
        self.layout.addWidget(self.delayLabel, 1, 2, 1, 1)

        self.scanLabel   = QtWidgets.QLabel(self.widget)
        self.scanLabel.setText("Scan")
#        self.scanLabel.setStyleSheet("* { background-color: rgb(230,127,230) }")
        self.scanLabel.setGeometry(QtCore.QRect(0, 0, 22, 22))
        self.scanLabel.setMinimumSize(QtCore.QSize(22, 22))
        self.scanLabel.setMaximumSize(QtCore.QSize(22, 22))
        self.layout.addWidget(self.scanLabel, 1, 3, 1, 1)

        self.indexLabel   = QtWidgets.QLabel(self.widget)
        self.indexLabel.setText("Index")
        self.indexLabel.setGeometry(QtCore.QRect(0, 0, 22, 22))
        self.indexLabel.setMinimumSize(QtCore.QSize(22, 22))
        self.indexLabel.setMaximumSize(QtCore.QSize(22, 22))
        self.layout.addWidget(self.indexLabel, 1, 4, 1, 1)

        self.bitGroups = ["Out 1", "Out 2", "Out 3", "Out 4", "Counter gate"]
        self.bitGroupsColors =["* { background-color: rgb(127,230,230) }",
                               "* { background-color: rgb(230,127,230) }",
                               "* { background-color: rgb(230,230,127) }",
                               "* { background-color: rgb(240,127,127) }",
                               "* { background-color: rgb(127,240,127) }"]

        self.bitLabel = {}
        self.bitGroupLabel = {}
        self.bitChannelLabel = ChannelLabel()
        for i in range(5):
            self.bitGroupLabel[i]   = QtWidgets.QLabel(self.widget)
            self.bitGroupLabel[i].setText(self.bitGroups[i])
            self.bitGroupLabel[i].setStyleSheet(self.bitGroupsColors[i])
            self.bitGroupLabel[i].setGeometry(QtCore.QRect(0, 0, 20, 20))
            self.bitGroupLabel[i].setMinimumSize(QtCore.QSize(20, 20))
            # self.bitGroupLabel[i].setMaximumSize(QtCore.QSize(20, 20))
            self.layout.addWidget(self.bitGroupLabel[i], 0, 5+8*i, 1, 8)
            for j in range(8):
                self.bitLabel[8*i+j]   = QtWidgets.QLabel(self.widget)
                self.bitLabel[8*i+j].setText(str(j+1))
                self.bitLabel[8*i+j].setStyleSheet(self.bitGroupsColors[i])
                self.bitLabel[8*i+j].setGeometry(QtCore.QRect(0, 0, 20, 20))
                self.bitLabel[8*i+j].setMinimumSize(QtCore.QSize(20, 20))
                self.bitLabel[8*i+j].setMaximumSize(QtCore.QSize(20, 20))
                self.bitLabel[8*i+j].setToolTip(self.bitChannelLabel.label[8*i+j])
                self.layout.addWidget(self.bitLabel[8*i+j], 1, 5+8*i+j, 1, 1)


# Chapter for the time sequence; draws it on the screen and keeps the data
class Chapter():
    def __init__(self, widget, rows, active = True):
        self.green = "* { background-color: rgb(125,255,100) }"
        self.gray  = "* { background-color: rgb(125,110,100) }"
        self.widget = widget

        self.active = active
        if (rows < 2):
            self.nrow = 2
        else:
            self.nrow   = rows

        self.delay = {}
        self.scan  = {}
        self.pattn = {}
        self.index = {}

        self.widget.setGeometry(QtCore.QRect(50, 20, PIXWIDTH, self.nrow * BITWIDTH))
        self.widget.setMinimumSize(QtCore.QSize(PIXWIDTH, self.nrow * BITWIDTH))

        self.layout = QtWidgets.QGridLayout(widget)
        self.layout.setObjectName("gridLayout")

        self.activeButton = QtWidgets.QPushButton(self.widget)
        self.activeButton.setMinimumSize(QtCore.QSize(44, 20))
        self.activeButton.setGeometry(QtCore.QRect(0, 0, 44, 20))
        self.layout.addWidget(self.activeButton, 0, 0, 1, 1)

        self.name = QtWidgets.QLineEdit(self.widget)
        self.name.setMinimumSize(QtCore.QSize(44, 20))
        self.name.setObjectName("Chapter name")
        self.layout.addWidget(self.name, 1, 0, 1, 1)

        self.plusButton = QtWidgets.QToolButton(self.widget)
        self.plusButton.setText("+")
        self.plusButton.setMinimumSize(QtCore.QSize(18, 18))
        self.layout.addWidget(self.plusButton, 0, 1, 1, 1)

        self.minusButton = QtWidgets.QToolButton(self.widget)
        self.minusButton.setText("-")
        self.minusButton.setMinimumSize(QtCore.QSize(18, 18))
        self.layout.addWidget(self.minusButton, 1, 1, 1, 1)


        # add row
        for i in range(self.nrow):
            self.delay[i] = QtWidgets.QDoubleSpinBox(self.widget)
            self.delay[i].setMaximum(10000000)
            self.delay[i].setMinimum(0.1)
            self.delay[i].setSingleStep(1.0)
            self.delay[i].setObjectName("delay")
            self.delay[i].setMinimumSize(QtCore.QSize(50, 22))
            self.layout.addWidget(self.delay[i], i, 2, 1, 1)

            self.scan[i] = QtWidgets.QRadioButton(self.widget)
            self.scan[i].setMinimumSize(QtCore.QSize(22, 22))
            self.layout.addWidget(self.scan[i], i, 3, 1, 1)
            scangroup.addButton(self.scan[i])

            self.index[i] = QtWidgets.QLabel(self.widget)
            self.index[i].setMinimumSize(QtCore.QSize(22, 22))
            self.index[i].setText(str(i+1))
            self.layout.addWidget(self.index[i], i, 4, 1, 1)

            self.pattn[i] = Pattern(self.widget, self.layout, i)

        self.setActive(self.active)
        self.layout.update()

        # Signal / slot connection for buttons
        self.activeButton.clicked.connect(self.active_clicked)
        self.plusButton.clicked.connect(self.plus_clicked)
        self.minusButton.clicked.connect(self.minus_clicked)

    # Gets all the data to save chapter to disk
    def getData(self):
        chapdata = ChapterData(nrow = self.nrow, active = self.active, name = self.name.text())
        for i in range(self.nrow):
            chapdata.lines.append(SeqLine(self.delay[i].value(), self.scan[i].isChecked(), self.pattn[i].getPattern()))
        return chapdata

    # Sets the data
    def setData(self, chapdata):
    # Add or remove rows in the chapter
        if (chapdata.nrow > self.nrow):
            for i in range(chapdata.nrow - self.nrow):
                self.add_line()
        elif (chapdata.nrow < self.nrow):
            for i in range(self.nrow - chapdata.nrow):
                self.del_line()
        self.nrow = chapdata.nrow
    # set rows
        for i in range(self.nrow):
            self.pattn[i].setPattern(chapdata.lines[i])
            self.delay[i].setValue(chapdata.lines[i].delay)
            self.scan[i].setChecked(chapdata.lines[i].scanned)
    # Set active data
        self.name.setText(chapdata.name)
        self.setActive(chapdata.active)
#        print("setData for ", chapdata.name)

    # return chapter name and line number if scan check box is clicked.
    # return "" and -1 otherwise
    def getScanLine(self):
        for i in range(self.nrow):
            if (self.scan[i].isChecked()):
                return self.name.text(), i
        return "", -1


    # returns the array of seqline objects that correspond to the chapter
    def appendData(self, seq):
        if (self.active == False):
            return seq

        for i in range(self.nrow):
            seq.append(SeqLine(self.delay[i].value(), self.scan[i].isChecked(), self.pattn[i].getPattern()))
        return seq

    # Adds one line to the chapter
    def add_line(self, copy=False):
        self.widget.setGeometry(QtCore.QRect(50, 20, PIXWIDTH, (self.nrow + 1)* BITWIDTH))
        self.widget.setMinimumSize(QtCore.QSize(PIXWIDTH, (self.nrow + 1) * BITWIDTH))
        self.delay[self.nrow] = QtWidgets.QDoubleSpinBox(self.widget)
        self.delay[self.nrow].setMaximum(10000000)
        self.delay[self.nrow].setMinimum(0.1)
        self.delay[self.nrow].setSingleStep(1.0)
        self.delay[self.nrow].setObjectName("delay")
        self.delay[self.nrow].setMinimumSize(QtCore.QSize(50, 22))
        self.layout.addWidget(self.delay[self.nrow], self.nrow, 2, 1, 1)

        self.scan[self.nrow] = QtWidgets.QRadioButton(self.widget)
        self.scan[self.nrow].setMinimumSize(QtCore.QSize(22, 22))
        self.layout.addWidget(self.scan[self.nrow], self.nrow, 3, 1, 1)
        scangroup.addButton(self.scan[self.nrow])

        self.index[self.nrow] = QtWidgets.QLabel(self.widget)
        self.index[self.nrow].setMinimumSize(QtCore.QSize(22, 22))
        self.index[self.nrow].setText(str(self.nrow+1))
        self.layout.addWidget(self.index[self.nrow], self.nrow, 4, 1, 1)

        self.pattn[self.nrow] = Pattern(self.widget, self.layout, self.nrow)
        if copy and self.nrow > 0:
            self.pattn[self.nrow].copyBits(self.pattn[self.nrow-1])
        self.nrow += 1
        # emit a signal if chapter size changed
        self.widget.resizeEvent()

    # removes one line from the chapter
    def del_line(self):
        if (self.nrow <= 2):
            return
        self.nrow -= 1
        # remove delay indicator
        self.layout.removeWidget(self.delay[self.nrow])
        self.delay[self.nrow].setParent(None)
        self.layout.removeWidget(self.scan[self.nrow])
        scangroup.removeButton(self.scan[self.nrow])
        self.scan[self.nrow].setParent(None)
        self.layout.removeWidget(self.index[self.nrow])
        self.index[self.nrow].setParent(None)
        
        # remove line of buttons
        self.pattn[self.nrow].delete()
        self.widget.setGeometry(QtCore.QRect(50, 20, PIXWIDTH, (self.nrow)* BITWIDTH))
        self.widget.setMinimumSize(QtCore.QSize(PIXWIDTH, (self.nrow) * BITWIDTH))
        # emit a signal if chaprer size changed
        self.widget.resizeEvent()


    # slot for active clicked signal
    def active_clicked(self):
        if self.active :
            self.setActive(False)
        else:
            self.setActive(True)

    # slot for plus button signal. Adds another line
    def plus_clicked(self):
        self.add_line()

    # slot for minus button signal. Removes last line
    def minus_clicked(self):
        self.del_line()

    # set the active state for the chapter
    def setActive(self, active):
        self.active = active
        # change color of the button
        if(self.active):
            self.activeButton.setStyleSheet(self.green)
        else:
            self.activeButton.setStyleSheet(self.gray)
        # make everything else disabled
        for i in self.pattn:
            self.pattn[i].setActive(self.active)
        for i in self.delay:
            self.delay[i].setEnabled(self.active)
        for i in self.scan:
            self.scan[i].setEnabled(self.active)

        self.plusButton.setEnabled(self.active)
        self.minusButton.setEnabled(self.active)
        self.name.setEnabled(self.active)

    def who(self):
        print("I am a Generic chapter")

# Enum for different types of sequence
class CHAP:
    Generic, SIDEBAND, DYNDECOUP, RAMSEY, CLASSIFIER = list(range((5)))


class SidebandChapterData(ChapterData):
    def __init__(self, nrow = 2, active = True, lines = [], name = "Sideband cooling"):
        self.name   = "Sideband cooling"
        self.nrow   = 2
        self.active = active
        self.lines  = lines[:]

        self.pumping_time  = 1  # default optical puming time (microseconds)
        self.raman_pi_time = 1  # raman pi time for the sideband transition (\eta \Omega)
        self.n_phonons     = 10 # initial number of phonons
        self.n_cycles      = 40 # initial number of the optical pumping cycles

    # Saves the sideband cooling configuration
    def setConfig(self, pumping_time, raman_pi_time, n_phonons, n_cycles):
        self.pumping_time  = pumping_time  # default optical puming time (microseconds)
        self.raman_pi_time = raman_pi_time  # raman pi time for the sideband transition (\eta \Omega)
        self.n_phonons     = n_phonons # initial number of phonons
        self.n_cycles      = n_cycles # initial number of the optical pumping cycles

    # Returns the sadeband cooling parameters
    def getConfig(self):
        return  self.pumping_time, self.raman_pi_time, self.n_phonons, self.n_cycles



# Class inherited from the main chapter class
class SidebandChapter(Chapter):
    def __init__(self, widget):
        Chapter.__init__(self, widget, 2)

        self.name.setText("Sideband cooling")
        self.name.setStyleSheet('color: red; background-color: yellow')
        self.name.setToolTip("This is a special chapter for the sideband cooling sequence")

        self.delay[0].setToolTip("Optical pumping pattern")
        self.delay[0].setEnabled(False)
        self.scan[0].setEnabled(False)
        self.delay[1].setToolTip("Raman transition pattern")
        self.delay[1].setEnabled(False)
        self.scan[1].setEnabled(False)

        self.plusButton.setEnabled(True)
        self.minusButton.setEnabled(True)
        self.plusButton.setToolTip("Configure the sideband cooling")
        self.minusButton.setToolTip("Configure the sideband cooling")
        self.plusButton.setStyleSheet('background-color: yellow')
        self.minusButton.setStyleSheet('background-color: yellow')
        self.plusButton.setText("Cfg")
        self.minusButton.setText("Cfg")

        self.cfg = sideband_ui_dialog()

        self.plusButton.clicked.disconnect(self.plus_clicked)
        self.minusButton.clicked.disconnect(self.minus_clicked)
        self.plusButton.clicked.connect(self.config_clicked)
        self.minusButton.clicked.connect(self.config_clicked)



    # returns the array of seqline objects that correspond to the chapter
    # HAS TO CHANGE IT for the sideband cooling !!!
    def appendData(self, seq):
        if (self.active == False):
            return seq

#        for i in range(self.nrow):
#            seq.append(SeqLine(self.delay[i].value(), self.scan[i].isChecked(), self.pattn[i].getPattern()))
#        return seq

        for i in range(self.cfg.n_cycles):
            raman_time = self.cfg.raman_pi_time / math.sqrt(1.0 + self.cfg.n_phonons * (1.0 - float(i+1.0) / float(self.cfg.n_cycles) ))
            seq.append(SeqLine(self.cfg.pumping_time, self.scan[0].isChecked(), self.pattn[0].getPattern()))
            seq.append(SeqLine(raman_time,            self.scan[1].isChecked(), self.pattn[1].getPattern()))
            print("Raman time is ", raman_time            )
        return seq
#        print("appendData SidebandSequence")

    # Gets all the data to save chapter to disk
    def getData(self):
        chapdata = SidebandChapterData(nrow = self.nrow, active = self.active, name = self.name.text())
        chapdata.setConfig(self.cfg.pumping_time, self.cfg.raman_pi_time, \
                           self.cfg.n_phonons, self.cfg.n_cycles )

        for i in range(self.nrow):
            chapdata.lines.append(SeqLine(self.delay[i].value(), self.scan[i].isChecked(), self.pattn[i].getPattern()))
        return chapdata
#        print("getData SidebandSequence")

    # Sets the data
    def setData(self, chapdata):
    # Add or remove rows in the chapter
        if (2 > self.nrow):
            for i in range(2 - self.nrow):
                self.add_line()
        elif (2 < self.nrow):
            for i in range(self.nrow - 2):
                self.del_line()
        self.nrow = 2
    # set rows
        for i in range(self.nrow):
            self.pattn[i].setPattern(chapdata.lines[i])
            self.delay[i].setValue(chapdata.lines[i].delay)
            self.scan[i].setChecked(False)
    # Set active data
        self.name.setText("Sideband cooling")
        self.setActive(chapdata.active)
    # Set sideband cooling specific data
        [ self.cfg.pumping_time, self.cfg.raman_pi_time,  \
          self.cfg.n_phonons, self.cfg.n_cycles ] =  \
         chapdata.getConfig()
#        print("setData SidebandSequence")

    # Override set active method of the parent class to disable +/- button
    def setActive(self, active):
        Chapter.setActive(self, active)
        self.plusButton.setEnabled(True)
        self.minusButton.setEnabled(True)
        for i in self.delay:
            self.delay[i].setEnabled(False)
            self.scan[i].setEnabled(False)

    # Click the config button
    def config_clicked(self):
        self.cfg.show()

    # print(who i am on the console, for debugging)
    def who(self):
        print("I am a SIDEBAND chapter")

###########################################

class DynDecoupChapterData(ChapterData):
    def __init__(self, nrow = 3, active = True, lines = [], name = "Dynamical Decoupling"):
        self.name   = "Dynamical Decoupling"
        self.nrow   = 3
        self.active = active
        self.lines  = lines[:]

        self.rabi_pi_time  = 2  # default Rabi PI time (microseconds)
        self.wait_time  = 2  # default Rabi PI time (microseconds)
        self.n_cycles      = 5 # initial number of DD pulses

    # Saves the dynamical decoupling parameters
    def setConfig(self, rabi_pi_time, wait_time, n_cycles):
        self.rabi_pi_time = rabi_pi_time  #  Rabi pi time for the sideband transition (\eta \Omega)
        self.wait_time = wait_time  #  wait time between PI pulses
        self.n_cycles      = n_cycles # initial number of DD pulses

    # Returns the dynamical decoupling parameters
    def getConfig(self):
        return  self.rabi_pi_time, self.wait_time, self.n_cycles



# Class inherited from the main chapter class
class DynDecoupChapter(Chapter):
    def __init__(self, widget):
        Chapter.__init__(self, widget, 3)

        self.name.setText("Dynamical Decoupling")
        self.name.setStyleSheet('color: black; background-color: cyan')

        self.name.setToolTip("This is a special chapter for dynamical decoupling sequence")

        self.delay[0].setToolTip("Waiting time pattern")
        self.delay[0].setEnabled(True)
        self.scan[0].setEnabled(True)
        self.delay[1].setToolTip("PI pulse pattern")
        self.delay[1].setEnabled(False)
        self.scan[1].setEnabled(False)
        self.delay[2].setToolTip("waiting time pattern")
        self.delay[2].setEnabled(False)
        self.scan[2].setEnabled(False)

        self.plusButton.setEnabled(True)
        self.minusButton.setEnabled(True)
        self.plusButton.setToolTip("Configure the DD pulses")
        self.minusButton.setToolTip("Configure the DD pulses")
        self.plusButton.setStyleSheet('color: black; background-color: cyan')
        self.minusButton.setStyleSheet('color: black; background-color: cyan')
        self.plusButton.setText("DD")
        self.minusButton.setText("DD")

        self.DD_cfg = DD_ui_dialog()

        self.plusButton.clicked.disconnect(self.plus_clicked)
        self.minusButton.clicked.disconnect(self.minus_clicked)
        self.plusButton.clicked.connect(self.config_clicked)
        self.minusButton.clicked.connect(self.config_clicked)



    # returns the array of seqline objects that correspond to the chapter
    # HAS TO CHANGE IT for the sideband cooling !!!
    def appendData(self, seq):
        if (self.active == False):
            return seq

#        for i in range(self.nrow):
#            seq.append(SeqLine(self.delay[i].value(), self.scan[i].isChecked(), self.pattn[i].getPattern()))
#        return seq
        self.pulseNo = int(self.DD_cfg.n_cycles)
        self.t1 = (self.DD_cfg.wait_time/self.DD_cfg.n_cycles-self.DD_cfg.rabi_pi_time)/2
        self.t2 = (self.DD_cfg.wait_time/self.DD_cfg.n_cycles-self.DD_cfg.rabi_pi_time)/2
        for i in range(self.pulseNo):
            seq.append(SeqLine(self.t1, self.scan[0].isChecked(), self.pattn[0].getPattern()))
            seq.append(SeqLine(self.DD_cfg.rabi_pi_time, self.scan[1].isChecked(), self.pattn[1].getPattern()))
            seq.append(SeqLine(self.t2, self.scan[2].isChecked(), self.pattn[2].getPattern()))
            # print("Rabi PI time is ", self.DD_cfg.rabi_pi_time)
        exWait = self.DD_cfg.wait_time*(1. - self.pulseNo/(self.DD_cfg.n_cycles))
        seq.append(SeqLine(exWait, self.scan[0].isChecked(), self.pattn[0].getPattern()))
        return seq
#        print("appendData SidebandSequence")

    # Gets all the data to save chapter to disk
    def getData(self):
        chapdata = DynDecoupChapterData(nrow = self.nrow, active = self.active, name = self.name.text())
        chapdata.setConfig(self.DD_cfg.rabi_pi_time, self.DD_cfg.wait_time, self.DD_cfg.n_cycles)

        for i in range(self.nrow):
            chapdata.lines.append(SeqLine(self.delay[i].value(), self.scan[i].isChecked(), self.pattn[i].getPattern()))
        return chapdata
#        print("getData SidebandSequence")

    # Sets the data
    def setData(self, chapdata):
    # Add or remove rows in the chapter
        if (3 > self.nrow):
            for i in range(3 - self.nrow):
                self.add_line()
        elif (3 < self.nrow):
            for i in range(self.nrow - 3):
                self.del_line()
        self.nrow = 3
    # set rows
        for i in range(self.nrow):
            self.pattn[i].setPattern(chapdata.lines[i])
            self.delay[i].setValue(chapdata.lines[i].delay)
            self.scan[i].setChecked(False)
    # Set active data
        self.name.setText("Dynamical Decoupling")
        self.setActive(chapdata.active)
    # Set sideband cooling specific data
        [ self.DD_cfg.rabi_pi_time, self.DD_cfg.wait_time, self.DD_cfg.n_cycles] =  \
         chapdata.getConfig()
#        print("setData SidebandSequence")

    # Override set active method of the parent class to disable +/- button
    def setActive(self, active):
        Chapter.setActive(self, active)
        self.plusButton.setEnabled(True)
        self.minusButton.setEnabled(True)
        for i in self.delay:
            self.delay[i].setEnabled(False)
            self.scan[i].setEnabled(False)
        if active:
            self.scan[2].setEnabled(True)

    # Click the config button
    def config_clicked(self):
        self.DD_cfg.show()

    # print(who i am on the console, for debugging)
    def who(self):
        print("I am a Dynamical Decoupling chapter")


##########################################

########################################### 24/09/2017 Ramsey fixed wait time #####

class RamseyChapterData(ChapterData):
    def __init__(self, nrow = 3, active = True, lines = [], name = "Ramsey WaitTime"):
        self.name   = "Ramsey WaitTime"
        self.nrow   = 3
        self.active = active
        self.lines  = lines[:]

# Class inherited from the main chapter class
class RamseyChapter(Chapter):
    def __init__(self, widget):
        Chapter.__init__(self, widget, 3)

        self.name.setText("Ramsey WaitTime")
        self.name.setStyleSheet('color: black; background-color: cyan')

        self.name.setToolTip("This is a special chapter for Ramsey sequence with fixed wait time")

        self.delay[0].setToolTip("short fixed Waiting time")
        self.delay[0].setEnabled(False)
        self.scan[0].setEnabled(False)
        self.delay[1].setToolTip("External field application time")
        self.delay[1].setEnabled(False)
        self.scan[1].setEnabled(False)
        self.delay[2].setToolTip("varied to keep fixed total time")
        self.delay[2].setEnabled(False)
        self.scan[2].setEnabled(False)

        self.plusButton.setEnabled(False)
        self.minusButton.setEnabled(False)
        self.plusButton.setToolTip("Ramsey fixed wait time")
        self.minusButton.setToolTip("Ramsey fixed wait time")
        self.plusButton.setStyleSheet('color: black; background-color: cyan')
        self.minusButton.setStyleSheet('color: black; background-color: cyan')
        self.plusButton.setText("Ramsey")
        self.minusButton.setText("Ramsey")

        # self.activeButton.buttonClicked.connect(self.scan_clicked_slot)



    # returns the array of seqline objects that correspond to the chapter
    # HAS TO CHANGE IT for the Ramsey or any special scans !!!
    def appendData(self, seq):
        if (self.active == False):
            return seq

        seq.append(SeqLine(1.0, self.scan[0].isChecked(), self.pattn[0].getPattern()))
        seq.append(SeqLine(0.1, self.scan[1].isChecked(), self.pattn[1].getPattern()))
        seq.append(SeqLine(1.0, self.scan[2].isChecked(), self.pattn[2].getPattern()))
        return seq

    # Gets all the data to save chapter to disk
    def getData(self):
        chapdata = RamseyChapterData(nrow = self.nrow, active = self.active, name = self.name.text())

        for i in range(self.nrow):
            chapdata.lines.append(SeqLine(self.delay[i].value(), self.scan[i].isChecked(), self.pattn[i].getPattern()))
        return chapdata

    # Sets the data
    def setData(self, chapdata):
        self.nrow = 3
    # set rows
        for i in range(self.nrow-1):
            self.pattn[i].setPattern(chapdata.lines[i])
            self.delay[i].setValue(chapdata.lines[i].delay)
            self.scan[i].setChecked(False)
    # Set active data
        self.name.setText("Ramsey WaitTime")
        self.setActive(chapdata.active)

    # Override set active method of the parent class to disable +/- button
    def setActive(self, active):
        Chapter.setActive(self, active)
        self.plusButton.setEnabled(False)
        self.minusButton.setEnabled(False)
        for i in self.delay:
            self.delay[i].setEnabled(False)
            self.scan[i].setEnabled(False)
        if active:
            self.scan[1].setEnabled(True)
            # self.scan[1].setChecked(True)

    # print(who i am on the console, for debugging)
    def who(self):
        print("I am a RAMSEY chapter")


##########################################

class ClassifierChapterData(ChapterData):
    def __init__(self, nrow = 3, active = False, lines = [], name = "Classifier"):
        self.name   = "Classifier"
        self.nrow   = nrow
        self.active = active
        self.lines  = lines[:]

        self.rabi_pi_time  = 2  # default Rabi PI time (microseconds)
        self.n_cycles      = self.nrow # initial number of classifier operations (depth)

    # Saves the classifier parameters
    def setConfig(self, rabi_pi_time, n_cycles, rabi_frequency, rabi_amplitude):
        self.rabi_pi_time = rabi_pi_time  #  Rabi pi time
        self.n_cycles      = n_cycles # initial number of classifier operations/data loading
        self.rabi_frequency = rabi_frequency
        self.rabi_amplitude = rabi_amplitude

    # Returns the classifier parameters
    def getConfig(self):
        return  self.rabi_pi_time, self.n_cycles, self.rabi_frequency, self.rabi_amplitude



# Class inherited from the main chapter class
class ClassifierChapter(Chapter):
    def __init__(self, widget):
        Chapter.__init__(self, widget, 2)

        self.name.setText("Classifier")
        self.name.setStyleSheet('color: black; background-color: cyan')

        self.name.setToolTip("This is a special chapter for Classifier sequence")


        self.deActivateDelay(2)
        self.plusButton.setEnabled(True)
        self.minusButton.setEnabled(True)
        self.plusButton.setToolTip("Configure the Classifier pulses")
        self.minusButton.setToolTip("Apply new configuration")
        self.plusButton.setStyleSheet('color: black; background-color: cyan')
        self.minusButton.setStyleSheet('color: black; background-color: lightgreen')
        self.plusButton.setText("CF")
        self.minusButton.setText("Go")

        self.CF_cfg = CF_ui_dialog()

        self.plusButton.clicked.disconnect(self.plus_clicked)
        self.minusButton.clicked.disconnect(self.minus_clicked)
        self.plusButton.clicked.connect(self.config_clicked)
        self.minusButton.clicked.connect(self.config_applied)
    # returns the array of seqline objects that correspond to the chapter

    def deActivateDelay(self, n):
        self.scan[0].setChecked(True)

        for i in range(n):
            self.delay[i].setToolTip("Sigma_Y rotation")
            self.delay[i].setEnabled(False)
            self.scan[i].setEnabled(False)


    def appendData(self, seq):
        if (self.active == False):
            return seq
        for i in range(self.nrow):
            seq.append(SeqLine(self.CF_cfg.rabi_pi_time/np.pi, self.scan[i].isChecked(), self.pattn[i].getPattern()))
        print("Classifier Rabi PI time is ", self.CF_cfg.rabi_pi_time/np.pi)
        return seq

    # Gets all the data to save chapter to disk
    def getData(self):
        chapdata = ClassifierChapterData(nrow = self.nrow, active = self.active, name = self.name.text())
        chapdata.setConfig(self.CF_cfg.rabi_pi_time, self.CF_cfg.n_cycles, self.CF_cfg.rabi_frequency, self.CF_cfg.rabi_amplitude)

        for i in range(self.nrow):
            chapdata.lines.append(SeqLine(self.delay[i].value(), self.scan[i].isChecked(), self.pattn[i].getPattern()))
        return chapdata

    # Sets the data
    def setData(self, chapdata):
        for i in range(self.nrow):
            self.pattn[i].setPattern(chapdata.lines[i])
            self.delay[i].setValue(chapdata.lines[i].delay)
            self.scan[i].setChecked(True)
    # Set active data
        self.name.setText("Classifier")
        self.setActive(chapdata.active)
    # Set classifier specific data
        [ self.CF_cfg.rabi_pi_time, self.CF_cfg.n_cycles, self.CF_cfg.rabi_frequency, self.CF_cfg.rabi_amplitude] =  \
         chapdata.getConfig()

    # Override set active method of the parent class to disable +/- button
    def setActive(self, active):
        Chapter.setActive(self, active)
        self.plusButton.setEnabled(True)
        self.minusButton.setEnabled(True)
        for i in self.delay:
            self.delay[i].setEnabled(False)
            self.scan[i].setEnabled(False)
        if active:
            self.scan[0].setChecked(True)

    # Click the config button
    def config_clicked(self):
        # print(self.CF_cfg.n_gates)
        self.CF_cfg.show()

    def config_applied(self):
        # Each gate consists of an Ry Gate and an Rz Gate
        n_gates = self.CF_cfg.n_gates * 2
        if self.nrow < n_gates:
            for i in range(n_gates-self.nrow):
                self.add_line(copy=True)
        elif self.nrow > n_gates:
            for i in range((self.nrow-n_gates)):
                self.del_line()
        self.nrow = n_gates
        self.deActivateDelay(self.nrow)

    # print(who i am on the console, for debugging)
    def who(self):
        print("I am a Classifier chapter")


##########################################


#########################################


# generate sequence that consist of several chapters
class Sequence():
    def __init__(self, widget, chapter_list):
        self.widget = widget
        self.vlayout = QtWidgets.QVBoxLayout(self.widget)
        self.vlayout.setObjectName("verticalLayout")

        self.chapter = {}
        self.wchap   = {}

        # Draw labels on the top
        self.wlabels  = QtWidgets.QWidget(self.widget)
        self.vlayout.addWidget(self.wlabels)
        self.labels   = Labels(self.wlabels)

        nChapters = len(chapter_list)

        # Draw chapters
        for i in range(nChapters):
            self.wchap[i] = QtWidgets.QWidget(self.widget)
            self.vlayout.addWidget(self.wchap[i])

            if (chapter_list[i] == CHAP.Generic):
                self.chapter[i] = Chapter(self.wchap[i], 2)
            elif (chapter_list[i] == CHAP.SIDEBAND):
                self.chapter[i] = SidebandChapter(self.wchap[i])
            elif (chapter_list[i] == CHAP.DYNDECOUP):
                self.chapter[i] = DynDecoupChapter(self.wchap[i])
            elif (chapter_list[i] == CHAP.RAMSEY):
                self.chapter[i] = RamseyChapter(self.wchap[i])
            elif (chapter_list[i] == CHAP.CLASSIFIER):
                self.chapter[i] = ClassifierChapter(self.wchap[i])

#           self.chapter[i] = Chapter(self.wchap[i], 2)
            self.wchap[i].resizeEvent = self.resize

        for i in range(nChapters):
            self.chapter[i].who()

    # resize time sequence widget
    def resize(self, event=None):
        nrow = 0
        # print(self.chapter)
        for i in self.chapter:
            nrow += self.chapter[i].nrow
        nrow += 2 # space for labels
        self.widget.setMinimumSize(QtCore.QSize(PIXWIDTH, nrow * 32))
        self.widget.setMaximumSize(QtCore.QSize(PIXWIDTH, nrow * 32))

    def get(self):
        data = []
        for i in self.chapter:
            data = self.chapter[i].appendData(data)
        return data

    # Returns name of the selected chapter and line number for scanning
    def getScanLine(self):
        for i in self.chapter:
            name, line = self.chapter[i].getScanLine()
            if (line >= 0):
                return name, line
        return "", -1


    # retieves all the data to save it in the file
    def getData(self):
        data = []
        for i in self.chapter:
            data.append(self.chapter[i].getData())
        return data

    # save sequence data to a file
    def save(self, file):
        pickle.dump(self.getData(), file)

    # loads sequence data from a file and updates GUI
    def load(self, file):
        try:
            data = pickle.load(file)
            for i in self.chapter:
                self.chapter[i].setData(data[i])
        except Exception as e:
            print(f'Failed to set chapters due to: {e}')

    def addChapter(self, newChapter):

        lenChapter = len(self.chapter)+1

        # Draw chapters
        self.wchap[lenChapter] = QtWidgets.QWidget(self.widget)
        self.vlayout.addWidget(self.wchap[lenChapter])

        if (newChapter == CHAP.Generic):
            self.chapter[lenChapter] = Chapter(self.wchap[lenChapter], 2)
        elif (newChapter == CHAP.SIDEBAND):
            self.chapter[lenChapter] = SidebandChapter(self.wchap[lenChapter])
        elif (newChapter == CHAP.DYNDECOUP):
            self.chapter[lenChapter] = DynDecoupChapter(self.wchap[lenChapter])
        elif (newChapter == CHAP.RAMSEY):
            self.chapter[lenChapter] = RamseyChapter(self.wchap[lenChapter])
        elif (newChapter == CHAP.CLASSIFIER):
            self.chapter[lenChapter] = ClassifierChapter(self.wchap[lenChapter])

        self.resize()
        self.chapter[lenChapter].who()
        self.chapter[lenChapter].setActive(False)

    def removeChapters(self):
        if self.vlayout is not None:
            old_layout = self.vlayout
            for i in range(old_layout.count()-1,0,-1):
                old_layout.itemAt(i).widget().setParent(None)

    def get_classifier_pi_time(self):
        for i in self.chapter:
            name, _ = self.chapter[i].getScanLine()
            if name == 'Classifier':
                return self.chapter[i].getData().getConfig()
        return -1

# Main widget
#class MyTest(QtWidgets.QDialog):
class TimeSeqWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None, master=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.master = master
        self.ui = UI_ChapterWindow()
        self.ui.setupUi(self)

        # self.chapter_list = [CHAP.Generic]
        #
        # self.sequence = Sequence(self.ui.widget, \
        #                           self.chapter_list) # initial chapters in window
        # self.sequence.resize() # window resize with scroll active
        #
        # self.fpga     = FPGA_Seq()  # need the sequence module to connect to FPGA and send time data
        #
        # self.setUSBStatus(self.fpga.usbstatus) # allow viewing the status of the USB on time window
        #
        # self.ui.actionRun.triggered.connect(
        #                        self.run_slot)
        #
        # self.ui.actionSave.triggered.connect(
        #                        self.save_slot)
        #
        # self.ui.actionLoad.triggered.connect(
        #                        self.load_slot)
        #
        # self.ui.actionConfigure.triggered.connect(
        #                        self.config_slot)
        #
        # self.ui.actionGeneric.triggered.connect(
        #                        partial(self.buildSequence, self.ui.actionGeneric.text()))
        #
        # self.ui.actionSideband.triggered.connect(
        #                        partial(self.buildSequence, self.ui.actionSideband.text()))
        #
        # self.ui.actionDynamical_Decoupling.triggered.connect(
        #                        partial(self.buildSequence, self.ui.actionDynamical_Decoupling.text()))
        #
        # self.ui.actionRamsey.triggered.connect(
        #                        partial(self.buildSequence, self.ui.actionRamsey.text()))
        #
        # self.ui.actionMulti_Single_Qubit_Gate.triggered.connect(
        #                        partial(self.buildSequence, self.ui.actionMulti_Single_Qubit_Gate.text()))

        # self.ui.actionRemove_All_Chapters.triggered.connect(
        #                        self.clearChapters)

#        self.fpga.usb.read_thread.data_ready.connect(self.data_ready_slot)

        # self.lastWindowClosed.connect(self.stop_slot)

        # scangroup.buttonClicked.connect(self.scan_clicked_slot)

        # Load default time sequence
        # self.load_file()
#        self.fpga.usbstatus.connect(
#                               self.setUSBStatus)

#########################

        self.sequence = Sequence(self.ui.widget,
                                 [CHAP.Generic])
        self.sequence.resize()

        # self.fpga = FPGA_Seq()
        # self.setUSBStatus(self.fpga.usbstatus)

        # self.ui.runButton.clicked.connect(self.run_slot)
        self.ui.saveButton.clicked.connect(self.save_slot)
        self.ui.loadButton.clicked.connect(self.load_slot)
        # self.ui.configButton.clicked.connect(self.config_slot)

        #        self.fpga.usb.read_thread.data_ready.connect(self.data_ready_slot)

        # scangroup.buttonClicked.connect(self.scan_clicked_slot)

        # Load default time sequence
        # self.load_file()

    #        self.fpga.usbstatus.connect(
    #                               self.setUSBStatus)

    #########################

    # print(the time sequence )
    def write(self):
        s = self.sequence.get()
        for i in s:
            i.write()

    # uploads new time sequence to an fpga
    # def config_slot(self):
    #     self.fpga.setSeq(self.sequence.get())
    #     self.save_tofile() # Saves to the default time sequence


    #  runs a loaded time sequence
    # def run_slot(self, reload = True):
    #     if (reload):
    #         self.fpga.setSeq(self.sequence.get())
    #         self.save_tofile() # Saves to the default time sequence
    #     self.fpga.run()

    # def scan_clicked_slot(self, button):
    #     name, line = self.sequence.getScanLine()
    #     self.master.delay_scan.scan_line_slot(name, line)
    #     # print("Button ", name, " Line ", line ," clicked")

    # Save timesequence to file
    def save_slot(self):
        home_dir = str(pathlib.Path.home())
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Open file', home_dir)[0]
        if ( filename == "" ):
            return
        self.save_tofile(filename)
#        file = open(filename, "wb")
#        pickle.dump(self.sequence.getData(), file)
#        file.close()

    # saves data to the default file, will read this file upon the startup
    def save_tofile(self, filename = "default_timeseq.dat"):
        try:
            file = open(filename, "wb")
            pickle.dump(self.sequence.getData(), file)
            file.close()
        except:
            print("Can't save timesequence to the default file " + filename)
            traceback.print_exc()

    # loads timesequence from file
    def load_slot(self):
        filename = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '', 'Sequence data (*.dat)')[0]
        if filename != '': self.load_file(filename)
#        file = open(filename, "rb")
#        self.sequence.load(file)
#        file.close()

    # loads timesequence data from file
    def load_file(self, filename):
        try:
            file = open(filename, "rb")
            # print(file)
            self.sequence.load(file)
            file.close()
        except:
            print("Can't load the sequence file " + filename)
            traceback.print_exc()


    # closes USB connection
    def closeEvent(self, event):
        # self.fpga.usb.close()
        event.accept()

    # def nrep_changed_slot(self, value):
    #     self.fpga.setNrep(value)

    # # change delay, reconfigure fpga and run a time sequence
    # def scan_delay_slot(self, delay):
    #
    #     # Change delay and reload time sequence
    #     seq = self.sequence.get()
    #     for i in seq:
    #         if i.scanned:
    #             i.delay = delay
    #     self.fpga.setSeq(seq)
    #
    #     # run the time sequence
    #     self.fpga.run()

    # change delay, reconfigure fpga and run a time sequence ###########revised on 25/09/17

    # def scan_delay_slot(self, delay, stop):
    #     # print(delay)
    #     # Change delay and reload time sequence
    #     seq = self.sequence.get()
    #     name, line = self.sequence.getScanLine()
    #     if name == 'Ramsey WaitTime':
    #         for i,j in enumerate(seq,start=-1):
    #             if j.scanned:
    #                 seq[i].delay = delay
    #                 seq[i+1].delay= stop-delay
    #     elif name == 'Dynamical Decoupling':
    #         for i,j in enumerate(seq,start=-1):
    #             if j.scanned:
    #                 seq[i-1].delay = seq[i-1].delay - delay
    #                 seq[i-2].delay= seq[i-2].delay + delay
    #     elif name == 'Classifier':
    #         for i,j in enumerate(seq,start=0):
    #             if j.scanned:
    #                 for delay_ in delay:
    #                     print(f'Raw Ry delays: {delay_}')
    #                 for item in range(len(delay)):
    #                     # print(seq[i+item].delay)
    #                     RZ_DELAY = 1.1
    #                     seq[i+item*2].delay = seq[i+item*2].delay*delay[item] - RZ_DELAY
    #                     seq[i+item*2+1].delay = RZ_DELAY
    #                 for k in range(len(delay)*2):
    #                     print(f'Classifier delay[{k}]: {seq[i+k].delay}')
    #             else:
    #                 continue
    #             # i=i+len(delay)
    #     else:
    #         for i in seq:
    #             if i.scanned:
    #                 i.delay = delay

    #     self.fpga.setSeq(seq)
    #     # run the time sequence
    #     self.fpga.run()

# Appends data to display buffer when they are ready
#    def data_ready_slot(self, data):
        # print(data)
#        self.ui.rcvText.append(str(data))



    # updates USB status string
    # def setUSBStatus(self, status):
    #     if (status == 0):
    #         self.ui.labelUSB.setText("FPGA is connected")
    #     if (status == -1) :
    #         self.ui.labelUSB.setText("Can't connect to FPGA")
    #         self.ui.labelUSB.setStyleSheet("QLabel { background-color : red; color : blue; }")


    def buildSequence(self, q):
        newChap = CHAP.Generic
        if q == 'Generic':
            newChap = CHAP.Generic
        elif q == 'Sideband Cooling':
            newChap = CHAP.SIDEBAND
        elif q == 'Ramsey':
            newChap = CHAP.RAMSEY
        elif q == 'Dynamical Decoupling':
            newChap = CHAP.DYNDECOUP
        elif q == 'Multi Single Qubit Gate':
            newChap = CHAP.CLASSIFIER

        self.sequence.addChapter(newChap) # initial chapters in window

    def clearChapters(self):

        self.sequence.removeChapters()

    def get_classifier_pi_time(self):
        return self.sequence.get_classifier_pi_time()

# main function to test GUI
def main():
    app = QtWidgets.QApplication(sys.argv)
#   myapp = MyByte()
#   myapp.show()
    myapp = TimeSeqWindow()
    myapp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()