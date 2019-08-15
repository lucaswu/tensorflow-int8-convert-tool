from base import *
import tensorflow as tf
import math
import os
from data_utils import *
import numpy as np
import math, copy
from scipy import stats

class Quantization(object):
    def __init__(self,graph,name,num=2048):
        self.graph = graph
        self.num_bins = num

        self.histogram = np.zeros(self.num_bins)
        self.histogram_interval = 0.0
        self.max_value = 0.0
        self.threshold = 0.0
    
        self.scale = 0.0
        self.name = name

    def quantize_weight(self,output_path='test'):
        with tf.Session(graph=self.graph) as sess:
            for op in self.graph.get_operations():
                if(op.type == "Conv2D"):
                    for input in op.inputs:
                        if "weights" in input.name:
                            var = input
                            filename = '{}-{}'.format(output_path, var.name.replace(':', '-'))
                            output_dir, output_filename = os.path.split(filename)
                            output_dir2, output_filename2 = os.path.split(output_dir)
                          
                            makeDir(output_dir2)
                            new_name = output_filename2 + '_' + output_filename
                            new_path = os.path.join(output_dir2, new_name)

                            var = tf.transpose(var, perm=[3, 2, 0, 1])
                            weightData = sess.run(var)
                            
            
                            max_val = np.max(weightData)
                            min_val = np.min(weightData)
                            threshold = max(abs(max_val), abs(min_val))

                            weight_scale = 127./threshold

                            weight_scale = np.array([weight_scale])
                            weight_scale = weight_scale.astype(np.float32)

                            with open(new_path+"_scale", mode='w') as file_:
                                weight_scale.tofile(file_)
                            print2("%s scale:%f"%(input.name,weight_scale),textColor="red")

    def initial_max(self,result):
        max_val = np.max(result)
        min_val = np.min(result)
        self.max_value = max(self.max_value, max(abs(max_val), abs(min_val)))
    
    def initial_histogram_interval(self):
        self.histogram_interval = self.max_value/self.num_bins


    def initial_histograms(self,result):
        th = self.max_value

        hist, hist_edge = np.histogram(result,bins=self.num_bins,range=(0,th))
        self.histogram += hist

    def threshold_distribution(self,target_bin = 128):
        distribution = self.histogram[1:]
        length = distribution.size
        threshold_sum = sum(distribution[target_bin:])
        kl_divergence = np.zeros(length - target_bin)

        for threshold in range(target_bin, length):
            sliced_nd_hist = copy.deepcopy(distribution[:threshold])

            # generate reference distribution p
            p = sliced_nd_hist.copy()
            p[threshold-1] += threshold_sum
            threshold_sum = threshold_sum - distribution[threshold]

            # is_nonzeros[k] indicates whether hist[k] is nonzero
            is_nonzeros = (p != 0).astype(np.int64)
            # 
            quantized_bins = np.zeros(target_bin, dtype=np.int64)
            # calculate how many bins should be merged to generate quantized distribution q
            num_merged_bins = sliced_nd_hist.size // target_bin
            
            # merge hist into num_quantized_bins bins
            for j in range(target_bin):
                start = j * num_merged_bins
                stop = start + num_merged_bins
                quantized_bins[j] = sliced_nd_hist[start:stop].sum()
            quantized_bins[-1] += sliced_nd_hist[target_bin * num_merged_bins:].sum()
            
            # expand quantized_bins into p.size bins
            q = np.zeros(sliced_nd_hist.size, dtype=np.float64)
            for j in range(target_bin):
                start = j * num_merged_bins
                if j == target_bin - 1:
                    stop = -1
                else:
                    stop = start + num_merged_bins
                norm = is_nonzeros[start:stop].sum()
                if norm != 0:
                    q[start:stop] = float(quantized_bins[j]) / float(norm)
            q[p == 0] = 0
            # p = _smooth_distribution(p) # with some bugs, need to fix
            # q = _smooth_distribution(q)
            p[p == 0] = 0.0001
            q[q == 0] = 0.0001
            
            # calculate kl_divergence between q and p
            kl_divergence[threshold - target_bin] = stats.entropy(p, q)

        min_kl_divergence = np.argmin(kl_divergence)
        threshold_value = min_kl_divergence + target_bin

        return threshold_value

    def quantize_data(self):
        distribution = np.array(self.histogram)
        threshold_bin = self.threshold_distribution()
        self.threshold = threshold_bin
        threshold = (threshold_bin + 0.5) * self.histogram_interval
        self.scale = 127./threshold

        print2("%-20s ,maxvalue:%-10f,bin:%-10f,threshold:%-10f,interval:%-10f,scale:%-10f"%(self.name,self.max_value,threshold_bin,threshold,self.histogram_interval,self.scale),textColor="red")

        return self.scale




    





                            

