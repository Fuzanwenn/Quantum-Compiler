# -*- coding:utf-8 -*-
"""
BY Fu Zanwen @ CQT
June 2024
"""

import csv
import pickle
import select
import timeseq_p2v2
import guibyte_scroll
import pandas as pd
import ast
import glob
import command_func
import sys
import os
from io import StringIO
from PyQt6 import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QTimer
from new_timeseq_p2v2 import Chapter, ChapterData, Sequence, SidebandChapter, SidebandChapterData, DynDecoupChapter, \
      DynDecoupChapterData, RamseyChapter, RamseyChapterData, ClassifierChapter, ClassifierChapterData
from fpgaseq import FPGA_Seq
from mainwin import IonApp, newIonApp
import time
import threading
from PyQt5.QtCore import QCoreApplication, QTimer, pyqtSignal, QObject, QThread
from plot import get_single_timeseq_hist, get_single_timeseq_hist_threshold
from multiprocessing import Process
import matplotlib.pyplot as plt
import queue
import matplotlib.ticker as ticker
from matplotlib.ticker import MaxNLocator
from scandata import ScanData
import tty
import termios
from threading import Thread, Event

pause_event = Event()
quit_event = Event()
app = QtWidgets.QApplication(sys.argv)
data_queue = queue.Queue()
color_list = {'a':'red', 'b':'green', 'c':'blue', 'd':'yellow', 'e':'purple', 'f':'black', 'g':'pink'}

pause_event.set()
# class SignalEmitter(QObject):
#     quit_signal = pyqtSignal()

# # Create an instance of SignalEmitter to handle signals
# signal_emitter = SignalEmitter()
running = True
threshold = 0
scantype = ""
starting_value = None

def unpickle(path):
    with open(path, "rb") as f:
        unpickled_data = pickle.load(f)
        chapter_list = []

        for d in unpickled_data:
            curr_line = dict()
            curr_line["name"] = d.name
            curr_line["nrow"] = d.nrow
            curr_line["active"] = d.active
            curr_line["lines"] = []

            for l in d.lines:
                curr_seqline_obj = dict()
                curr_seqline_obj["delay"] = l.delay
                curr_seqline_obj["bitarray"] = l.bitarray
                curr_seqline_obj["scanned"] = l.scanned

                curr_line["lines"].append(curr_seqline_obj)
                # print(curr_line["lines"])
            chapter_list.append(curr_line)
    f.close()
    # print(chapter_list)
    return chapter_list

def export_csv(chapter_list):
    for chapter in chapter_list:
        name = chapter["name"]

        bitarray_dataframe = pd.DataFrame()
        delay_list = []
        scan_list = []
        i = 0
        for line in chapter["lines"]:
            delay_list.append(line["delay"])
            scan_list.append(line["scanned"])
            curr_frames = [bitarray_dataframe, pd.DataFrame(line["bitarray"], index=[i])]
            bitarray_dataframe = pd.concat(curr_frames)
            i += 1
            
        delay_dataframe = pd.DataFrame({"delay":delay_list})
        scan_dataframe = pd.DataFrame({"scan":scan_list})
        delay_scan_dataframe = delay_dataframe.reset_index(drop=True).join(scan_dataframe)
        curr_dataframe = delay_scan_dataframe.reset_index(drop=True).join(bitarray_dataframe)

        if (os.getcwd() == "D:\Center for Quantum Technologies"):
            curr_dataframe.to_csv(os.path.join("src", "iongui", "data", f"{name}.csv"), sep=',', index=False)
        else:
            curr_dataframe.to_csv(os.path.join(f"{name}.csv"), sep=',', index=False)

def modify_character(s, index, new_char):
    if index < 0 or index >= len(s):
        raise IndexError("Index out of range")
    char_list = list(s)
    char_list[index] = str(new_char)
    return ''.join(char_list)

def function_apply(content, row, func, increment):
    row_content = content[row].strip()
    row_content = row_content.split(",")

    if "." in row_content[0]:
        row_content[0] = str(func(float(row_content[0]), increment))
    else:
        row_content[0] = str(func(int(row_content[0]), increment))

    row_content = ','.join(row_content)
    row_content += "\n"
    return row_content

# Initialize Chapter object -> Set data -> Put Chapters into a Sequence -> Set fpga -> Run fpga.
def setSequence(waiting_files):

    sequence = Sequence()
    
    for curr_file_name in waiting_files.keys():
        curr_file_df_list = waiting_files[curr_file_name]
        # breakpoint()
        for curr_file_df in curr_file_df_list:
            curr_nrow = curr_file_df.shape[0]

            if curr_file_name == "Classifier":
                chapter = ClassifierChapter()
                curr_chapterData = ClassifierChapterData(curr_file_df)
                print("Chapter type: Classifier")

            elif curr_file_name == "Dynamical Decoupling":
                chapter = DynDecoupChapter()
                curr_chapterData = DynDecoupChapterData(curr_file_df)
                print("Chapter type: Dynamical Decoupling")

            elif curr_file_name == "Ramsey WaitTime":
                chapter = RamseyChapter()
                curr_chapterData = RamseyChapterData(curr_file_df)
                print("Chapter type: Ramsey WaitTime")

            elif curr_file_name == "Sideband cooling":
                chapter = SidebandChapter()
                curr_chapterData = SidebandChapterData(curr_file_df)
                print("Chapter type: Sideband cooling")

            else:
                chapter = Chapter(curr_nrow, curr_file_name)
                curr_chapterData = ChapterData(curr_file_name, curr_nrow, curr_file_df)
                print("Chapter type: Generic")

            chapter.setData(curr_chapterData)
            sequence.setData(chapter)

            print(f"Loaded file: {curr_file_name} to Sequence.")
            print(curr_file_df)
    return sequence

def get_rep(path):
    command_txt = open(path, "r")
    first_line = command_txt.readline()
    num_of_experiment = int(first_line.split(";")[0].strip())
    num_of_execution_per_exp = int(first_line.split(";")[1].strip())
    return [num_of_experiment, num_of_execution_per_exp]

# To be updated:
# 1. Resolve issue: number of experiments set up [Done]
# 2. Add in hist['b'] histogram [Done]
# 3. Split run and execute_command, follow OOP. [Done]
# 4. Remove GUI entirely
# 5. Plot the diagram [Done]
def execute_fpga_command(path, waiting_files={}):
    input_waiting_files = len(waiting_files)
    command_txt = open(path, "r")
    total_command_lines = command_txt.readlines()

    print("Start modifying user's commands.")
    for command_line in total_command_lines[1:]:
        sep_msg = [x.strip() for x in command_line.split(";")]
        csv_file_name = sep_msg[0]

        # try:
        if len(sep_msg) == 1 or sep_msg[1] == '':
            if csv_file_name not in waiting_files.keys():
                if (os.getcwd() == "D:\Center for Quantum Technologies"):
                    df = pd.read_csv(os.path.join("src", "iongui", "data", f"{csv_file_name}.csv"))
                else:
                    df = pd.read_csv(os.path.join(f"{csv_file_name}.csv"))
                waiting_files[csv_file_name] = [df]
            else:
                if (input_waiting_files == 0):
                    waiting_files[csv_file_name].append(df)
            print(f"No instruction on file: {csv_file_name}.")
            continue
        # except:
        #     print(f"Please check the spelling of file name: {csv_file_name}!")
        #     break

        print("Modifying file: ", csv_file_name)
        print("The parsed command is: ", sep_msg)


        if csv_file_name not in waiting_files.keys():
            # Open modify_csv_file:
            if (os.getcwd() == "D:\Center for Quantum Technologies"):
                modify_csv_file = open(os.path.join("src", "iongui", "data", f"{csv_file_name}.csv"), "r")
            else:
                modify_csv_file = open(os.path.join(f"{csv_file_name}.csv"), "r")
            curr_file_content = modify_csv_file.readlines()

            modify_command = sep_msg[1]
            try:
                executable_command = ast.literal_eval(modify_command)
                # Modifying variables command.
                if isinstance(executable_command, tuple):
                    row_num = executable_command[0]
                    value_to_modify = executable_command[1]
                    row_to_modify = curr_file_content[row_num].split(",")
                    row_to_modify[0] = str(value_to_modify)
                    curr_file_content[row_num] = ','.join(row_to_modify)
                    print(f"Modified delay value to {value_to_modify}.")
                # Type of input is not correct.
                else:
                    print("No type found ", type(executable_command))
            except Exception as e:
                print(f"{e} during initialising the data in {csv_file_name}!")

            # After modifying a file, convert it to a Dataframe object.
            csv_data = ''.join(curr_file_content)
            df = pd.read_csv(StringIO(csv_data))
            waiting_files[csv_file_name] = [df]

    print("Finished running user's command.")
    # breakpoint()
    return waiting_files

def execute_dds_command(ionmain, path):
    command_txt = open(path, "r")
    total_command_lines = command_txt.readlines()

    for command_line in total_command_lines:
        command = command_line.split(",")
        sernum = command[0].strip()
        if len(sernum) == 0:
            continue
        colname = command[1].strip()
        value = command[2].strip()

        if colname.lower() == "mode":
            ionmain.updateDDSMode(sernum, value)
            time.sleep(1)
            print(f"Initialised DDS {sernum} mode to {value}.")
        else:
            if command_line != total_command_lines[-1]:
                ionmain.setDDSValue(sernum, colname, float(value))
                time.sleep(1)
                print(f"Initialised DDS {sernum} {colname} to {value}.")
            else:
                ionmain.setDDSValue2(sernum, colname, float(value))
                time.sleep(1)
                print(f"Initialised DDS {sernum} {colname} to {value}.")
        
def execute_scan_command(ionmain, waiting_files, path):
    command_txt = open(path, "r")
    total_command_lines = command_txt.readlines()

    for command_line in total_command_lines:
        command = command_line.split(",")
        scantype = command[0].strip()
        if len(scantype) == 0:
            continue
        if scantype.lower() == "freqscan":
            sernum = command[1].strip()
            colname = command[2].strip()
            value = command[3].strip()
            freq = freqscan(ionmain, sernum, colname, value)
            filename = f"freq={freq}"
            print("Finished running freq scan.")
            
        elif scantype.lower() == "delayscan":
            chaptername = command[1].strip()
            row = command[2].strip()
            value = command[3].strip()
            delay, waiting_files = delayscan(waiting_files, chaptername, row, float(value))
            filename = f"delay={delay}"
            print("Finished running delay scan.")

        elif len(scantype) != 0:
            print(f"{scantype} is not implemented!")

    return filename, waiting_files



def freqscan(ionmain, sernum, col, value):
    if col.lower() == "mode":
        newmode = value
        ionmain.updateDDSMode(sernum, newmode)
        print(f"Updated DDS {sernum} mode to {newmode}.")
    else:
        increment = float(value)
        ionmain.updateDDSValue(sernum, col, increment)
        newValue = ionmain.getDDSValue(sernum, col)
        print(f"Incremented DDS {sernum} to {newValue}.")
    
    return ionmain.getDDSValue(sernum, col)


def delayscan(waiting_files, chaptername, row, value):
    df_list = waiting_files[chaptername]
    for df in df_list:
        row = int(row)
        delay = df.iloc[row-1, 0]
        df.iloc[row-1, 0] = float(df.iloc[row-1, 0]) + float(value)
        break
    waiting_files[chaptername] = df_list
    return delay, waiting_files
    

def saveHist(num_of_experiment, value, hist, name, ionNo, threshold=0):
    if name.startswith("delay"):
        folder = "delayscan"
        scantype = "delay="
    elif name.startswith("freq"):
        folder = "freqscan"
        scantype = "freq="
    # Ensure the folder exists
    if not os.path.exists(folder):
        os.makedirs(folder)
    hist_file = open(os.path.join(folder, f"{name}.dat"), "wb+")
    # writer = csv.writer(hist_file)
    # col_name = ["ionNo", "Num of Exp", "Value", "Tag"] + list(range(0, 1024))
    # writer.writerow(col_name)
    hist_dict = {}
    for tag in hist.keys():

        hist_dict[tag] = {}
        hist_dict[tag]["ionNo"] = ionNo
        hist_dict[tag]["num of exp"] = num_of_experiment
        hist_dict[tag]["value"] = value
        hist_dict[tag]["list"] = hist[tag]
    data_queue.put((name.removeprefix(scantype), get_single_timeseq_hist_threshold(hist, threshold)))

    pickle.dump(hist_dict, hist_file)
    print("Saved histograms to dat file.")

def removeFolder(scantype):
    if scantype == "delayscan":
        files = glob.glob(os.path.join("delayscan", '*'))
    elif scantype == "freqscan":
        files = glob.glob(os.path.join("freqscan", '*'))
    
    for file in files:
        if os.path.isfile(file):
            os.remove(file)

# delete old result folders [Done]
# normalize
# stop n resume [Done]
# live plot [Done]
# no while true [Done]


def saveScanData(scandata):
    file = open(os.path.join(scantype, "scandata.dat"), "wb+")
    pickle.dump(scandata, file)

def getScanRange():
    file = open("everything.txt", "r")
    content = file.readlines()
    isScan = False
    for line in content:
        line = line.strip()
        if line.startswith("$ Scan Type"):
            isScan = True
            continue
        if len(line) != 0 and isScan:
            scan_commands = [x.strip() for x in line.strip().split(",")]
            scantype, scan_target, parameter, start, stop, increment = scan_commands
            return start, increment

def run(fpga_path, dds_path, scan_path):
    fpga = FPGA_Seq()
    ionmain = IonApp()
    scandata = ScanData()
    global running, threshold, starting_value
    
    num_of_experiment = get_rep(fpga_path)[0]
    num_of_execution_per_exp = get_rep(fpga_path)[1]
    start, increment = getScanRange()
    scanvalue = float(start)
    # Step 1: Set up user's DDS settings.
    execute_dds_command(ionmain, dds_path)
    # breakpoint()
    print("Finished setting up DDS.")

    # ionmain.set_fpga(fpga)
    fpga.setNrep(num_of_execution_per_exp)

    for experiment_iteration in range(num_of_experiment):
        if not running:
            print("Worker stopping...")
            break
        print(f"Starting the {experiment_iteration+1} experiment.")
        pause_event.wait()

        # Step 2: Set up fpga sequences.
        if experiment_iteration == 0:
            waiting_files = execute_fpga_command(fpga_path)
        else:
            waiting_files = execute_fpga_command(fpga_path, new_waiting_files)
        sequence = setSequence(waiting_files)
        # ionmain.set_sequence(sequence)
        fpga.setSeq(sequence.get())
        
        print("Finished setting up fpga sequences.")

        # Create a local event loop to wait for the hready signal
        event_loop = QtCore.QEventLoop()

        # Connect the hready signal to quit the event loop when data is ready
        fpga.hready.connect(event_loop.quit)

        # Step 3: Run fpga sequences.
        # fpga.fake_data_ready_slot()
        # breakpoint()
        fpga.run()

        event_loop.exec_()

        # while True:
        #     try:
        ionmain.set_histrogram(fpga.hist)
        ionNo = ionmain.ion_data.get_ionNo()
        scandata.ydata(ionNo)
        value, final_hist, scandata = ionmain.save_data_slot(scandata, scanvalue)
        scanvalue += float(increment)
            #     break
            # except:
            #     continue
        
        print("Finished running fpga sequences.")

        # Step 4: Update values based on type of scan.
        filename, new_waiting_files = execute_scan_command(ionmain, waiting_files, scan_path)

        print("Finished running scan.txt.")

        # Step 5: Save histograms after this run.
        saveHist(num_of_experiment, value, final_hist, filename, ionNo, threshold)
        print(f"Finished running program {num_of_execution_per_exp} times.")
        print(f"Finished {experiment_iteration+1} times of experiment.")

    # Step 6: Reset DDS Settings.
    saveScanData(scandata)
    ionmain.resetDDSDefault()
    print("Finished running entire program.")
    print(scandata.getx())

def calculate_exp_num(start, end, step):
    global starting_value
    starting_value = start
    if start > end:
        temp_end = start
        start = end
        end = temp_end
    num = 0
    while start <= end:
        num += 1
        start += abs(step)
    return num

def find_indexes(lst, element):
    return [index for index, value in enumerate(lst) if value == element]

def generate_everything(path):
    global threshold, scantype
    file = open(path, "r")
    file_content = file.read()
    everything = file_content.split("$")
    for line in everything:
        curr_line = line.strip()
        if len(curr_line) == 0:
            continue
        curr_line = curr_line.split("\n")
        print(curr_line)

        target_object = curr_line[0]
        if target_object.startswith("DDS"):
            dds_file = open("dds_settings.txt", "w+")
            for command in curr_line[1:]:
                if len(command.strip()) == 0:
                    continue
                dds_file.write(command.strip()+"\n")

        elif target_object.startswith("Number"):
            for command in curr_line[1:]:
                if len(command.strip()) == 0:
                    continue
                nrep = command.strip()
                break

        elif target_object.startswith("Fpga"):
            fpga_file = open("fpga_commands.txt", "w+")
            fpga_seq = []
            for command in curr_line[1:]:
                if len(command.strip()) == 0:
                    continue

                if len(command.strip().split(",")) == 1:
                    fpga_seq.append(command.strip())
                    export_csv(unpickle(f"{command.strip()}.dat"))
                    continue
                command = command.strip()
                gate = command.split(",")[0].strip()
                repeat_time = int(command.split(",")[1].strip())
                for i in range(repeat_time):
                    fpga_seq.append(gate)
                export_csv(unpickle(f"{gate}.dat"))
        
        elif target_object.startswith("Scan"):
            scan_file = open("scan.txt", "w+")
            for command in curr_line[1:]:
                if len(command.strip()) == 0:
                    continue
                scan_commands = [x.strip() for x in command.strip().split(",")]
                scantype, scan_target, parameter, start, stop, increment = scan_commands
                # start = float(start) - float(increment)
                num_of_experiments = calculate_exp_num(float(start), float(stop), float(increment))
                try:
                    fpga_file.write(str(num_of_experiments) + "; " + nrep + "\n")
                except UnboundLocalError:
                    fpga_file.write(str(num_of_experiments) + "; " + "100" + "\n")
                scan_file.write(scantype + ", " + scan_target + ", " + parameter + ", " + increment)
                if scantype == "freqscan":
                    dds_file.write(scan_target + ", " + parameter + ", " + start)
                elif scantype == "delayscan":
                    indexes = find_indexes(fpga_seq, scan_target)
                    fpga_seq[fpga_seq.index(scan_target)] += "; " + f"({parameter}, {start})"
                [fpga_file.write(x+"\n") for x in fpga_seq]
                break

        elif target_object.startswith("Threshold"):
            for command in curr_line[1:]:
                if len(command.strip()) == 0:
                    continue
                threshold = int(command.strip())
                break

    print("Finished loading user's commands.")


def quit_app():
    QtWidgets.QApplication.quit()

def quit_all_threads():
    """Stop all running threads and quit the application."""
    print("Stopping all threads...")
    # Wait for all threads to finish
    for thread in threading.enumerate():
        if thread != threading.main_thread():  # Skip the main thread
            print(f"Waiting for thread {thread.name} to finish...")
            thread.join()  # Wait for the thread to finish

    print("All threads stopped. Exiting the application...")
    QTimer.singleShot(0, quit_app)

"""
ToDo:
1. Add one more column named "Mode" to the dds csv. [Done]

2. Add dds_command.txt: [Done]
    sernum; col_name; value

3. Update functions that apply on freqscan and delayscan.
    - freqscan: everytime update freq. [Done]
    - delayscan: everytime update delay. [Done]

4. Update functions that apply on dds. [Done]
    - mode: update dds mode.
    - value: update dds value.
    
5. Save Hist: change to the value of freq or delay. [Done]

6. Plot: (lower -> higher level; A seperate program.)
    - add threshold (eg. 10: less than 10 -> 0; bigger than 10 -> 1; Weighted average.)
    - save each individual plot.
    - 8 hist plot together.
    - x axis: freq or delay value everytime.
    - load from the csv file.
    - fit feature.

Bug:
1. Delay scan restarts from the default value everytime. [Fixed]
"""

def pause_program():
    pause_event.clear()  # Clear the event to pause the worker thread
    print("Program paused. Press 'r' to resume...")

# Function to handle resuming the program
def resume_program():
    pause_event.set()  # Set the event to resume the worker thread
    print("Program resumed. Press 'p' to pause...")

# Function to handle aborting the program
def abort_program():
    global running
    print("Aborting the program...")
    running = False
    plt.close('all')
    QTimer.singleShot(0, quit_all_threads)


def hotkey_listener():
    """
    Listens for hotkeys: 'p' to pause, 'r' to resume, and 'ESC' to quit.
    Uses raw input mode to detect keypresses immediately without needing 'Enter'.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)  # Save terminal settings

    try:
        tty.setcbreak(fd)
        while not quit_event.is_set():
            if select.select([sys.stdin], [], [], 0.1)[0]:  # Non-blocking input
                key = sys.stdin.read(1)
                if key == "p":
                    print("[INFO] Program paused. Press 'r' to resume.")
                    pause_event.clear()
                elif key == "r":
                    print("[INFO] Program resumed.")
                    pause_event.set()
                elif key == "\x1b":  # ESC key
                    print("[INFO] Exiting program...")
                    quit_event.set()
                    pause_event.set()  # Ensure the program does not remain paused
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)  # Restore settings

def main_run():
    
    # DDS default value is initialized in this step.
    
    # Unpickle the saved file from UI. Export data as a csv file for each Chapter.
    # export_csv(unpickle("try.dat"))

    generate_everything("everything.txt")

    removeFolder(scantype)

    # Execute user commands in command file.
    run("fpga_commands.txt", "dds_settings.txt", "scan.txt")

    QTimer.singleShot(0, quit_app)
    # sys.exit(app.exec_())

class LivePlot(QObject):
    # Define a signal to receive new data safely
    # new_data_signal = pyqtSignal(float, dict)

    def __init__(self):
        super().__init__()
        # Initialize the figure and axes
        print("Initializing plot...")
        self.fig, self.ax = plt.subplots()
        self.x_data, self.y_data, self.color_data = [], [], []

        # Connect the signal to the update_plot method
        print("Setting up timer...")
        self.timer = self.fig.canvas.new_timer(interval=100)
        self.timer.add_callback(self.update_plot)
        self.timer.start()

    def update_plot(self):
        """Update the plot with new data received via the signal."""
        while not data_queue.empty():
            new_data_x, new_data_y = data_queue.get()
            print(f"New data: x={new_data_x}, y={new_data_y}")

            # Store the new data
            for tag, y_value in new_data_y.items():
                print(f"Tag: {tag}, y-value: {y_value}")
                self.x_data.append(new_data_x)  # Add x value
                self.y_data.append(y_value)  # Add corresponding y value
                self.color_data.append(color_list[tag])  # Add color

        # Redraw the plot immediately after receiving new data
        self.redraw_plot()

    def redraw_plot(self):
        """Redraw the plot with the latest data."""
        self.ax.clear()
        self.ax.scatter(self.x_data, self.y_data, color=self.color_data)

        # Check if x-axis data is in descending order
        if self.x_data and all(earlier >= later for earlier, later in zip(self.x_data, self.x_data[1:])):
            # print("Reversing x-axis...")
            self.ax.invert_xaxis()

        # Set plot labels and formatting
        self.ax.set_title("Live Data Plot")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Data Value")
        self.ax.xaxis.set_major_locator(MaxNLocator(nbins=3))
        self.ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'{x:.2f}'))

        # Rotate x-axis labels to avoid overlap
        for label in self.ax.get_xticklabels():
            label.set_rotation(45)

        # Redraw the figure
        self.fig.canvas.draw()


# def plotting_thread(histFolder, histType, plot_callback, fig, ax, scatter_plots):
#     # This function now uses pre-created plot objects (fig, ax, scatter_plots)

#     while running:
#         pause_event.wait()  # Wait if paused
        
#         # Read all data from files in histFolder using the plot_callback function
#         timeseq_hist, x_axis, ionNo, num_exp, hist_value, all_hists = plot_callback(histFolder, f"{histType}=")

#         # Update scatter plot data
#         for tag, scatter_plot in scatter_plots.items():
#             if tag in timeseq_hist:
#                 curr_y = timeseq_hist[tag]
#                 scatter_plot.set_offsets(list(zip(x_axis, curr_y)))

#         # Update the plot
#         plt.draw()
#         plt.pause(100)  # Pause for a short interval to allow the plot to update

def main():
    # Determine the directory for data collection and plotting
    # histFolder = getScanType()
    # histType = histFolder[0:-4]
    # print(histFolder, histType)
    # removeFolder(scantype)

    # Initialize the plot in the main thread
    # plt.ion()
    # colors = {'a': 'red', 'b': 'green', 'c': 'blue', 'd': 'yellow', 'e': 'purple', 'f': 'black', 'g': 'pink'}
    
    # # Initialize the figure and axis
    # fig, ax = plt.subplots()

    # # Initialize empty scatter plot
    # scatter_plots = {}
    # for tag in colors.keys():
    #     scatter_plots[tag] = ax.scatter([], [], color=colors[tag], label=tag)

    # # Show the legend
    # plt.legend()
    live_plot = LivePlot()
    # Start the data collection thread
    data_thread = threading.Thread(target=main_run)
    data_thread.start()

    # # Start the plotting thread with pre-created figure and scatter plots
    # plot_thread = threading.Thread(target=plotting_thread, args=(histFolder, histType, parse_global_dat_hist, fig, ax, scatter_plots))
    # plot_thread.start()

    # plt.ion()
    plt.show()

    while data_thread.is_alive():
        # Allow Matplotlib to process UI events
        plt.pause(0.1)

    # Wait for threads to complete
    data_thread.join()
    # plot_thread.join()



if __name__ == "__main__":
    hotkey_thread = Thread(target=hotkey_listener, daemon=True)
    hotkey_thread.start()
    try:
        while not quit_event.is_set():
            pause_event.wait()
            main()
    except KeyboardInterrupt:
        print("[INFO] Program interrupted by user.")
    finally:
        quit_event.set()
        hotkey_thread.join()
        print("[INFO] Program terminated.")
