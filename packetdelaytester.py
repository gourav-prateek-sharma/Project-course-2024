from loguru import logger
import numpy as np
import json
import matplotlib.pyplot as plt
import os

def get_ran_delay(packet):
    if packet.get('ip.out_t')!=None and packet.get('ip.in_t')!=None:
        return (packet['ip.out_t']-packet['ip.in_t'])*1000
    else:
        logger.error(f"Packet {packet['id']} either ip.in_t or ip.out_t not present")
        return None
    
def plot_ccdf(delays, label, figsize=(10, 6)):
    """
    Plots the Complementary Cumulative Distribution Function (CCDF) of the given delays.
    
    Parameters:
        delays (list or array-like): The delay values to plot.
        label (str): The label for the plot.
        figsize (tuple): The size of the figure (default is (10, 6)).
        
    Returns:
        fig, ax: The figure and axis objects of the plot.
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Sort the delay values and calculate the CCDF
    sorted_delays = np.sort(delays)
    ccdf = 1.0 - np.arange(1, len(sorted_delays) + 1) / len(sorted_delays)
    
    # Plot the CCDF
    ax.plot(sorted_delays, ccdf, linestyle='-', linewidth=4, label=label)
    
    # Set the y-axis to a logarithmic scale
    ax.set_yscale('log')
    
    # Label the axes
    ax.set_xlabel('Delay (ms)', fontsize=15)
    ax.set_ylabel('Probability', fontsize=15)
    ax.tick_params(axis='both', labelsize=16)

    
    # Add grid and legend
    ax.grid(True)
    ax.legend()
    
    return fig, ax

#/Users/haree/Desktop/5G Causal modelling/s24

MEAS_LABEL = 'Users/haree/Desktop/5G Causal modelling/s24'
PLOTS_DIR = './plots/'+MEAS_LABEL+'/'

packets_path='/'+MEAS_LABEL+'/packets.json'
with open(packets_path, 'r') as file:
    packets = json.load(file)

ran_delays = np.array(list({packet['id']: get_ran_delay(packet) 
                                for packet in packets 
                               if get_ran_delay(packet) is not None}.values()))

# Ensure the PLOTS_DIR exists
if not os.path.exists(PLOTS_DIR):
    os.makedirs(PLOTS_DIR)

# skip the extreme packets
SKIP_FIRST = 1200
SKIP_LAST = 100

fig, ax  = plot_ccdf(ran_delays[SKIP_FIRST:-SKIP_LAST], '_', figsize=(8, 5))
plt.savefig(f"{PLOTS_DIR}ran_delays_ccdf_plot.png", dpi=300, bbox_inches='tight')  # You can change the file format (e.g., .pdf)
plt.show()