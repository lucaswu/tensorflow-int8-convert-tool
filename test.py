import tensorflow as tf
import numpy as np
import scipy
from quantization import *
import os
from data_utils import *
from video import *


def load_graph(frozen_graph_filename):
    # We parse the graph_def file
    with tf.gfile.GFile(frozen_graph_filename, "rb") as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())

    # We load the graph_def in the default graph
    with tf.Graph().as_default() as graph:
        tf.import_graph_def(
            graph_def,
            input_map=None,
            return_elements=None,
            name="",
            op_dict=None,
            producer_op_list=None
        )
    return graph

class PreTrain(object):
    def __init__(self,graph,num_bins,inputName,outputName,outDir):
        self.graph = graph
        self.input_name = inputName
        self.output_name = outputName
        self.quantization = Quantization(graph,outputName)
        self.out_dir = outDir
        self.quantization.quantize_weight(outDir+"/weight")
        self.hasDir = False

    def pretrain_from_video(self,video_name):
        videoTypes = ['.avi', '.mp4', '.flv', '.mov', '.mkv', '.wmv']
        if os.path.splitext(video_name)[1] not in videoTypes:
            print2("input file:%s is not a video!" % video_name, textColor="red")
            return
        reader = VideoReader(video_name, pix_fmt='I420')
        [frame_num, fps, w, h] = [reader.frame_num, reader.fps, reader.w, reader.h]

        num = 1#frame_num#min(100,frame_num)
        x = graph.get_tensor_by_name(self.input_name)
        y = graph.get_tensor_by_name(self.output_name)

        with tf.Session(graph=graph) as sess:
            #get the max value
            for i in range(0,num):
                frame = reader.get_frame(i)
                [framein_y, framein_u, framein_v] = split_yuv420(frame)
                framein_y = np.asarray(framein_y, dtype=np.float32)
            
                output = sess.run(y,feed_dict={x:framein_y})
                self.quantization.initial_max(output)
                # print(output)

            #histogram_interval
            self.quantization.initial_histogram_interval()

            #histogram
            for i in range(0,num):
                frame = reader.get_frame(i)
                [framein_y, framein_u, framein_v] = split_yuv420(frame)
                framein_y = np.asarray(framein_y, dtype=np.float32)
            
                output = sess.run(y,feed_dict={x:framein_y})
                self.quantization.initial_histograms(output)

            #kId
            if self.hasDir == False:
                return self.quantization.get_scale()
            

    def pretrain_from_video_path(self,input_path):

        if not os.path.exists(input_path):
            print2("input path: %s does not exit!" % input_path, textColor="red")
            return
        fileTypes = ['.avi', '.mp4', '.flv', '.mov', '.mkv']

        self.hasDir = True

        for video_file in os.listdir(input_path):
            video_name = os.path.join(input_path, video_file)
            if os.path.splitext(video_name)[1] not in fileTypes:
                # print2("skip %s" % video_file, textColor="red")
                continue
            # print2("processing the video: %s" % video_name, textColor="green")
            self.pretrain_from_video(video_name)

        scale = self.quantization.quantize_data()

        return scale

if __name__ == '__main__':
    graph = load_graph('model/sharpen.pb')

    for op in graph.get_operations():
        print(op.name,op.values(),op.type)

    quan_name = []
    graph = load_graph('model/sharpen.pb')
    for op in graph.get_operations():
        if op.type == "BiasAdd":
            quan_name.append(op.name)
        if op.type == "ConcatV2":
            quan_name.append(op.name)
        print(op.name,op.values(),op.type)
        if(op.type == "Add"):
            if "sharpen" in op.name:
                for input in op.inputs:
                    if "conv" in input.name:
                       quan_name.append(op.name) 
            else:    
                quan_name.append(op.name)
            # print2(op.name,textColor="red")
            # for input in op.inputs:
            #     print(input.name)

    print2(quan_name,type(quan_name),len(quan_name))

    outDir = "test/"
    for i in range(0,len(quan_name)):
        name = quan_name[i] +":0"
        preTrain = PreTrain(graph,2048,"src_input_1:0",name,outDir)
        scale = preTrain.pretrain_from_video_path("video")
        scale = np.array([scale])
        scale = scale.astype(np.float32)
        filename = quan_name[i].replace('/', '_')
        filename = outDir + filename + "_Scale"
        with open(filename, mode='w') as file_:
            scale.tofile(file_)
            print2("save %s"%filename,textColor="green")
