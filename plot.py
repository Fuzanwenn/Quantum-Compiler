import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator
import math
import numpy as np
import os
from fit import sine_fit, ampl_fit, freq_fit
import pickle
import ast
import sys

def parse_dat_hist(folder, path):
    hist_file = open(os.path.join(folder, path), "rb")
    hist_content = pickle.load(hist_file)
    hist = {}
    # for rows in hist_content[1:]:
    #     curr_row = rows.strip().split(",")
    #     curr_ionNo, curr_num_exp, curr_value, curr_tag = curr_row[0:4]
    #     curr_hist = [int(x) for x in curr_row[4:]]
    #     hist[curr_tag] = curr_hist
    # print(hist)

    for tag in hist_content.keys():
        curr_hist = hist_content[tag]
        # print(curr_hist)
        curr_ionNo = curr_hist["ionNo"]
        curr_num_exp = curr_hist["num of exp"]
        curr_value  = curr_hist["value"]
        hist[tag] = curr_hist["list"]

    return curr_ionNo, curr_num_exp, curr_value, hist
    

def basic_plot(hist):
    # Single plot
    if len(hist.keys()) == 1:
        fig, ax = plt.subplots()
        tag = list(hist.keys())[0]
        print(f"Plotted histogram {tag}.")
        x_axis = range(150)
        y_axis = np.array(hist[tag][0:150])
        plt.bar(x_axis, y_axis)
        plt.title(f"Histogram {tag}")
        ax.xaxis.set_major_locator(MultipleLocator(50))
        ax.xaxis.set_minor_locator(MultipleLocator(10))

    # One dim plot
    elif len(hist.keys()) == 2:
        fig, axs = plt.subplots(1, len(hist.keys()))
        index = 0
        for tag in hist.keys():
            print(f"Plotted histogram {tag}.")
            x_axis = range(150)
            y_axis = np.array(hist[tag][0:150])
            axs[index].bar(x_axis, y_axis)
            axs[index].set_title(f"Histogram {tag}")
            axs[index].xaxis.set_major_locator(MultipleLocator(50))
            axs[index].xaxis.set_minor_locator(MultipleLocator(10))
            index += 1

    # Multiple dim plot
    else:
        fig, axs = plt.subplots(math.ceil(len(hist.keys())/2), 2)
        row = 0
        col = 0
        for tag in hist.keys():
            print(f"Plotted histogram {tag}.")
            x_axis = range(150)
            y_axis = np.array(hist[tag][0:150])
            axs[row, col].bar(x_axis, y_axis)
            axs[row, col].set_title(f"Histogram {tag}")
            axs[row, col].xaxis.set_major_locator(MultipleLocator(50))
            axs[row, col].xaxis.set_minor_locator(MultipleLocator(10))
            if col == 0:
                col+=1
            else:
                col=0
                row+=1
    plt.tight_layout()
    # Display the plot
    plt.show()


# def parse_global_dat_hist(folder, file_pattern, threshold=-1):
#     timeseq_hist = {}
#     all_hists = []
#     x_axis = []
#     values = []
#     for file in os.listdir(folder):
#         if file.startswith(file_pattern) and file.endswith(".dat"):
#             curr_ionNo, curr_num_exp, curr_value, curr_hist = parse_dat_hist(folder, file)
#             values.append(curr_value)
#             if threshold != -1:
#                 single_timeseq_hist = get_single_timeseq_hist_threshold(curr_hist, threshold)
#             else:
#                 single_timeseq_hist = get_single_timeseq_hist(curr_hist)
#             # print(single_timeseq_hist)
#             all_hists.append(single_timeseq_hist)
#             for tag in single_timeseq_hist.keys():
#                 if tag not in timeseq_hist.keys():
#                     timeseq_hist[tag] = [single_timeseq_hist[tag]]
#                 else:
#                     timeseq_hist[tag].append(single_timeseq_hist[tag])                
#             x = file.removeprefix(file_pattern)
#             x = x.removesuffix(".dat")
#             x = round(float(x), 2)
#             x_axis.append(x)
#     # print(timeseq_hist, x_axis)
#     return timeseq_hist, x_axis


def parse_Scandata(threshold=None):
    scandata = getScandata()
    timeseq_hist = {}
    for hist in scandata.histogram:
        if threshold is None:
            curr_hist = get_single_timeseq_hist(hist)
        else:
            curr_hist = get_single_timeseq_hist_threshold(hist, threshold)
        for tag in hist.keys():
            if tag not in timeseq_hist.keys():
                timeseq_hist[tag] = [curr_hist[tag]]
            else:
                timeseq_hist[tag].append(curr_hist[tag])
    print(scandata.getx())

    return timeseq_hist, scandata.getx()


def get_single_timeseq_hist_threshold(hist, threshold):
    single_timeseq_hist = {}
    for tag in hist.keys():
        curr_hist = hist[tag]
        # hist_abv = np.array(curr_hist) * np.array(range(len(curr_hist)))
        weighted_average = sum(curr_hist[threshold:]) / sum(curr_hist)
        single_timeseq_hist[tag] = weighted_average
        print(single_timeseq_hist)
    return single_timeseq_hist

def get_single_timeseq_hist(hist):
    single_timeseq_hist = {}
    for tag in hist.keys():
        curr_hist = hist[tag]
        
        average = 0
        for i in range(0, len(curr_hist)-1):
            average += i * curr_hist[i]
        total = sum(curr_hist)
        if total != 0:
            weighted_average = float(average) / float(total)
        else:
            weighted_average = 0.00

        single_timeseq_hist[tag] = weighted_average
        # print(weighted_average)
    return single_timeseq_hist

def timeseq_plot(timeseq_hist, x_axis, ax):
    colors = {'a':'red', 'b':'green', 'c':'blue', 'd':'yellow', 'e':'purple', 'f':'black', 'g':'pink'}
    print(timeseq_hist)
    print(x_axis)

    for tag in timeseq_hist.keys():
        curr_y = timeseq_hist[tag]
        ax.scatter(x_axis, curr_y, color=colors[tag], label=f'Original {tag}')
    ax.legend()

def timeseq_plot_threshold(timeseq_hist, x_axis, ax, fig):
    colors = {'a':'red', 'b':'green', 'c':'blue', 'd':'yellow', 'e':'purple', 'f':'black', 'g':'pink'}
    for tag in timeseq_hist.keys():
        curr_y = timeseq_hist[tag]
        if len(x_axis) != len(curr_y):
            print(f"Length mismatch for {tag}: len(x_axis)={len(x_axis)}, len(curr_y)={len(curr_y)}")
            # Adjust lengths here if necessary
            min_len = min(len(x_axis), len(curr_y))
            x_axis_trimmed = x_axis[:min_len]
            curr_y_trimmed = curr_y[:min_len]
        else:
            x_axis_trimmed = x_axis
            curr_y_trimmed = curr_y

        ax.set_xlim(min(x_axis), max(x_axis))
        ax.set_ylim(0, 1)
        ax.scatter(x_axis_trimmed, curr_y_trimmed, c=colors[tag], label=f'Original {tag} (Threshold)')
    ax.legend()
    ax.relim()
    ax.autoscale_view()

    # Redraw plot
    plt.draw()
    plt.pause(0.1)


def set_sine_fit(scandata):
    fit = sine_fit()
    # for i in range(0,num_of_exp):
    #     # curr_value = values[i].removeprefix("[")
    #     # curr_value = curr_value.removesuffix("]")
    #     # curr_value = [float(x) for x in values[i].split(" ")]
    #     scandata.add_pair(x_axis[i], values[i], hists[i])
    x = np.array(scandata.getx()[::-1])
    yavg = np.array(scandata.get_avg()[::-1])
    fit.set_data(np.array(x), np.array(yavg) )
    return scandata, fit

def set_freq_fit(scandata):
    fit = freq_fit()
    # for i in range(0,num_of_exp):
    #     # curr_value = values[i].removeprefix("[")
    #     # curr_value = curr_value.removesuffix("]")
    #     # curr_value = [float(x) for x in values[i].split(" ")]
    #     scandata.add_pair(x_axis[i], values[i], hists[i])
    x = np.array(scandata.getx()[::-1])
    yavg = np.array(scandata.get_avg()[::-1])
    fit.set_data(np.array(x), np.array(yavg) )
    return scandata, fit

def filter_data(x, x_start, x_end):
    start_index = np.argmin(abs(x-x_start))
    end_index = np.argmin(abs(x-x_end))
    return start_index, end_index

def set_ampl_fit(scandata):
    fit = ampl_fit()
    x = np.array(scandata.getx()[::-1])
    yavg = np.array(scandata.get_avg()[::-1])
    fit.set_data(np.array(x), np.array(yavg) )
    return scandata, fit

def fit_sine(scandata, fit, a, b, Tpi):
    fit.set_params(a, b, Tpi)
    fit.fit()
    fit.print_all()
    x = scandata.getx()
    xlarge = np.linspace(x[0], x[-1], 400)
    y = fit.function_data(xlarge)
    return xlarge, y

def fit_freq(scandata, fit, a, b, f0, Tpi, T):
    fit.set_params(a, b, f0, Tpi, T)
    fit.fit()
    fit.print_all()
    x = scandata.getx()
    xlarge = np.linspace(x[0], x[-1], 400)
    y = fit.function_data(xlarge)
    return xlarge, y

def fit_ampl(scandata, fit, alpha, beta, gamma, start, end):
    fit.set_params( alpha, beta, gamma)
    fit.fit()
    fit.print_all()
    x = np.array(scandata.getx()[::-1])
    start_index, end_index = filter_data(x, start, end)
    if start_index >= end_index:
        print(f'Filter failed: start_index = {start_index}, end_index = {end_index}')
        return
    x = x[start_index:end_index]
    xlarge = np.linspace(x[0], x[-1], 400)
    y = fit.function_data(xlarge)
    return xlarge, y
    

def fit_command(scandata, ax):
    
    while True:
        # plt.ion()  # Turn on interactive mode
        # fig, ax = plt.subplots()
        # line, = ax.plot([], [])
        fit_type = input("Enter your fit type: (sine, freq, ampl)\n")
        line, = ax.plot([], [], label='Fit Curve', color='red')  # Placeholder for the fit curve
        updated_scatter = ax.scatter([], [], color='green', marker='x', label='Updated Data')  # Placeholder for updated data

        # scandata = ScanData()
        # scandata.ydata(ionNo)
        if fit_type.lower().startswith("s"):
            sine_scandata, sine_fit = set_sine_fit(scandata)
            sine_a = input("Enter value for 'a':\n")
            sine_b = input("Enter value for 'b':\n")
            sine_pi = input("Enter value for 'Pi time, us':\n")
            xlarge, y = fit_sine(sine_scandata, sine_fit, float(sine_a), float(sine_b), float(sine_pi))
            plt.title("y = a + b Sin(t * pi / 2 Tpi)^2")
        elif fit_type.lower().startswith("f"):
            freq_scandata, freq_fit = set_freq_fit(scandata)
            freq_a = input("Enter value for 'a':\n")
            freq_b = input("Enter value for 'b':\n")
            freq_f0 = input("Enter value for 'Pi time, us':\n")
            freq_Tpi = input("Enter value for 'Pulse time, us':\n")
            freq_T = input("Enter value for 'Frequency, MHz':\n")
            xlarge, y = fit_freq(freq_scandata, freq_fit, float(freq_a), float(freq_b), float(freq_f0), float(freq_Tpi), float(freq_T))
            plt.title("Freqency fit")
        elif fit_type.lower().startswith("a"):
            ampl_alpha = input("Enter value for 'alpha':\n")
            ampl_beta = input("Enter value for 'beta':\n")
            ampl_gamma = input("Enter value for 'gamma':\n")
            ampl_start = input("Enter value for 'start':\n")
            ampl_end = input("Enter value for 'end':\n")
            ampl_scandata, ampl_fit, start, end = set_ampl_fit(scandata)
            xlarge, y = fit_ampl(ampl_scandata, ampl_fit, float(ampl_alpha), float(ampl_beta), float(ampl_gamma), start, end)
            plt.title("y = 0.5(1 - e^(αA) cos(βA+γ))")
        else:
            print("Incorrect fit type!")
            break

        line.set_xdata(xlarge)
        line.set_ydata(y)
        # ax.relim()
        # ax.autoscale_view()
        y_updated = y  # Updated data (using fit function)
        updated_scatter.set_offsets(np.c_[xlarge, y_updated])

        ax.relim()
        ax.autoscale_view()
        ax.legend()

        # Redraw plot
        plt.draw()
        plt.pause(0.1)
        next_fit = input("Do you want to fit again: Y/N?\n")
        if not next_fit.lower().startswith("y"):
            break

def getScandata():
    file = open("scandata.dat", "rb")
    scandata = pickle.load(file)
    return scandata

def main():
    while True:
        plotType = input("Choose your plot type: single/timeseq\n")
        if plotType.strip().startswith("s"):
            while True:
                histFolder = input("Choose your scan type: delayscan/freqscan\n")
                if histFolder.startswith("d"):
                    histFolder, histType = "delayscan", "delay"
                    break
                elif histFolder.startswith("f"):
                    histFolder, histType = "freqscan", "freq"
                    break
                else:
                    print("You have to input either delayscan or freqscan. Please try again!")
            while True:
                value = input(f"Enter the exact {histType} value you want to plot:\n")
                try:
                    ionNo, num_exp, hist_value, hist = parse_dat_hist(histFolder, f"{histType}={value}.dat")
                    break
                except:
                    print(f"The value {value} is not found. Please check you value!")

            basic_plot(hist)

            exitMsg = input("Do you want to exit: Y/N?\n")
            if exitMsg.lower() == "y":
                break

        elif plotType.strip().startswith("t"):
            while True:
                histFolder = input("Choose your scan type: delayscan/freqscan\n")
                if histFolder.startswith("d"):
                    histFolder, histType = "delayscan", "delay"
                    break
                elif histFolder.startswith("f"):
                    histFolder, histType = "freqscan", "freq"
                    break
                else:
                    print("You have to input either delayscan or freqscan. Please try again!")

            threshold_check = input("Apply threshold: Y/N?\n")
            plt.ion()  # Turn on interactive mode
            fig, ax = plt.subplots()
            if threshold_check.lower() == "y":
                
                while True:
                    threshold = input("Enter the threshold value:\n")
                    try:
                        # timeseq_hist, x_axis = parse_global_dat_hist(histFolder, f"{histType}=", int(threshold))
                        timeseq_hist, x_axis = parse_Scandata(int(threshold))
                    except:
                        print("Invalid value for threshold. Please try again!")
                    ax.clear()
                    timeseq_plot_threshold(timeseq_hist, x_axis, ax)
                    next_threshold = input("Do you want to apply threshold again: Y/N?\n")
                    if not next_threshold.lower().startswith("y"):
                        break

            else:
                # timeseq_hist, x_axis = parse_global_dat_hist(histFolder, f"{histType}=")
                timeseq_hist, x_axis = parse_Scandata()
                timeseq_plot(timeseq_hist, x_axis, ax)

            fit_msg = input("Do you want to fit the plot: Y/N?\n")
            if fit_msg.lower() == "y":
                fit_command(getScandata(), ax)
                    
            exitMsg = input("Do you want to exit: Y/N?\n")
            if exitMsg.lower() == "y":
                break

        else:
            print("You have to input either single or timeseq. Please try again!")
        

if __name__ == "__main__":
    main()